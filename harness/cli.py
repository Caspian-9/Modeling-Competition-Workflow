from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from .intake import RawIntakeService
from .models import ValidationError
from .qc import DeterministicQC
from .runner import ExperimentRunner
from .selection import select_experiment
from .status import build_status
from .storage import CaseRepository


def _configure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def _dump(data: Any) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    try:
        sys.stdout.write(payload)
    except UnicodeEncodeError:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            sys.stdout.write(payload.encode("ascii", errors="backslashreplace").decode())
        else:
            buffer.write(payload.encode("utf-8"))
            buffer.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m harness",
        description="FAST 数学建模实验与归档工具；不编排 Agent 或论文工作流。",
    )
    parser.add_argument("--cases-root", default="cases", help="case 根目录")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="初始化或补齐 FAST case 目录")
    init.add_argument("case_id")
    init.add_argument("--questions", nargs="+")

    intake = commands.add_parser("intake", help="登记 raw 文件并提取题面")
    intake.add_argument("case_id")

    chat_intake = commands.add_parser(
        "chat-intake",
        help="将桌面对话附件复制到 raw/，再登记题面、数据和 CSV 派生文件",
    )
    chat_intake.add_argument("case_id")
    chat_intake.add_argument(
        "--file",
        action="append",
        required=True,
        help="桌面会话暴露的附件本地路径，可重复使用",
    )
    chat_intake.add_argument("--questions", nargs="+")
    chat_intake.add_argument(
        "--replace",
        action="store_true",
        help="确认以同名新附件替换现有 raw 文件",
    )

    status = commands.add_parser("status", help="汇总 raw、实验、选择和论文进度")
    status.add_argument("case_id")

    create = commands.add_parser("experiment-create", help="创建可复现实验目录")
    create.add_argument("case_id")
    create.add_argument("question_id")
    create.add_argument("experiment_id")
    create.add_argument("--title")
    create.add_argument("--objective", required=True)
    create.add_argument("--seed", type=int, default=2026)
    create.add_argument(
        "--input",
        action="append",
        default=[],
        help="case 相对输入路径，可重复使用",
    )
    create.add_argument(
        "--output",
        action="append",
        required=True,
        help="实验目录相对输出路径，可重复使用",
    )
    create.add_argument("--notes", default="")
    create.add_argument(
        "--command",
        dest="run_command",
        nargs=argparse.REMAINDER,
        required=True,
        help="必须放在最后，例如 --command python code/main.py",
    )

    run = commands.add_parser("run", help="执行一个可信实验")
    run.add_argument("case_id")
    run.add_argument("question_id")
    run.add_argument("experiment_id")
    _add_runner_arguments(run)

    batch = commands.add_parser("run-batch", help="并行执行多个独立实验")
    batch.add_argument("case_id")
    batch.add_argument("question_id")
    batch.add_argument("experiment_ids", nargs="+")
    batch.add_argument("--max-workers", type=int, default=8)
    _add_runner_arguments(batch)

    qc = commands.add_parser("qc", help="检查运行、输入、代码和输出完整性")
    qc.add_argument("case_id")
    qc.add_argument("question_id")
    qc.add_argument("experiment_id")

    select = commands.add_parser("select", help="记录当前问采用的实验结果")
    select.add_argument("case_id")
    select.add_argument("question_id")
    select.add_argument("experiment_id")
    select.add_argument("--reason", required=True)
    select.add_argument(
        "--force",
        action="store_true",
        help="由用户明确承担风险，在 QC 未通过时仍记录选择",
    )
    return parser


def _add_runner_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--max-log-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument(
        "--allow-executable",
        action="append",
        default=[],
        help="额外允许的可信可执行文件名",
    )


def main(argv: Sequence[str] | None = None) -> int:
    _configure_utf8_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    repository = CaseRepository(args.cases_root)
    try:
        if args.command == "init":
            result = repository.initialize_case(args.case_id, args.questions).to_dict()
            _dump(result)
            return 0
        if args.command == "intake":
            result = RawIntakeService(repository).sync(args.case_id)
            _dump(result)
            return 0 if result["ready"] else 1
        if args.command == "chat-intake":
            repository.initialize_case(args.case_id, args.questions)
            result = RawIntakeService(repository).ingest(
                args.case_id,
                args.file,
                replace=args.replace,
            )
            _dump(result)
            return 0 if result["inventory"]["ready"] else 1
        if args.command == "status":
            _dump(build_status(repository, args.case_id))
            return 0
        if args.command == "experiment-create":
            manifest = repository.create_experiment(
                args.case_id,
                args.question_id,
                args.experiment_id,
                title=args.title or args.experiment_id,
                objective=args.objective,
                command=tuple(args.run_command),
                seed=args.seed,
                inputs=tuple(args.input),
                expected_outputs=tuple(args.output),
                notes=args.notes,
            )
            _dump(manifest.to_dict())
            return 0
        if args.command in {"run", "run-batch"}:
            runner = ExperimentRunner(
                repository,
                timeout_seconds=args.timeout,
                max_log_bytes=args.max_log_bytes,
                allowed_executables=args.allow_executable,
            )
            if args.command == "run":
                result = runner.run(
                    args.case_id, args.question_id, args.experiment_id
                )
                _dump(result)
                return 0 if result["status"] == "SUCCEEDED" else 1
            results = runner.run_batch(
                args.case_id,
                args.question_id,
                args.experiment_ids,
                max_workers=args.max_workers,
            )
            _dump(results)
            return 0 if all(item["status"] == "SUCCEEDED" for item in results) else 1
        if args.command == "qc":
            report = DeterministicQC(repository).run(
                args.case_id, args.question_id, args.experiment_id
            )
            _dump(report)
            return 0 if report["decision"] == "PASS" else 1
        if args.command == "select":
            _dump(
                select_experiment(
                    repository,
                    args.case_id,
                    args.question_id,
                    args.experiment_id,
                    reason=args.reason,
                    force=args.force,
                )
            )
            return 0
        parser.error(f"unsupported command: {args.command}")
    except (ValidationError, OSError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    return 2
