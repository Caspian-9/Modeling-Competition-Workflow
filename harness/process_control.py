from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from ctypes import Structure, WinDLL, byref, c_size_t, sizeof
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class ProcessOutcome:
    exit_code: int
    timed_out: bool
    duration_seconds: float
    stdout_truncated: bool
    stderr_truncated: bool


def run_process(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
    max_log_bytes: int,
    on_timeout: Callable[[], None] | None = None,
    on_start: Callable[[int], None] | None = None,
    stdin_bytes: bytes | None = None,
) -> ProcessOutcome:
    """Run a process without a shell, bounding logs and killing its process tree."""
    creation: dict[str, Any] = {}
    if os.name == "nt":
        creation["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        creation["start_new_session"] = True

    started_clock = time.monotonic()
    process = subprocess.Popen(
        tuple(command),
        cwd=cwd,
        env=dict(environment),
        shell=False,
        stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **creation,
    )
    windows_job = _WindowsKillJob.attach(process) if os.name == "nt" else None
    if on_start is not None:
        try:
            on_start(process.pid)
        except Exception:
            if windows_job is not None:
                windows_job.terminate()
                windows_job.close()
            _terminate_process_tree(process)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
            raise
    truncation = {"stdout": False, "stderr": False}
    stdout_thread = threading.Thread(
        target=_drain_stream,
        args=(process.stdout, stdout_path, "stdout", truncation, max_log_bytes),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_drain_stream,
        args=(process.stderr, stderr_path, "stderr", truncation, max_log_bytes),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    stdin_thread: threading.Thread | None = None
    if stdin_bytes is not None and process.stdin is not None:
        stdin_thread = threading.Thread(
            target=_write_stdin,
            args=(process.stdin, stdin_bytes),
            daemon=True,
        )
        stdin_thread.start()
    timed_out = False
    try:
        exit_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        if on_timeout is not None:
            try:
                on_timeout()
            except Exception:
                pass
        if windows_job is not None:
            windows_job.terminate()
        _terminate_process_tree(process)
        try:
            exit_code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                exit_code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                exit_code = -9
    finally:
        # Closing a kill-on-close Job Object removes descendants that outlived a
        # cmd/PowerShell wrapper before pipe-draining threads are joined.
        if windows_job is not None:
            windows_job.close()
        stdout_thread.join(timeout=10)
        stderr_thread.join(timeout=10)
        if stdin_thread is not None:
            stdin_thread.join(timeout=10)
        if (
            not stdout_thread.is_alive()
            and process.stdout is not None
            and not process.stdout.closed
        ):
            process.stdout.close()
        if (
            not stderr_thread.is_alive()
            and process.stderr is not None
            and not process.stderr.closed
        ):
            process.stderr.close()

    return ProcessOutcome(
        exit_code=exit_code,
        timed_out=timed_out,
        duration_seconds=round(time.monotonic() - started_clock, 6),
        stdout_truncated=truncation["stdout"],
        stderr_truncated=truncation["stderr"],
    )


def _write_stdin(stream: Any, payload: bytes) -> None:
    try:
        stream.write(payload)
        stream.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        stream.close()


def _drain_stream(
    stream: Any,
    path: Path,
    key: str,
    truncation: dict[str, bool],
    max_log_bytes: int,
) -> None:
    written = 0
    truncated = False
    try:
        with path.open("wb") as handle:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                remaining = max_log_bytes - written
                if remaining > 0:
                    payload = chunk[:remaining]
                    handle.write(payload)
                    written += len(payload)
                if len(chunk) > max(remaining, 0):
                    truncated = True
            if truncated:
                handle.write(b"\n[log truncated by harness policy]\n")
    finally:
        stream.close()
    truncation[key] = truncated


def _terminate_process_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            shell=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


class _JobObjectBasicLimitInformation(Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
        ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", c_size_t),
        ("MaximumWorkingSetSize", c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(Structure):
    _fields_ = [
        ("ReadOperationCount", wintypes.ULARGE_INTEGER),
        ("WriteOperationCount", wintypes.ULARGE_INTEGER),
        ("OtherOperationCount", wintypes.ULARGE_INTEGER),
        ("ReadTransferCount", wintypes.ULARGE_INTEGER),
        ("WriteTransferCount", wintypes.ULARGE_INTEGER),
        ("OtherTransferCount", wintypes.ULARGE_INTEGER),
    ]


class _JobObjectExtendedLimitInformation(Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", c_size_t),
        ("JobMemoryLimit", c_size_t),
        ("PeakProcessMemoryUsed", c_size_t),
        ("PeakJobMemoryUsed", c_size_t),
    ]


class _WindowsKillJob:
    _KILL_ON_JOB_CLOSE = 0x00002000
    _EXTENDED_LIMIT_INFORMATION = 9

    def __init__(self, kernel32: Any, handle: int) -> None:
        self.kernel32 = kernel32
        self.handle = handle

    @classmethod
    def attach(cls, process: subprocess.Popen[Any]) -> "_WindowsKillJob | None":
        try:
            kernel32 = WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
            kernel32.SetInformationJobObject.restype = wintypes.BOOL
            kernel32.SetInformationJobObject.argtypes = (
                wintypes.HANDLE,
                wintypes.INT,
                wintypes.LPVOID,
                wintypes.DWORD,
            )
            kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
            kernel32.TerminateJobObject.restype = wintypes.BOOL
            kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            handle = kernel32.CreateJobObjectW(None, None)
            if not handle:
                return None
            information = _JobObjectExtendedLimitInformation()
            information.BasicLimitInformation.LimitFlags = cls._KILL_ON_JOB_CLOSE
            configured = kernel32.SetInformationJobObject(
                handle,
                cls._EXTENDED_LIMIT_INFORMATION,
                byref(information),
                wintypes.DWORD(sizeof(information)),
            )
            assigned = configured and kernel32.AssignProcessToJobObject(
                handle, wintypes.HANDLE(process._handle)
            )
            if not assigned:
                kernel32.CloseHandle(handle)
                return None
            return cls(kernel32, handle)
        except (AttributeError, OSError, TypeError, ValueError):
            return None

    def terminate(self) -> None:
        if self.handle:
            self.kernel32.TerminateJobObject(self.handle, 1)

    def close(self) -> None:
        if self.handle:
            self.kernel32.CloseHandle(self.handle)
            self.handle = 0
