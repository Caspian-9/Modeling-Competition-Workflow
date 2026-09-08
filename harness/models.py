from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


class ValidationError(ValueError):
    """Raised when a FAST Harness input violates a deterministic contract."""


IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
UNICODE_DASHES = str.maketrans({"—": "-", "–": "-", "－": "-", "−": "-"})
EXPERIMENT_STATUSES = frozenset({"CREATED", "RUNNING", "SUCCEEDED", "FAILED"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_identifier(value: str, field_name: str = "identifier") -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")
    normalized = re.sub(r"\s+", "-", value.translate(UNICODE_DASHES).strip())
    if not IDENTIFIER_RE.fullmatch(normalized):
        raise ValidationError(
            f"unsafe {field_name}: {value!r}; use letters, digits, '.', '_' or '-'"
        )
    return normalized


def relative_path(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty relative path")
    path = Path(value.replace("\\", "/"))
    if path.is_absolute() or path.drive or ".." in path.parts:
        raise ValidationError(f"unsafe {field_name}: {value!r}")
    return path.as_posix()


def resolve_within(root: Path, value: str, field_name: str) -> Path:
    relative = relative_path(value, field_name)
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValidationError(f"{field_name} escapes its workspace: {value!r}")
    return resolved


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_path(path: Path, *, ignore_transient: bool = False) -> str:
    if path.is_file():
        return hash_file(path)
    if not path.is_dir():
        raise ValidationError(f"cannot hash missing path: {path}")
    digest = hashlib.sha256()
    children = (item for item in path.rglob("*") if item.is_file())
    if ignore_transient:
        children = (
            item
            for item in children
            if "__pycache__" not in item.parts and item.suffix.lower() not in {".pyc", ".pyo"}
        )
    for child in sorted(children):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hash_file(child).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def json_bytes(data: Any) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


@dataclass(frozen=True)
class CaseConfig:
    case_id: str
    questions: tuple[str, ...]
    created_at: str
    updated_at: str
    schema_version: str = "fast-1.0"

    def __post_init__(self) -> None:
        if self.schema_version != "fast-1.0":
            raise ValidationError("unsupported case schema_version")
        if normalize_identifier(self.case_id, "case_id") != self.case_id:
            raise ValidationError("case_id must already be normalized")
        if not self.questions:
            raise ValidationError("questions must not be empty")
        if len(set(self.questions)) != len(self.questions):
            raise ValidationError("questions must be unique")
        for question in self.questions:
            if normalize_identifier(question, "question_id") != question:
                raise ValidationError("question IDs must already be normalized")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["questions"] = list(self.questions)
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CaseConfig":
        try:
            return cls(
                schema_version=str(raw["schema_version"]),
                case_id=str(raw["case_id"]),
                questions=tuple(str(item) for item in raw["questions"]),
                created_at=str(raw["created_at"]),
                updated_at=str(raw["updated_at"]),
            )
        except (KeyError, TypeError) as exc:
            raise ValidationError(f"invalid case.json: {exc}") from exc


@dataclass
class ExperimentManifest:
    case_id: str
    question_id: str
    experiment_id: str
    title: str
    objective: str
    command: tuple[str, ...]
    seed: int
    inputs: tuple[dict[str, Any], ...]
    expected_outputs: tuple[str, ...]
    created_at: str
    updated_at: str
    status: str = "CREATED"
    latest_run: str | None = None
    qc: dict[str, Any] | None = None
    notes: str = ""
    schema_version: str = "fast-1.0"

    def __post_init__(self) -> None:
        if self.schema_version != "fast-1.0":
            raise ValidationError("unsupported experiment schema_version")
        for name, value in (
            ("case_id", self.case_id),
            ("question_id", self.question_id),
            ("experiment_id", self.experiment_id),
        ):
            if normalize_identifier(value, name) != value:
                raise ValidationError(f"{name} must already be normalized")
        if not self.title.strip() or not self.objective.strip():
            raise ValidationError("title and objective must not be empty")
        if not self.command or any(not str(item) for item in self.command):
            raise ValidationError("command must not be empty")
        if not isinstance(self.seed, int):
            raise ValidationError("seed must be an integer")
        if self.status not in EXPERIMENT_STATUSES:
            raise ValidationError(f"invalid experiment status: {self.status}")
        if len(set(self.expected_outputs)) != len(self.expected_outputs):
            raise ValidationError("expected_outputs must be unique")
        for index, item in enumerate(self.inputs):
            if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
                raise ValidationError(f"inputs[{index}] must contain path and sha256")
            relative_path(str(item["path"]), f"inputs[{index}].path")
            if not re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"])):
                raise ValidationError(f"inputs[{index}].sha256 must be SHA-256")
        for index, output in enumerate(self.expected_outputs):
            normalized = relative_path(output, f"expected_outputs[{index}]")
            if Path(normalized).parts[0] != "outputs" or normalized == "outputs":
                raise ValidationError(
                    f"expected_outputs[{index}] must be below the outputs/ directory"
                )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["command"] = list(self.command)
        data["inputs"] = [dict(item) for item in self.inputs]
        data["expected_outputs"] = list(self.expected_outputs)
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ExperimentManifest":
        try:
            return cls(
                schema_version=str(raw["schema_version"]),
                case_id=str(raw["case_id"]),
                question_id=str(raw["question_id"]),
                experiment_id=str(raw["experiment_id"]),
                title=str(raw["title"]),
                objective=str(raw["objective"]),
                command=tuple(str(item) for item in raw["command"]),
                seed=int(raw["seed"]),
                inputs=tuple(dict(item) for item in raw.get("inputs", [])),
                expected_outputs=tuple(
                    str(item) for item in raw.get("expected_outputs", [])
                ),
                created_at=str(raw["created_at"]),
                updated_at=str(raw["updated_at"]),
                status=str(raw.get("status", "CREATED")),
                latest_run=(
                    str(raw["latest_run"]) if raw.get("latest_run") is not None else None
                ),
                qc=dict(raw["qc"]) if isinstance(raw.get("qc"), dict) else None,
                notes=str(raw.get("notes", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"invalid experiment.json: {exc}") from exc


def aggregate_hash(entries: Sequence[tuple[str, str]]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(entries):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()
