from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml


CJK_RE = re.compile(r"[\u4e00-\u9fff]")
QUESTION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
DEFAULT_DEPENDENCY_ALIASES = {
    "pillow": "PIL",
    "pyyaml": "yaml",
    "scikit-learn": "sklearn",
    "opencv-python": "cv2",
}
VISUAL_METHODS = {
    "title",
    "suptitle",
    "set_title",
    "xlabel",
    "ylabel",
    "set_xlabel",
    "set_ylabel",
    "figtext",
    "text",
    "annotate",
}
VISUAL_KEYWORDS = {
    "label",
    "title",
    "xlabel",
    "ylabel",
}
PLAN_TEXT_FIELDS = {
    "plot_goal",
    "title_plan",
    "axis_plan",
    "legend_plan",
    "annotation_plan",
}
DEFAULT_ALLOWED_VISUAL_TOKENS = {
    "%",
    "BMI",
    "GC",
    "NIPT",
    "DNA",
    "Y",
    "X",
    "Z",
    "PCA",
    "SHAP",
    "AUC",
    "RMSE",
    "MAE",
    "R2",
    "R^2",
    "p",
    "n",
    "N",
}


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _literal_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        return "".join(parts)
    return None


def _looks_like_nonvisual_token(text: str, allowed_tokens: set[str]) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in allowed_tokens:
        return True
    if re.fullmatch(r"[\s\d.,:;+\-*/=(){}\[\]_%<>]+", stripped):
        return True
    if re.fullmatch(r"[A-Z](?:\d+)?", stripped):
        return True
    return False


def _extract_visual_strings(code: str) -> list[dict[str, Any]]:
    tree = ast.parse(code)
    strings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in VISUAL_METHODS:
            positional_indexes: tuple[int, ...]
            if name in {"text", "figtext"}:
                positional_indexes = (2,)
            else:
                positional_indexes = (0,)
            for index in positional_indexes:
                if index < len(node.args):
                    text = _literal_text(node.args[index])
                    if text is not None:
                        strings.append(
                            {
                                "text": text,
                                "source": f"{name} positional argument {index}",
                                "line": getattr(node, "lineno", None),
                            }
                        )
        for keyword in node.keywords:
            if keyword.arg in VISUAL_KEYWORDS:
                text = _literal_text(keyword.value)
                if text is not None:
                    strings.append(
                        {
                            "text": text,
                            "source": f"{name} keyword {keyword.arg}",
                            "line": getattr(keyword.value, "lineno", getattr(node, "lineno", None)),
                        }
                    )
    return strings


def _collect_plan_texts(plan: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for field in PLAN_TEXT_FIELDS:
        value = plan.get(field)
        if isinstance(value, str) and value.strip():
            records.append({"text": value, "source": f"adaptation_plan.{field}", "line": None})
    for item in plan.get("column_mappings", []):
        if isinstance(item, dict):
            role = item.get("template_role")
            if isinstance(role, str) and role.strip():
                records.append(
                    {
                        "text": role,
                        "source": f"adaptation_plan.column_mappings[{item.get('data_column', '?')}].template_role",
                        "line": None,
                    }
                )
    return records


def validate_chinese_visual_annotations(
    *,
    plan: dict[str, Any],
    adaptation: dict[str, Any],
    allowed_tokens: set[str] | None = None,
) -> dict[str, Any]:
    allowed = set(DEFAULT_ALLOWED_VISUAL_TOKENS)
    allowed.update(allowed_tokens or set())
    issues: list[dict[str, Any]] = []
    code = str(adaptation.get("adapted_code", ""))
    try:
        visual_strings = _extract_visual_strings(code)
    except SyntaxError as error:
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "checked_strings": [],
            "issues": [
                {
                    "code": "adapted_code_syntax_error",
                    "severity": "error",
                    "message": str(error),
                }
            ],
        }
    checked = _collect_plan_texts(plan) + visual_strings
    for item in checked:
        text = str(item["text"])
        if _looks_like_nonvisual_token(text, allowed):
            continue
        if not CJK_RE.search(text):
            issues.append(
                {
                    "code": "non_chinese_visual_annotation",
                    "severity": "error",
                    "message": text,
                    "source": item["source"],
                    "line": item["line"],
                }
            )
    return {
        "schema_version": "1.0",
        "status": "FAIL" if issues else "PASS",
        "policy": "All visible chart annotations must be Chinese; approved symbols/units are allowed.",
        "checked_strings": checked,
        "allowed_tokens": sorted(allowed),
        "issues": issues,
    }


