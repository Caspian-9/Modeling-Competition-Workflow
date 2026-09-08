from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from harness.cli import build_parser, main


class FastCliTests(unittest.TestCase):
    def test_batch_defaults_to_eight_workers(self) -> None:
        args = build_parser().parse_args(["run-batch", "C", "Q1", "EXP-A", "EXP-B"])
        self.assertEqual(args.max_workers, 8)

    def test_cli_init_create_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cases_root = str(Path(temporary) / "cases")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "--cases-root",
                        cases_root,
                        "init",
                        "CLI—C",
                        "--questions",
                        "Q1",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["case_id"], "CLI-C")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["--cases-root", cases_root, "init", "CLI-C"]), 0
                )
            case_dir = Path(cases_root) / "CLI-C"
            (case_dir / "raw" / "problem.txt").write_text(
                "这是 CLI 测试使用的数学建模题目文本，长度足以通过题面提取检查。",
                encoding="utf-8",
            )
            (case_dir / "raw" / "data.csv").write_text(
                "x,y\n1,2\n", encoding="utf-8"
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--cases-root", cases_root, "intake", "CLI-C"]), 0)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "--cases-root",
                        cases_root,
                        "experiment-create",
                        "CLI-C",
                        "Q1",
                        "EXP-1",
                        "--objective",
                        "验证 CLI",
                        "--input",
                        "raw/data.csv",
                        "--output",
                        "outputs/result.json",
                        "--command",
                        "python",
                        "code/main.py",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["experiment_id"], "EXP-1")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(
                    main(["--cases-root", cases_root, "status", "CLI-C"]), 0
                )
            status = json.loads(stdout.getvalue())
            self.assertTrue(status["raw_ready"])
            self.assertEqual(
                status["questions"][0]["experiments"][0]["status"], "CREATED"
            )

    def test_cli_reports_invalid_case(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temporary, redirect_stderr(stderr):
            code = main(
                ["--cases-root", str(Path(temporary) / "cases"), "status", "../bad"]
            )
        self.assertEqual(code, 2)
        self.assertIn("unsafe case_id", stderr.getvalue())

    def test_chat_intake_initializes_case_and_copies_attachments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases_root = root / "cases"
            incoming = root / "attachments"
            incoming.mkdir()
            problem = incoming / "problem.txt"
            problem.write_text(
                "这是由桌面对话附件提供的数学建模题目，长度足以通过题面提取检查。",
                encoding="utf-8",
            )
            data = incoming / "data.csv"
            data.write_text("x,y\n1,2\n", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "--cases-root",
                        str(cases_root),
                        "chat-intake",
                        "CHAT-C",
                        "--questions",
                        "Q1",
                        "--file",
                        str(problem),
                        "--file",
                        str(data),
                    ]
                )
            result = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(result["inventory"]["ready"])
            self.assertTrue((cases_root / "CHAT-C" / "raw" / "data.csv").is_file())


if __name__ == "__main__":
    unittest.main()
