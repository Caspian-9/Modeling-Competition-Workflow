from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


FORBIDDEN_TEXT = ("pip install", "git+", "shell=True", "sudo ")
FORBIDDEN_IMPORTS = {"requests", "urllib"}
SUPPORTED_OUTPUT_SUFFIXES = {".pdf", ".png", ".svg"}


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _file_snapshot(root: Path) -> dict[Path, tuple[int, int]]:
    if not root.exists():
        return {}
    return {
        path.resolve(): (path.stat().st_mtime_ns, path.stat().st_size)
        for path in root.rglob("*")
        if path.is_file()
    }


def _scan_script(path: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    text = path.read_text(encoding="utf-8")
    lower_text = text.lower()
    for marker in FORBIDDEN_TEXT:
        if marker.lower() in lower_text:
            issues.append(
                {
                    "code": "forbidden_script_text",
                    "severity": "error",
                    "message": marker,
                }
            )
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as error:
        return [
            {
                "code": "script_syntax_error",
                "severity": "error",
                "message": str(error),
            }
        ]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".", 1)[0]
                if top in FORBIDDEN_IMPORTS or top == "subprocess":
                    issues.append(
                        {
                            "code": "forbidden_import",
                            "severity": "error",
                            "message": top,
                        }
                    )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top = node.module.split(".", 1)[0]
            if top in FORBIDDEN_IMPORTS or top == "subprocess":
                issues.append(
                    {"code": "forbidden_import", "severity": "error", "message": top}
                )
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "system"
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            ):
                issues.append(
                    {
                        "code": "forbidden_os_system",
                        "severity": "error",
                        "message": "os.system",
                    }
                )
    return issues


def execute_plot_script(
    *,
    script: Path,
    data: Path,
    output_dir: Path,
    output_root: Path,
    report_path: Path,
    python_executable: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    for path, code in (
        (script, "script_outside_output_root"),
        (output_dir, "output_dir_outside_output_root"),
        (report_path, "report_outside_output_root"),
    ):
        if not _inside(path, output_root):
            issues.append({"code": code, "severity": "error", "message": str(path)})
    if not script.is_file():
        issues.append({"code": "script_not_found", "severity": "error", "message": str(script)})
    if script.is_symlink():
        issues.append({"code": "symlink_script", "severity": "error", "message": str(script)})
    if not data.is_file():
        issues.append({"code": "data_not_found", "severity": "error", "message": str(data)})
    if data.is_symlink():
        issues.append({"code": "symlink_data", "severity": "error", "message": str(data)})
    if script.is_file():
        issues.extend(_scan_script(script))
    if any(item["severity"] == "error" for item in issues):
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "issues": issues,
            "generated_files": [],
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    before = _file_snapshot(output_dir)
    env = os.environ.copy()
    env["DATA_PATH"] = str(data.resolve())
    env["OUTPUT_DIR"] = str(output_dir.resolve())
    command = [
        python_executable,
        str(script.resolve()),
        str(data.resolve()),
        str(output_dir.resolve()),
    ]
    start = time.time()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
            env=env,
            cwd=str(script.parent.resolve()),
        )
        return_code = completed.returncode
        stdout = completed.stdout[-20000:]
        stderr = completed.stderr[-20000:]
        timed_out = False
    except subprocess.TimeoutExpired as error:
        return_code = None
        stdout = error.stdout or ""
        stderr = error.stderr or str(error)
        timed_out = True

    generated = []
    after = _file_snapshot(output_dir)
    for path, stat in after.items():
        if before.get(path) == stat:
            continue
        if path.suffix.lower() not in SUPPORTED_OUTPUT_SUFFIXES:
            issues.append(
                {
                    "code": "unsupported_generated_format",
                    "severity": "warning",
                    "message": str(path),
                }
            )
        generated.append(
            {
                "path": path.as_posix(),
                "sha256": _digest(path),
                "size_bytes": path.stat().st_size,
                "format": path.suffix.lower().lstrip("."),
            }
        )
    if timed_out:
        issues.append({"code": "script_timeout", "severity": "error", "message": stderr})
    if return_code != 0:
        issues.append(
            {
                "code": "script_failed",
                "severity": "error",
                "message": f"return_code={return_code}",
            }
        )
    if not generated:
        issues.append({"code": "no_generated_files", "severity": "error", "message": str(output_dir)})
    failed = any(item["severity"] == "error" for item in issues)
    return {
        "schema_version": "1.0",
        "status": "FAIL" if failed else "PASS",
        "command": command,
        "shell": False,
        "python_executable": python_executable,
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        },
        "script": script.resolve().as_posix(),
        "script_sha256": _digest(script),
        "data": data.resolve().as_posix(),
        "data_sha256": _digest(data),
        "output_dir": output_dir.resolve().as_posix(),
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
        "elapsed_seconds": round(time.time() - start, 4),
        "generated_files": generated,
        "issues": issues,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a Writer plotting script reproducibly")
    parser.add_argument("--script", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report_path = Path(args.report).resolve()
    output_root = Path(args.output_root).resolve()
    report = execute_plot_script(
        script=Path(args.script).resolve(),
        data=Path(args.data).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        output_root=output_root,
        report_path=report_path,
        python_executable=args.python_executable,
        timeout_seconds=args.timeout_seconds,
    )
    if not _inside(report_path, output_root):
        print("report path must stay inside output root", file=sys.stderr)
        return 2
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "report": report_path.as_posix()}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