def validate_question_id(question_id: str) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not QUESTION_ID_RE.fullmatch(question_id):
        issues.append(
            {
                "code": "invalid_question_id",
                "severity": "error",
                "message": "question-id must identify one question and contain only ASCII letters, digits, '_' or '-'.",
            }
        )
    if "," in question_id or "+" in question_id:
        issues.append(
            {
                "code": "multiple_question_id",
                "severity": "error",
                "message": "modelviz_adapter runs one question at a time.",
            }
        )
    return {"status": "FAIL" if issues else "PASS", "issues": issues}


def build_absolute_catalog(
    *,
    modelviz_root: Path,
    output_path: Path,
    dependency_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    catalog_path = modelviz_root / "docs" / "template_catalog.yaml"
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    aliases = dict(DEFAULT_DEPENDENCY_ALIASES)
    aliases.update(dependency_aliases or {})
    for item in data.get("templates", []):
        for key in ("code_path", "preview"):
            value = item.get(key)
            if value and not Path(value).is_absolute():
                item[key] = str((modelviz_root / value).resolve())
        item["dependencies"] = [
            aliases.get(str(dep).lower(), dep) for dep in item.get("dependencies", [])
        ]
    _write_json(output_path, data)
    return {
        "schema_version": "1.0",
        "source_catalog": str(catalog_path.resolve()),
        "source_catalog_sha256": _digest(catalog_path),
        "absolute_catalog": str(output_path.resolve()),
        "template_count": len(data.get("templates", [])),
        "dependency_aliases": aliases,
    }


def _load_writer_validator():
    validator_path = Path(__file__).resolve().with_name("validate_figure.py")
    spec = importlib.util.spec_from_file_location("writer_validate_figure", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load validator: {validator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_figure


def _prepare_run_dirs(output_root: Path, question_id: str) -> dict[str, Path]:
    run_root = output_root / "modelviz" / question_id
    workspace = run_root / "workspace"
    outputs = run_root / "outputs"
    quality = output_root / "quality" / "modelviz" / question_id
    for directory in (run_root, workspace, outputs, quality):
        directory.mkdir(parents=True, exist_ok=True)
    if outputs.exists():
        for path in outputs.iterdir():
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
    return {"run_root": run_root, "workspace": workspace, "outputs": outputs, "quality": quality}


def _prepare_recall_dirs(output_root: Path, question_id: str) -> dict[str, Path]:
    run_root = output_root / "modelviz_recall" / question_id
    workspace = run_root / "workspace"
    quality = output_root / "quality" / "modelviz_recall" / question_id
    for directory in (run_root, workspace, quality):
        directory.mkdir(parents=True, exist_ok=True)
    return {"run_root": run_root, "workspace": workspace, "quality": quality}


def build_recall_only_report(
    *,
    question_id: str,
    requirement: dict[str, Any],
    candidate_result: dict[str, Any],
    catalog: dict[str, Any],
    catalog_info: dict[str, Any],
) -> dict[str, Any]:
    catalog_by_id = {
        str(item.get("id")): item
        for item in catalog.get("templates", [])
        if isinstance(item, dict) and item.get("id")
    }
    candidates: list[dict[str, Any]] = []
    for candidate in candidate_result.get("candidates", []):
        candidate_id = str(candidate.get("template_id", ""))
        entry = catalog_by_id.get(candidate_id, {})
        code_path = Path(str(entry.get("code_path", "")))
        preview_path = Path(str(entry.get("preview", "")))
        candidates.append(
            {
                "candidate_id": candidate_id,
                "name": str(candidate.get("template_name", "")),
                "category": str(candidate.get("category", "")),
                "chart_type": str(entry.get("chart_type", "")),
                "score": float(candidate.get("score", 0.0)),
                "matched_chart_types": list(candidate.get("matched_chart_types", [])),
                "matched_keywords": list(candidate.get("matched_keywords", [])),
                "matched_use_cases": list(candidate.get("matched_use_cases", [])),
                "matched_styles": list(candidate.get("matched_styles", [])),
                "penalties": list(candidate.get("penalties", [])),
                "candidate_reason": str(candidate.get("candidate_reason", "")),
                "catalog_entry_sha256": _canonical_digest(entry),
                "template_code_sha256": _digest(code_path) if code_path.is_file() else None,
                "preview_sha256": _digest(preview_path) if preview_path.is_file() else None,
                "license_status": "unresolved",
            }
        )
    return {
        "schema_version": "1.0",
        "status": "PASS",
        "mode": "modelviz_recall_only",
        "question_id": question_id,
        "one_question_only": True,
        "rendering_allowed": False,
        "template_adaptation_allowed": False,
        "template_code_reused": False,
        "executable_metadata_removed": True,
        "downstream_owner": "nature-figure",
        "reuse_scope": "chart_type_and_composition_cues_only",
        "requirement_sha256": _canonical_digest(requirement),
        "catalog": {
            "source_catalog_sha256": catalog_info.get("source_catalog_sha256"),
            "template_count": catalog_info.get("template_count"),
            "dependency_aliases": catalog_info.get("dependency_aliases", {}),
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
        "warnings": list(candidate_result.get("warnings", [])),
        "limitations": [
            "Candidate recall does not approve template code, preview reuse, dependencies or data transformations.",
            "Nature-Figure must independently select evidence-compatible cues and redraw in Chinese.",
            "Writer remains the only owner of source/claim checks and figure_manifest registration.",
        ],
    }


def run_modelviz_recall(args: argparse.Namespace) -> dict[str, Any]:
    output_root = Path(args.output_root).resolve()
    report_path = (
        Path(args.report).resolve()
        if args.report
        else output_root
        / "quality"
        / "modelviz_recall"
        / args.question_id
        / "recall_report.json"
    )
    question_check = validate_question_id(args.question_id)
    if question_check["status"] != "PASS":
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "validate_question_id",
            "issues": question_check["issues"],
        }
    if not _inside(report_path, output_root):
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "validate_paths",
            "issues": [{"code": "report_outside_output_root", "message": str(report_path)}],
        }
    modelviz_root = Path(args.modelviz_root).resolve()
    if not (modelviz_root / "SKILL.md").is_file():
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "validate_modelviz_root",
            "issues": [{"code": "modelviz_skill_missing", "message": str(modelviz_root)}],
        }
    requirement_path = Path(args.requirement_json).resolve()
    if not requirement_path.is_file():
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "validate_requirement",
            "issues": [{"code": "requirement_json_missing", "message": str(requirement_path)}],
        }
    requirement = _read_json(requirement_path)
    if not isinstance(requirement, dict) or not requirement.get("original_request"):
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "validate_requirement",
            "issues": [{"code": "invalid_requirement", "message": "original_request is required"}],
        }

    dirs = _prepare_recall_dirs(output_root, args.question_id)
    catalog_info = build_absolute_catalog(
        modelviz_root=modelviz_root,
        output_path=dirs["run_root"] / "template_catalog.absolute.yaml",
    )
    catalog = _read_json(Path(catalog_info["absolute_catalog"]))

    sys.path.insert(0, str(modelviz_root))
    from langchain_core.runnables import RunnableLambda
    from src.services.candidate_matching_pipeline import run_candidate_matching_pipeline
    from src.services.requirement_parser import parse_and_save_requirement

    previous_cwd = Path.cwd()
    try:
        os.chdir(dirs["run_root"])
        parse_and_save_requirement(
            requirement["original_request"],
            RunnableLambda(lambda _: requirement),
            vocabulary_path=modelviz_root / "docs" / "requirement_vocabulary.yaml",
            output_path=dirs["workspace"] / "user_requirement.json",
        )
        stage3 = run_candidate_matching_pipeline(
            requirement_path=str(dirs["workspace"] / "user_requirement.json"),
            catalog_path=str(dirs["run_root"] / "template_catalog.absolute.yaml"),
            output_path=str(dirs["workspace"] / "candidate_templates.upstream.json"),
            top_k=args.top_k,
            min_score=args.min_score,
        )
    finally:
        os.chdir(previous_cwd)
    if stage3.get("success") is not True:
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "candidate_matching",
            "upstream": stage3,
        }
    report = build_recall_only_report(
        question_id=args.question_id,
        requirement=requirement,
        candidate_result=stage3["candidate_result"],
        catalog=catalog,
        catalog_info=catalog_info,
    )
    sanitized_path = dirs["workspace"] / "modelviz_candidate_recall.json"
    _write_json(sanitized_path, report)
    for sensitive_path in (
        dirs["workspace"] / "candidate_templates.upstream.json",
        Path(catalog_info["absolute_catalog"]),
    ):
        if sensitive_path.is_file() and _inside(sensitive_path, dirs["run_root"]):
            sensitive_path.unlink()
    report["sanitized_candidate_path"] = sanitized_path.relative_to(output_root).as_posix()
    return report


