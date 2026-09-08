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
    raw_ready = bool(isinstance(inventory, dict) and inventory.get("ready"))
    return {
        "schema_version": "fast-1.0",
        "case": config.to_dict(),
        "raw_ready": raw_ready,
        "raw_errors": inventory.get("errors", []) if isinstance(inventory, dict) else [],
        "raw_data_files": (
            inventory.get("data_files", []) if isinstance(inventory, dict) else []
        ),
        "derived_csv_files": (
            inventory.get("derived_csv_files", [])
            if isinstance(inventory, dict)
            else []
        ),
        "initialization": _build_initialization_status(case_dir, raw_ready),
        "questions": questions,
        "paper": {
            "manuscript_path": "paper/manuscript.md",
            "manuscript_bytes": manuscript.stat().st_size if manuscript.is_file() else 0,
        },
        "progress_path": "workspace/progress.md" if progress.is_file() else None,
        "legacy_layout_detected": (case_dir / "state" / "case_state.json").is_file(),
    }


def _build_initialization_status(case_dir, raw_ready: bool) -> dict[str, Any]:
    initialization = case_dir / "initialization"
    paths = {
        "plan": initialization / "plan.md",
        "engineer_report": initialization / "engineer_report.md",
        "summary": initialization / "summary.md",
        "front_matter": initialization / "front_matter.md",
    }
    figure_extensions = {".svg", ".pdf", ".png", ".tif", ".tiff"}
    figure_paths = sorted(
        path
        for path in (initialization / "figures").rglob("*")
        if _has_content(path) and path.suffix.lower() in figure_extensions
    )
    missing: list[str] = []
    if not _has_content(paths["plan"]):
        missing.append("initialization/plan.md")
    if not _has_content(paths["engineer_report"]):
        missing.append("initialization/engineer_report.md")
    if not _has_content(paths["summary"]):
        missing.append("initialization/summary.md")
    if not figure_paths:
        missing.append("initialization/figures/<EDA figure>")
    if not _has_content(paths["front_matter"]):
        missing.append("initialization/front_matter.md")

    if not raw_ready:
        status = "WAITING_FOR_RAW"
    elif not _has_content(paths["plan"]):
        status = "NOT_STARTED"
    elif not _has_content(paths["engineer_report"]):
        status = "ENGINEERING"
    elif not _has_content(paths["summary"]):
        status = "SYNTHESIS"
    elif not figure_paths:
        status = "FIGURES"
    elif not _has_content(paths["front_matter"]):
        status = "WRITING"
    else:
        status = "READY_FOR_Q1"

    return {
        "status": status,
        "plan_path": "initialization/plan.md",
        "engineer_report_path": "initialization/engineer_report.md",
        "summary_path": "initialization/summary.md",
        "front_matter_path": "initialization/front_matter.md",
        "figure_paths": [
            path.relative_to(case_dir).as_posix() for path in figure_paths
        ],
        "missing": missing,
        "user_review_required": status == "READY_FOR_Q1",
    }


def _has_content(path) -> bool:
    return path.is_file() and path.stat().st_size > 0
