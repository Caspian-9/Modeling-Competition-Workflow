from __future__ import annotations

from typing import Any

from .models import ValidationError, utc_now
from .storage import CaseRepository


def select_experiment(
    repository: CaseRepository,
    case_id: str,
    question_id: str,
    experiment_id: str,
    *,
    reason: str,
    force: bool = False,
) -> dict[str, Any]:
    if not reason.strip():
        raise ValidationError("selection reason must not be empty")
    from .qc import DeterministicQC

    report = DeterministicQC(repository).run(case_id, question_id, experiment_id)
    manifest = repository.load_manifest(case_id, question_id, experiment_id)
    qc_decision = report["decision"]
    if qc_decision != "PASS" and not force:
        raise ValidationError(
            "selection requires deterministic QC PASS; use --force to record an "
            "explicit user decision without changing the QC result"
        )
    question_dir = (
        repository.case_dir(manifest.case_id)
        / "questions"
        / manifest.question_id
    )
    path = question_dir / "selection.json"
    history: list[dict[str, Any]] = []
    if path.is_file():
        previous = repository.read_json(path)
        if (
            isinstance(previous, dict)
            and previous.get("schema_version") == "fast-1.0"
            and isinstance(previous.get("history"), list)
        ):
            history = [dict(item) for item in previous["history"] if isinstance(item, dict)]
    record = {
        "experiment_id": manifest.experiment_id,
        "selected_at": utc_now(),
        "reason": reason.strip(),
        "forced": force,
        "experiment_status": manifest.status,
        "deterministic_qc": qc_decision,
    }
    history.append(record)
    selection = {
        "schema_version": "fast-1.0",
        "case_id": manifest.case_id,
        "question_id": manifest.question_id,
        "current": record,
        "history": history,
    }
    repository.write_json(path, selection)
    return selection