def run_modelviz_adapter(args: argparse.Namespace) -> dict[str, Any]:
    output_root = Path(args.output_root).resolve()
    report_path = Path(args.report).resolve() if args.report else output_root / "quality" / "modelviz" / args.question_id / "adapter_report.json"
    question_check = validate_question_id(args.question_id)
    if question_check["status"] != "PASS":
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "validate_question_id",
            "issues": question_check["issues"],
        }
    if not _inside(report_path, output_root):
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "validate_paths",
            "issues": [
                {
                    "code": "report_outside_output_root",
                    "severity": "error",
                    "message": str(report_path),
                }
            ],
        }
    modelviz_root = Path(args.modelviz_root).resolve()
    if not (modelviz_root / "SKILL.md").is_file():
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "validate_modelviz_root",
            "issues": [
                {
                    "code": "modelviz_skill_missing",
                    "severity": "error",
                    "message": str(modelviz_root),
                }
            ],
        }
    input_paths = {
        "requirement_json": Path(args.requirement_json).resolve(),
        "selection_json": Path(args.selection_json).resolve(),
        "plan_json": Path(args.plan_json).resolve(),
        "code_json": Path(args.code_json).resolve(),
        "visual_json": Path(args.visual_json).resolve() if args.visual_json else None,
    }
    for required in (
        input_paths["requirement_json"],
        input_paths["selection_json"],
        input_paths["plan_json"],
        input_paths["code_json"],
    ):
        if not required.is_file():
            return {
                "schema_version": "1.0",
                "status": "FAIL",
                "failed_step": "validate_input_json",
                "issues": [
                    {
                        "code": "input_json_missing",
                        "severity": "error",
                        "message": str(required),
                    }
                ],
            }
    data_path = Path(args.data).resolve()
    if not data_path.is_file():
        return {
            "schema_version": "1.0",
            "status": "FAIL",
            "failed_step": "validate_data",
            "issues": [{"code": "data_not_found", "severity": "error", "message": str(data_path)}],
        }

    requirement = _read_json(input_paths["requirement_json"])
    selection = _read_json(input_paths["selection_json"])
    plan = _read_json(input_paths["plan_json"])
    adaptation = _read_json(input_paths["code_json"])
    if args.require_chinese_annotations:
        chinese = validate_chinese_visual_annotations(
            plan=plan,
            adaptation=adaptation,
            allowed_tokens=set(args.allowed_visual_token or []),
        )
        chinese_report = output_root / "quality" / "modelviz" / args.question_id / "chinese_annotation_report.json"
        _write_json(chinese_report, chinese)
        if chinese["status"] != "PASS":
            return {
                "schema_version": "1.0",
                "status": "FAIL",
                "failed_step": "validate_chinese_annotations",
                "chinese_annotation_report": str(chinese_report.resolve()),
                "issues": chinese["issues"],
            }

    dirs = _prepare_run_dirs(output_root, args.question_id)
    catalog_info = build_absolute_catalog(
        modelviz_root=modelviz_root,
        output_path=dirs["run_root"] / "template_catalog.absolute.yaml",
    )

    sys.path.insert(0, str(modelviz_root))
    from langchain_core.runnables import RunnableLambda
    from src.services.candidate_matching_pipeline import run_candidate_matching_pipeline
    from src.services.final_template_selection_pipeline import run_final_template_selection_pipeline
    from src.services.plot_quality_pipeline import run_plot_quality_pipeline
    from src.services.requirement_parser import parse_and_save_requirement
    from src.services.template_adaptation_pipeline import run_template_adaptation_pipeline

    previous_cwd = Path.cwd()
    try:
        os.chdir(dirs["run_root"])
        parse_and_save_requirement(
            requirement["original_request"],
            RunnableLambda(lambda _: requirement),
            vocabulary_path=modelviz_root / "docs" / "requirement_vocabulary.yaml",
            output_path=dirs["workspace"] / "user_requirement.json",
        )
        stage3 = run_candidate_matching_pipeline(
            requirement_path=str(dirs["workspace"] / "user_requirement.json"),
            catalog_path=str(dirs["run_root"] / "template_catalog.absolute.yaml"),
            output_path=str(dirs["workspace"] / "candidate_templates.json"),
            top_k=args.top_k,
            min_score=args.min_score,
        )
        if stage3.get("success") is not True:
            return {"schema_version": "1.0", "status": "FAIL", "failed_step": "candidate_matching", "upstream": stage3}

        stage4 = run_final_template_selection_pipeline(
            RunnableLambda(lambda _: selection),
            data_path=str(data_path),
            requirement_path=str(dirs["workspace"] / "user_requirement.json"),
            candidate_path=str(dirs["workspace"] / "candidate_templates.json"),
            output_path=str(dirs["workspace"] / "final_template_selection.json"),
            dataset_context_path=str(dirs["workspace"] / "dataset_context.json"),
            sheet_name=args.sheet_name,
            max_sample_rows=args.max_sample_rows,
        )
        if stage4.get("success") is not True:
            return {"schema_version": "1.0", "status": "FAIL", "failed_step": "final_template_selection", "upstream": stage4}

        stage5 = run_template_adaptation_pipeline(
            RunnableLambda(lambda _: plan),
            RunnableLambda(lambda _: adaptation),
            data_path=str(data_path),
            final_selection_path=str(dirs["workspace"] / "final_template_selection.json"),
            requirement_path=str(dirs["workspace"] / "user_requirement.json"),
            dataset_context_path=str(dirs["workspace"] / "dataset_context.json"),
            catalog_path=str(dirs["run_root"] / "template_catalog.absolute.yaml"),
            workspace_dir=str(dirs["workspace"]),
            outputs_dir=str(dirs["outputs"]),
            python_executable=args.python_executable,
            auto_install=args.auto_install,
            timeout_seconds=args.timeout_seconds,
        )
        if stage5.get("success") is not True:
            return {"schema_version": "1.0", "status": "FAIL", "failed_step": "template_adaptation", "upstream": stage5}

        visual = (
            _read_json(input_paths["visual_json"])
            if input_paths["visual_json"]
            else {
                "passed": False,
                "requirement_alignment": "未提供实际视觉检查结果。",
                "data_expression_quality": "",
                "style_preservation": "",
                "readability": "",
                "layout_quality": "",
                "color_quality": "",
                "issues": ["需要检查实际渲染图像。"],
                "suggested_fixes": [],
                "needs_repair": True,
                "confidence": 0.0,
            }
        )
        if not args.visual_json:
            quality = {
                "success": False,
                "failed_step": "visual_quality_check",
                "error": {
                    "error_type": "manual_review_required",
                    "message": "ModelViz adapter generated files, but visual_json was not supplied.",
                },
            }
        else:
            repair_payload = {
                "can_retry": False,
                "repaired_code": "",
                "changes_summary": [],
                "additional_dependencies_requested": [],
            }
            quality = run_plot_quality_pipeline(
                RunnableLambda(lambda _: visual),
                RunnableLambda(lambda _: repair_payload),
                script_path=str(dirs["workspace"] / "adapted_plot.py"),
                data_path=str(data_path),
                output_directory=str(dirs["outputs"]),
                max_repair_attempts=args.max_repair_attempts,
                max_dependency_install_rounds=2,
                timeout_seconds=args.timeout_seconds,
            )
    finally:
        os.chdir(previous_cwd)

    validator = _load_writer_validator()
    technical_reports = []
    for figure in sorted(dirs["outputs"].glob("*")):
        if figure.suffix.lower() not in {".png", ".svg", ".pdf"}:
            continue
        report = validator(figure, output_root)
        report_file = dirs["quality"] / f"{figure.stem}-technical.json"
        _write_json(report_file, report)
        technical_reports.append(str(report_file.resolve()))

    outputs = [
        {
            "path": str(path.resolve()),
            "sha256": _digest(path),
            "size_bytes": path.stat().st_size,
            "format": path.suffix.lower().lstrip("."),
        }
        for path in sorted(dirs["outputs"].glob("*"))
        if path.is_file()
    ]
    failed_technical = []
    for report_file in technical_reports:
        payload = _read_json(Path(report_file))
        if payload.get("status") != "PASS":
            failed_technical.append(report_file)
    status = "PASS" if not failed_technical and quality.get("success") is True else "MANUAL_REVIEW_REQUIRED"
    if failed_technical:
        status = "FAIL"

    return {
        "schema_version": "1.0",
        "status": status,
        "adapter_mode": "local_modelviz_services",
        "question_id": args.question_id,
        "one_question_only": True,
        "chinese_annotations_required": bool(args.require_chinese_annotations),
        "source": {
            "path": str(data_path),
            "sha256": _digest(data_path),
        },
        "modelviz_root": str(modelviz_root),
        "catalog": catalog_info,
        "run_root": str(dirs["run_root"]),
        "workspace": str(dirs["workspace"]),
        "outputs_dir": str(dirs["outputs"]),
        "outputs": outputs,
        "upstream_quality": quality,
        "writer_technical_reports": technical_reports,
        "failed_technical_reports": failed_technical,
        "limitations": [
            "This adapter does not validate scientific claims or data semantics.",
            "Before publication, verify source data, Chinese annotations, and the actual rendered figure.",
            "Upstream ModelViz license status must be resolved before vendoring template source into formal competition artifacts.",
        ],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local upstream ModelViz services through a Writer-side adapter.")
    parser.add_argument("--modelviz-root", required=False, default=".tmp/modelviz-skill-main/modelviz-skill-main")
    parser.add_argument("--data", required=False)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--requirement-json")
    parser.add_argument("--selection-json")
    parser.add_argument("--plan-json")
    parser.add_argument("--code-json")
    parser.add_argument("--visual-json")
    parser.add_argument("--report")
    parser.add_argument("--sheet-name")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--min-score", type=float, default=0.05)
    parser.add_argument("--max-sample-rows", type=int, default=25)
    parser.add_argument("--max-repair-attempts", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--auto-install", action="store_true")
    parser.add_argument("--require-chinese-annotations", action="store_true")
    parser.add_argument("--allowed-visual-token", action="append", default=[])
    parser.add_argument("--check-chinese-only", action="store_true")
    parser.add_argument(
        "--recall-only",
        action="store_true",
        help="Run ModelViz candidate matching only; never select, adapt or render templates.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_root = Path(args.output_root).resolve()
    if args.check_chinese_only:
        if not args.plan_json or not args.code_json:
            print("--check-chinese-only requires --plan-json and --code-json", file=sys.stderr)
            return 2
        report_path = (
            Path(args.report).resolve()
            if args.report
            else output_root / "quality" / "modelviz" / args.question_id / "chinese_annotation_report.json"
        )
        if not _inside(report_path, output_root):
            print("report path must stay inside output root", file=sys.stderr)
            return 2
        question_check = validate_question_id(args.question_id)
        if question_check["status"] != "PASS":
            report = {
                "schema_version": "1.0",
                "status": "FAIL",
                "failed_step": "validate_question_id",
                "issues": question_check["issues"],
            }
        else:
            report = validate_chinese_visual_annotations(
                plan=_read_json(Path(args.plan_json)),
                adaptation=_read_json(Path(args.code_json)),
                allowed_tokens=set(args.allowed_visual_token or []),
            )
        _write_json(report_path, report)
        print(json.dumps({"status": report["status"], "report": report_path.as_posix()}))
        return 0 if report["status"] == "PASS" else 1

    if args.recall_only:
        if not args.requirement_json:
            print("--recall-only requires --requirement-json", file=sys.stderr)
            return 2
        report_path = (
            Path(args.report).resolve()
            if args.report
            else output_root
            / "quality"
            / "modelviz_recall"
            / args.question_id
            / "recall_report.json"
        )
        report = run_modelviz_recall(args)
        if not _inside(report_path, output_root):
            print("report path must stay inside output root", file=sys.stderr)
            return 2
        _write_json(report_path, report)
        print(json.dumps({"status": report["status"], "report": report_path.as_posix()}))
        return 0 if report["status"] == "PASS" else 1

    missing = [
        name
        for name in ("data", "requirement_json", "selection_json", "plan_json", "code_json")
        if not getattr(args, name)
    ]
    if missing:
        print(f"missing required arguments: {', '.join('--' + name.replace('_', '-') for name in missing)}", file=sys.stderr)
        return 2
    report_path = (
        Path(args.report).resolve()
        if args.report
        else output_root / "quality" / "modelviz" / args.question_id / "adapter_report.json"
    )
    report = run_modelviz_adapter(args)
    if not _inside(report_path, output_root):
        print("report path must stay inside output root", file=sys.stderr)
        return 2
    _write_json(report_path, report)
    print(json.dumps({"status": report["status"], "report": report_path.as_posix()}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
