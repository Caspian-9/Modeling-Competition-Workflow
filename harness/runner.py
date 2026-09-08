from __future__ import annotations

import os
import platform
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

from .models import (
    ExperimentManifest,
    ValidationError,
    hash_path,
    resolve_within,
    utc_now,
)
from .process_control import run_process
from .storage import CaseRepository


DEFAULT_EXECUTABLES = frozenset(
    {
        "python",
        "python.exe",
        "py",
        "py.exe",
        "rscript",
        "rscript.exe",
        "julia",
        "julia.exe",
    }
)


class RunnerError(ValidationError):
    pass


class ExperimentRunner:
    def __init__(
        self,
        repository: CaseRepository,
        *,
        timeout_seconds: int = 3600,
        max_log_bytes: int = 4 * 1024 * 1024,
        allowed_executables: Iterable[str] = (),
    ) -> None:
        if timeout_seconds < 1:
            raise RunnerError("timeout_seconds must be positive")
        if max_log_bytes < 1024:
            raise RunnerError("max_log_bytes must be at least 1024")
        self.repository = repository
        self.timeout_seconds = timeout_seconds
        self.max_log_bytes = max_log_bytes
        self.allowed_executables = DEFAULT_EXECUTABLES | {
            item.lower() for item in allowed_executables
        }

    def run(
        self, case_id: str, question_id: str, experiment_id: str
    ) -> dict[str, Any]:
        manifest = self.repository.load_manifest(case_id, question_id, experiment_id)
        self._validate_command(manifest.command)
        case_dir = self.repository.case_dir(manifest.case_id)
        experiment_dir = self.repository.experiment_dir(
            manifest.case_id, manifest.question_id, manifest.experiment_id
        )
        self._verify_inputs(case_dir, manifest)
        self._clear_outputs(experiment_dir, manifest.expected_outputs)
        attempt = self._next_attempt(experiment_dir)
        run_dir = experiment_dir / "runs" / f"run-{attempt:03d}"
        run_dir.mkdir(parents=True, exist_ok=False)
        stdout_path = run_dir / "stdout.log"
        stderr_path = run_dir / "stderr.log"
        code_hash_before = hash_path(experiment_dir / "code", ignore_transient=True)
        started_at = utc_now()

        manifest.status = "RUNNING"
        manifest.qc = None
        self.repository.write_manifest(manifest)
        command = self._effective_command(manifest.command)
        environment = self._experiment_environment()
        environment.update(
            {
                "MODELING_CASE_DIR": str(case_dir),
                "MODELING_RAW_DIR": str(case_dir / "raw"),
                "MODELING_DATA_DIR": str(case_dir / "data"),
                "MODELING_EXPERIMENT_DIR": str(experiment_dir),
                "MODELING_OUTPUT_DIR": str(experiment_dir / "outputs"),
                "MODELING_SEED": str(manifest.seed),
                "PYTHONHASHSEED": str(manifest.seed),
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
                "MPLCONFIGDIR": str(experiment_dir / ".matplotlib"),
            }
        )
        try:
            outcome = run_process(
                command,
                cwd=experiment_dir,
                environment=environment,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                timeout_seconds=self.timeout_seconds,
                max_log_bytes=self.max_log_bytes,
            )
            process_error = None
        except OSError as exc:
            outcome = None
            process_error = f"{type(exc).__name__}: {exc}"
            stdout_path.write_bytes(b"")
            stderr_path.write_text(process_error + "\n", encoding="utf-8")

        outputs = self._collect_outputs(experiment_dir, manifest.expected_outputs)
        code_hash_after = hash_path(experiment_dir / "code", ignore_transient=True)
        status = (
            "SUCCEEDED"
            if outcome is not None and outcome.exit_code == 0 and not outcome.timed_out
            else "FAILED"
        )
        result = {
            "schema_version": "fast-1.0",
            "case_id": manifest.case_id,
            "question_id": manifest.question_id,
            "experiment_id": manifest.experiment_id,
            "attempt": attempt,
            "started_at": started_at,
            "finished_at": utc_now(),
            "status": status,
            "command": list(command),
            "seed": manifest.seed,
            "timeout_seconds": self.timeout_seconds,
            "exit_code": outcome.exit_code if outcome is not None else None,
            "timed_out": outcome.timed_out if outcome is not None else False,
            "duration_seconds": outcome.duration_seconds if outcome is not None else 0.0,
            "stdout_truncated": (
                outcome.stdout_truncated if outcome is not None else False
            ),
            "stderr_truncated": (
                outcome.stderr_truncated if outcome is not None else False
            ),
            "process_error": process_error,
            "code_sha256_before": code_hash_before,
            "code_sha256_after": code_hash_after,
            "inputs": [dict(item) for item in manifest.inputs],
            "outputs": outputs,
            "runtime": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "executable": command[0],
            },
            "logs": {
                "stdout": stdout_path.relative_to(experiment_dir).as_posix(),
                "stderr": stderr_path.relative_to(experiment_dir).as_posix(),
            },
        }
        self.repository.write_json(run_dir / "run.json", result)
        manifest.status = status
        manifest.latest_run = (run_dir / "run.json").relative_to(
            experiment_dir
        ).as_posix()
        self.repository.write_manifest(manifest)
        return result

    def run_batch(
        self,
        case_id: str,
        question_id: str,
        experiment_ids: Iterable[str],
        *,
        max_workers: int = 8,
    ) -> list[dict[str, Any]]:
        identifiers = tuple(experiment_ids)
        if not identifiers:
            raise RunnerError("experiment_ids must not be empty")
        if len(set(identifiers)) != len(identifiers):
            raise RunnerError("experiment_ids must be unique")
        if max_workers < 1:
            raise RunnerError("max_workers must be positive")
        results: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=min(max_workers, len(identifiers))) as pool:
            futures = {
                pool.submit(self.run, case_id, question_id, experiment_id): experiment_id
                for experiment_id in identifiers
            }
            for future in as_completed(futures):
                experiment_id = futures[future]
                try:
                    results[experiment_id] = future.result()
                except Exception as exc:
                    results[experiment_id] = {
                        "schema_version": "fast-1.0",
                        "case_id": case_id,
                        "question_id": question_id,
                        "experiment_id": experiment_id,
                        "status": "FAILED",
                        "runner_error": f"{type(exc).__name__}: {exc}",
                    }
        return [results[item] for item in identifiers]

    @staticmethod
    def _experiment_environment() -> dict[str, str]:
        allowed = {
            "COMSPEC",
            "HOME",
            "LANG",
            "LC_ALL",
            "LOCALAPPDATA",
            "PATH",
            "PATHEXT",
            "PROGRAMDATA",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "SYSTEMDRIVE",
            "SYSTEMROOT",
            "TEMP",
            "TMP",
            "TMPDIR",
            "USERPROFILE",
            "WINDIR",
        }
        return {key: value for key, value in os.environ.items() if key.upper() in allowed}

    def _validate_command(self, command: tuple[str, ...]) -> None:
        executable = Path(command[0]).name.lower()
        if executable not in self.allowed_executables:
            raise RunnerError(
                f"executable not allowed: {command[0]!r}; "
                "use --allow-executable for trusted local tools"
            )

    @staticmethod
    def _effective_command(command: tuple[str, ...]) -> tuple[str, ...]:
        if Path(command[0]).name.lower() in {"python", "python.exe"}:
            return (sys.executable, *command[1:])
        return command

    @staticmethod
    def _verify_inputs(case_dir: Path, manifest: ExperimentManifest) -> None:
        for item in manifest.inputs:
            path = resolve_within(case_dir, item["path"], "manifest input")
            if not path.exists():
                raise RunnerError(f"pinned input is missing: {item['path']}")
            actual = hash_path(path)
            if actual != item["sha256"]:
                raise RunnerError(
                    f"pinned input changed: {item['path']}; "
                    "create a new experiment manifest"
                )

    @staticmethod
    def _next_attempt(experiment_dir: Path) -> int:
        attempts = []
        for path in (experiment_dir / "runs").glob("run-*"):
            try:
                attempts.append(int(path.name.removeprefix("run-")))
            except ValueError:
                continue
        return max(attempts, default=0) + 1

    @staticmethod
    def _clear_outputs(experiment_dir: Path, outputs: tuple[str, ...]) -> None:
        for index, value in enumerate(outputs):
            path = resolve_within(experiment_dir, value, f"expected_outputs[{index}]")
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
            path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _collect_outputs(
        experiment_dir: Path, outputs: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for index, value in enumerate(outputs):
            path = resolve_within(experiment_dir, value, f"expected_outputs[{index}]")
            record: dict[str, Any] = {
                "path": value,
                "exists": path.exists(),
                "kind": "directory" if path.is_dir() else "file",
                "sha256": hash_path(path) if path.exists() else None,
            }
            if path.is_file():
                record["size_bytes"] = path.stat().st_size
            records.append(record)
        return records
