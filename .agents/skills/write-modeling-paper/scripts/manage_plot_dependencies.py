from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
FORBIDDEN_PACKAGE_MARKERS = ("://", "/", "\\", "git+", "--")
DEFAULT_PACKAGE_MAP = {
    "PIL": "pillow",
    "cv2": "opencv-python",
    "factor_analyzer": "factor-analyzer",
    "mpl_toolkits": "matplotlib",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
}


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _valid_package(package: str) -> bool:
    return bool(PACKAGE_RE.fullmatch(package)) and not any(
        marker in package for marker in FORBIDDEN_PACKAGE_MARKERS
    )


def _stdlib_names() -> set[str]:
    names = set(sys.builtin_module_names)
    names.update(getattr(sys, "stdlib_module_names", set()))
    return names


def _parse_mapping(values: list[str]) -> dict[str, str]:
    mapping = dict(DEFAULT_PACKAGE_MAP)
    for value in values:
        if "=" not in value:
            raise ValueError(f"package map must use import=package: {value}")
        import_name, package_name = value.split("=", 1)
        import_name = import_name.strip()
        package_name = package_name.strip()
        if not import_name or not package_name:
            raise ValueError(f"package map must use import=package: {value}")
        mapping[import_name] = package_name
    return mapping


def _imports_from_script(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.add(node.module.split(".", 1)[0])
    return imports


def _module_available(import_name: str, executable: str, timeout: int = 10) -> bool:
    code = (
        "import importlib.util,json,sys;"
        "print(json.dumps(importlib.util.find_spec(sys.argv[1]) is not None))"
    )
    completed = subprocess.run(
        [executable, "-c", code, import_name],
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _install_package(package: str, executable: str, timeout: int) -> dict[str, Any]:
    start = time.time()
    try:
        completed = subprocess.run(
            [executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "package": package,
            "command": [executable, "-m", "pip", "install", package],
            "return_code": None,
            "stdout": error.stdout or "",
            "stderr": error.stderr or str(error),
            "elapsed_seconds": round(time.time() - start, 4),
            "timed_out": True,
        }
    return {
        "package": package,
        "command": [executable, "-m", "pip", "install", package],
        "return_code": completed.returncode,
        "stdout": completed.stdout[-20000:],
        "stderr": completed.stderr[-20000:],
        "elapsed_seconds": round(time.time() - start, 4),
        "timed_out": False,
    }


def inspect_and_optionally_install(
    *,
    scripts: list[Path],
    dependencies: list[str],
    output_root: Path,
    report_path: Path,
    package_map: dict[str, str],
    python_executable: str,
    install: bool,
    timeout_seconds: int,
    max_install_rounds: int,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not _inside(report_path, output_root):
        issues.append(
            {
                "code": "report_outside_output_root",
                "severity": "error",
                "message": str(report_path),
            }
        )
    script_imports: set[str] = set()
    for script in scripts:
        if not _inside(script, output_root):
            issues.append(
                {
                    "code": "script_outside_output_root",
                    "severity": "error",
                    "message": str(script),
                }
            )
            continue
        if not script.is_file():
            issues.append(
                {"code": "script_not_found", "severity": "error", "message": str(script)}
            )
            continue
        try:
            script_imports.update(_imports_from_script(script))
        except (SyntaxError, OSError) as error:
            issues.append(
                {
                    "code": "script_import_scan_failed",
                    "severity": "error",
                    "message": f"{script}: {error}",
                }
            )

    stdlib = _stdlib_names()
    requested_imports = sorted(
        {name for name in script_imports.union(dependencies) if name and name not in stdlib}
    )
    records = []
    invalid_packages = []
    for import_name in requested_imports:
        package_name = package_map.get(import_name, import_name)
        valid_package = _valid_package(package_name)
        if not valid_package:
            invalid_packages.append(package_name)
        available_before = False if not valid_package else _module_available(import_name, python_executable)
        records.append(
            {
                "import_name": import_name,
                "package_name": package_name,
                "valid_package_name": valid_package,
                "available_before": available_before,
                "available_after": available_before,
                "action": "skipped_available" if available_before else "pending",
            }
        )

    if invalid_packages:
        issues.append(
            {
                "code": "invalid_package_name",
                "severity": "error",
                "message": ", ".join(sorted(set(invalid_packages))),
            }
        )

    install_results = []
    install_rounds = 0
    if install and not invalid_packages and max_install_rounds > 0:
        for _round in range(max_install_rounds):
            missing = [item for item in records if not item["available_after"]]
            if not missing:
                break
            install_rounds += 1
            for item in missing:
                result = _install_package(
                    item["package_name"], python_executable, timeout_seconds
                )
                install_results.append(result)
                item["action"] = "install_attempted"
                if result["return_code"] == 0:
                    item["available_after"] = _module_available(
                        item["import_name"], python_executable
                    )
                if not item["available_after"]:
                    item["action"] = "install_failed_or_unavailable"
        if any(not item["available_after"] for item in records):
            issues.append(
                {
                    "code": "dependency_still_missing",
                    "severity": "error",
                    "message": ", ".join(
                        item["import_name"] for item in records if not item["available_after"]
                    ),
                }
            )
    elif any(not item["available_after"] for item in records) and not invalid_packages:
        issues.append(
            {
                "code": "dependency_missing",
                "severity": "error",
                "message": ", ".join(
                    item["import_name"] for item in records if not item["available_after"]
                ),
            }
        )

    failed = any(item["severity"] == "error" for item in issues)
    return {
        "schema_version": "1.0",
        "status": "FAIL" if failed else "PASS",
        "install_enabled": install,
        "install_rounds": install_rounds,
        "max_install_rounds": max_install_rounds,
        "python_executable": python_executable,
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        },
        "scripts": [path.resolve().as_posix() for path in scripts],
        "dependencies": records,
        "install_results": install_results,
        "issues": issues,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect and optionally install render-only plotting dependencies"
    )
    parser.add_argument("--script", action="append", default=[])
    parser.add_argument("--dependency", action="append", default=[])
    parser.add_argument("--package-map", action="append", default=[])
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-install-rounds", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        package_map = _parse_mapping(args.package_map)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    output_root = Path(args.output_root).resolve()
    report_path = Path(args.report).resolve()
    report = inspect_and_optionally_install(
        scripts=[Path(path).resolve() for path in args.script],
        dependencies=args.dependency,
        output_root=output_root,
        report_path=report_path,
        package_map=package_map,
        python_executable=args.python_executable,
        install=args.install,
        timeout_seconds=args.timeout_seconds,
        max_install_rounds=max(0, min(args.max_install_rounds, 2)),
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
