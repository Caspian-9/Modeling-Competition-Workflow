from __future__ import annotations

from typing import Any

from .storage import CaseRepository


def build_status(repository: CaseRepository, case_id: str) -> dict[str, Any]:
    config = repository.load_case(case_id)
    case_dir = repository.case_dir(config.case_id)
    inventory_path = case_dir / "workspace" / "raw_inventory.json"
    inventory = (
        repository.read_json(inventory_path) if inventory_path.is_file() else None
    )
    questions: list[dict[str, Any]] = []
    for question_id in config.questions:
        selection_path = case_dir / "questions" / question_id / "selection.json"
        selection = (
            repository.read_json(selection_path) if selection_path.is_file() else None
        )
        experiments = [
            {
                "experiment_id": item.experiment_id,
                "title": item.title,
                "status": item.status,
                "qc": (item.qc or {}).get("decision"),
                "latest_run": item.latest_run,
            }
            for item in repository.iter_manifests(config.case_id, question_id)
        ]
        questions.append(
            {
                "question_id": question_id,
                "experiments": experiments,
                "selected_experiment": (
                    selection.get("current") if isinstance(selection, dict) else None
                ),
                "analysis_path": f"questions/{question_id}/analysis.md",
            }
        )
    manuscript = case_dir / "paper" / "manuscript.md"
    progress = case_dir / "workspace" / "progress.md"
    return {
        "schema_version": "fast-1.0",
        "case": config.to_dict(),
        "raw_ready": bool(isinstance(inventory, dict) and inventory.get("ready")),
        "raw_errors": inventory.get("errors", []) if isinstance(inventory, dict) else [],
        "raw_data_files": (
            inventory.get("data_files", []) if isinstance(inventory, dict) else []
        ),
        "derived_csv_files": (
            inventory.get("derived_csv_files", [])
            if isinstance(inventory, dict)
            else []
        ),
        "questions": questions,
        "paper": {
            "manuscript_path": "paper/manuscript.md",
            "manuscript_bytes": manuscript.stat().st_size if manuscript.is_file() else 0,
        },
        "progress_path": "workspace/progress.md" if progress.is_file() else None,
        "legacy_layout_detected": (case_dir / "state" / "case_state.json").is_file(),
    }
