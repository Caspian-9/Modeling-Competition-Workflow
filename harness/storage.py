from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .models import (
    CaseConfig,
    ExperimentManifest,
    ValidationError,
    hash_path,
    json_bytes,
    normalize_identifier,
    resolve_within,
    utc_now,
)


class CaseRepository:
    """Filesystem repository for the small, state-machine-free FAST layout."""

    def __init__(self, cases_root: str | Path = "cases") -> None:
        self.cases_root = Path(cases_root).resolve()
        self.cases_root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, case_id: str) -> Path:
        normalized = normalize_identifier(case_id, "case_id")
        return self.cases_root / normalized

    def initialize_case(
        self, case_id: str, questions: Iterable[str] | None = None
    ) -> CaseConfig:
        normalized_case = normalize_identifier(case_id, "case_id")
        questions_were_supplied = questions is not None
        if questions is None:
            questions = ("Q1", "Q2", "Q3", "Q4")
        normalized_questions = tuple(
            normalize_identifier(item, "question_id") for item in questions
        )
        case_dir = self.case_dir(normalized_case)
        case_dir.mkdir(parents=True, exist_ok=True)
        config_path = case_dir / "case.json"
        if config_path.is_file():
            config = self.load_case(normalized_case)
            if questions_were_supplied and config.questions != normalized_questions:
                raise ValidationError(
                    "case already exists with different questions: "
                    + ", ".join(config.questions)
                )
            self._ensure_layout(config)
            return config

        now = utc_now()
        config = CaseConfig(
            case_id=normalized_case,
            questions=normalized_questions,
            created_at=now,
            updated_at=now,
        )
        self._ensure_layout(config)
        self.write_json(config_path, config.to_dict())
        return config

    def load_case(self, case_id: str) -> CaseConfig:
        path = self.case_dir(case_id) / "case.json"
        if not path.is_file():
            raise ValidationError(
                f"FAST case not initialized: {normalize_identifier(case_id, 'case_id')}; "
                "run python -m harness init <CASE_ID>"
            )
        raw = self.read_json(path)
        if not isinstance(raw, dict):
            raise ValidationError("case.json must contain an object")
        return CaseConfig.from_dict(raw)

    def _ensure_layout(self, config: CaseConfig) -> None:
        case_dir = self.case_dir(config.case_id)
        for relative in (
            "raw",
            "workspace",
            "data/interim",
            "data/processed",
            "paper/figures",
            "paper/reviews",
        ):
            (case_dir / relative).mkdir(parents=True, exist_ok=True)
        self._write_if_missing(
            case_dir / "workspace" / "brief.md",
            "# 题意与总体思路\n\n由主 Agent 持续维护。\n",
        )
        self._write_if_missing(
            case_dir / "workspace" / "symbols.md",
            "# 符号表\n\n| 符号 | 含义 | 单位 | 首次出现 |\n|---|---|---|---|\n",
        )
        self._write_if_missing(
            case_dir / "workspace" / "progress.md",
            "# 项目进度\n\n- 当前状态：等待读取题面与数据\n",
        )
        self._write_if_missing(case_dir / "paper" / "manuscript.md", "# 论文正文\n")
        self._write_if_missing(case_dir / "paper" / "references.md", "# 参考文献\n")
        for question in config.questions:
            question_dir = case_dir / "questions" / question
            for relative in ("research", "experiments", "figures"):
                (question_dir / relative).mkdir(parents=True, exist_ok=True)
            self._write_if_missing(
                question_dir / "analysis.md",
                f"# {question} 分析\n\n由主 Agent 记录问题理解、模型选择、结果解释和结论。\n",
            )

    @staticmethod
    def _write_if_missing(path: Path, content: str) -> None:
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    def validate_question(self, case_id: str, question_id: str) -> tuple[CaseConfig, str]:
        config = self.load_case(case_id)
        question = normalize_identifier(question_id, "question_id")
        if question not in config.questions:
            raise ValidationError(
                f"unknown question {question!r}; configured: {', '.join(config.questions)}"
            )
        return config, question

    def experiment_dir(
        self, case_id: str, question_id: str, experiment_id: str
    ) -> Path:
        config, question = self.validate_question(case_id, question_id)
        experiment = normalize_identifier(experiment_id, "experiment_id")
        return (
            self.case_dir(config.case_id)
            / "questions"
            / question
            / "experiments"
            / experiment
        )

    def create_experiment(
        self,
        case_id: str,
        question_id: str,
        experiment_id: str,
        *,
        title: str,
        objective: str,
        command: tuple[str, ...],
        seed: int,
        inputs: tuple[str, ...],
        expected_outputs: tuple[str, ...],
        notes: str = "",
    ) -> ExperimentManifest:
        config, question = self.validate_question(case_id, question_id)
        experiment = normalize_identifier(experiment_id, "experiment_id")
        directory = self.experiment_dir(config.case_id, question, experiment)
        manifest_path = directory / "experiment.json"
        if manifest_path.exists():
            raise ValidationError(f"experiment already exists: {experiment}")
        case_dir = self.case_dir(config.case_id)
        pinned_inputs: list[dict[str, Any]] = []
        for index, value in enumerate(inputs):
            path = resolve_within(case_dir, value, f"input[{index}]")
            if not path.exists():
                raise ValidationError(f"input does not exist: {value}")
            pinned_inputs.append(
                {
                    "path": path.relative_to(case_dir).as_posix(),
                    "sha256": hash_path(path),
                }
            )
        directory.mkdir(parents=True, exist_ok=False)
        for relative in ("code", "outputs", "runs"):
            (directory / relative).mkdir()
        now = utc_now()
        manifest = ExperimentManifest(
            case_id=config.case_id,
            question_id=question,
            experiment_id=experiment,
            title=title,
            objective=objective,
            command=command,
            seed=seed,
            inputs=tuple(pinned_inputs),
            expected_outputs=expected_outputs,
            created_at=now,
            updated_at=now,
            notes=notes,
        )
        self.write_manifest(manifest)
        return manifest

    def load_manifest(
        self, case_id: str, question_id: str, experiment_id: str
    ) -> ExperimentManifest:
        path = self.experiment_dir(case_id, question_id, experiment_id) / "experiment.json"
        if not path.is_file():
            raise ValidationError(f"experiment not found: {experiment_id}")
        raw = self.read_json(path)
        if not isinstance(raw, dict):
            raise ValidationError("experiment.json must contain an object")
        return ExperimentManifest.from_dict(raw)

    def write_manifest(self, manifest: ExperimentManifest) -> None:
        manifest.updated_at = utc_now()
        path = (
            self.experiment_dir(
                manifest.case_id, manifest.question_id, manifest.experiment_id
            )
            / "experiment.json"
        )
        self.write_json(path, manifest.to_dict())

    def iter_manifests(
        self, case_id: str, question_id: str
    ) -> tuple[ExperimentManifest, ...]:
        _, question = self.validate_question(case_id, question_id)
        root = self.case_dir(case_id) / "questions" / question / "experiments"
        result: list[ExperimentManifest] = []
        if not root.is_dir():
            return ()
        for path in sorted(root.glob("*/experiment.json")):
            try:
                raw = self.read_json(path)
                if isinstance(raw, dict) and raw.get("schema_version") == "fast-1.0":
                    result.append(ExperimentManifest.from_dict(raw))
            except (OSError, json.JSONDecodeError, ValidationError):
                continue
        return tuple(result)

    @staticmethod
    def read_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"cannot read JSON {path}: {exc}") from exc

    @staticmethod
    def write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json_bytes(data)
        fd, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary_path = Path(temporary)
            if temporary_path.exists():
                temporary_path.unlink()
