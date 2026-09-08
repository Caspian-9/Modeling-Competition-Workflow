from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import ValidationError, hash_path, resolve_within, utc_now
from .storage import CaseRepository


class DeterministicQC:
    """Check reproducibility plumbing only; this is not a semantic model review."""

    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository

    def run(
        self, case_id: str, question_id: str, experiment_id: str
    ) -> dict[str, Any]:
        manifest = self.repository.load_manifest(case_id, question_id, experiment_id)
        experiment_dir = self.repository.experiment_dir(
            manifest.case_id, manifest.question_id, manifest.experiment_id
        )
        checks: list[dict[str, Any]] = []
        run = self._load_latest_run(experiment_dir, manifest.latest_run)

        self._check(
            checks,
            "execution",
            run is not None
            and run.get("status") == "SUCCEEDED"
            and run.get("exit_code") == 0
            and run.get("timed_out") is False,
            "最近一次命令成功且未超时",
        )
        self._check(
            checks,
            "identity",
            run is not None
            and run.get("case_id") == manifest.case_id
            and run.get("question_id") == manifest.question_id
            and run.get("experiment_id") == manifest.experiment_id,
            "run 与 experiment identity 一致",
        )
        self._check(
            checks,
            "reproducibility_metadata",
            run is not None
            and run.get("seed") == manifest.seed
            and isinstance(run.get("command"), list)
            and bool(run.get("code_sha256_before")),
            "命令、seed 和代码 hash 已记录",
        )

        case_dir = self.repository.case_dir(manifest.case_id)
        inputs_ok = True
        input_details: list[str] = []
        for item in manifest.inputs:
            path = resolve_within(case_dir, item["path"], "manifest input")
            actual = hash_path(path) if path.exists() else None
            if actual != item["sha256"]:
                inputs_ok = False
                input_details.append(item["path"])
        self._check(
            checks,
            "input_integrity",
            inputs_ok,
            "输入 hash 与 manifest 一致"
            if inputs_ok
            else "输入已缺失或变化：" + "、".join(input_details),
        )

        current_code = hash_path(experiment_dir / "code", ignore_transient=True)
        code_ok = (
            run is not None
            and run.get("code_sha256_before") == run.get("code_sha256_after")
            and run.get("code_sha256_after") == current_code
        )
        self._check(
            checks,
            "code_integrity",
            code_ok,
            "运行前后及当前代码 hash 一致",
        )

        run_outputs = {
            item.get("path"): item
            for item in (run or {}).get("outputs", [])
            if isinstance(item, dict)
        }
        outputs_ok = True
        output_details: list[str] = []
        for index, value in enumerate(manifest.expected_outputs):
            path = resolve_within(
                experiment_dir, value, f"expected_outputs[{index}]"
            )
            recorded = run_outputs.get(value)
            actual = hash_path(path) if path.exists() else None
            if (
                not path.exists()
                or not isinstance(recorded, dict)
                or recorded.get("exists") is not True
                or recorded.get("sha256") != actual
            ):
                outputs_ok = False
                output_details.append(value)
        self._check(
            checks,
            "output_integrity",
            outputs_ok,
            "声明输出存在且 hash 未变化"
            if outputs_ok
            else "输出缺失或变化：" + "、".join(output_details),
        )

        decision = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
        report = {
            "schema_version": "fast-1.0",
            "case_id": manifest.case_id,
            "question_id": manifest.question_id,
            "experiment_id": manifest.experiment_id,
            "checked_at": utc_now(),
            "decision": decision,
            "scope": "deterministic_integrity_only",
            "semantic_reviewed": False,
            "checks": checks,
        }
        self.repository.write_json(experiment_dir / "qc.json", report)
        manifest.qc = {
            "decision": decision,
            "path": "qc.json",
            "checked_at": report["checked_at"],
        }
        self.repository.write_manifest(manifest)
        return report

    @staticmethod
    def _load_latest_run(
        experiment_dir: Path, latest_run: str | None
    ) -> dict[str, Any] | None:
        if not latest_run:
            return None
        path = resolve_within(experiment_dir, latest_run, "latest_run")
        if not path.is_file():
            return None
        raw = CaseRepository.read_json(path)
        if not isinstance(raw, dict):
            raise ValidationError("run.json must contain an object")
        return raw

    @staticmethod
    def _check(
        checks: list[dict[str, Any]], check_id: str, passed: bool, message: str
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "PASS" if passed else "FAIL",
                "message": message,
            }
        )
