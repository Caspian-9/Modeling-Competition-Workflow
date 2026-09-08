from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from harness.intake import RawIntakeService
from harness.models import ValidationError
from harness.qc import DeterministicQC
from harness.runner import ExperimentRunner
from harness.selection import select_experiment
from harness.status import build_status
from harness.storage import CaseRepository

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None


class FastHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = CaseRepository(self.root / "cases")
        self.config = self.repository.initialize_case("FAST-C", ("Q1", "Q2"))
        self.case_dir = self.repository.case_dir(self.config.case_id)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def prepare_raw(self) -> dict[str, object]:
        (self.case_dir / "raw" / "problem.txt").write_text(
            "这是一份用于测试 FAST 工作流的数学建模题目，包含两个需要分析的小问。",
            encoding="utf-8",
        )
        (self.case_dir / "raw" / "data.csv").write_text(
            "id,value\n1,2\n2,4\n", encoding="utf-8"
        )
        return RawIntakeService(self.repository).sync("FAST-C")

    def create_experiment(self, experiment_id: str = "EXP-BASE"):
        manifest = self.repository.create_experiment(
            "FAST-C",
            "Q1",
            experiment_id,
            title="可解释基线",
            objective="验证最小实验闭环",
            command=("python", "code/main.py"),
            seed=2026,
            inputs=("raw/data.csv",),
            expected_outputs=("outputs/metrics.json", "outputs/report.md"),
        )
        directory = self.repository.experiment_dir("FAST-C", "Q1", experiment_id)
        (directory / "code" / "helper.py").write_text(
            "SCORE = 1.0\n", encoding="utf-8"
        )
        (directory / "code" / "main.py").write_text(
            "from pathlib import Path\n"
            "import json, os\n"
            "import helper\n"
            "out = Path(os.environ['MODELING_OUTPUT_DIR'])\n"
            "out.mkdir(parents=True, exist_ok=True)\n"
            "(out / 'metrics.json').write_text(json.dumps({'score': helper.SCORE}))\n"
            "(out / 'report.md').write_text('# 实验结果\\n\\n基线运行成功。\\n', "
            "encoding='utf-8')\n",
            encoding="utf-8",
        )
        return manifest

    def test_init_normalizes_unicode_dash_and_preserves_legacy_files(self) -> None:
        legacy = self.root / "cases" / "2025-C"
        (legacy / "state").mkdir(parents=True)
        marker = legacy / "state" / "case_state.json"
        marker.write_text('{"legacy": true}', encoding="utf-8")
        config = self.repository.initialize_case("2025—C", ("Q1",))
        self.assertEqual(config.case_id, "2025-C")
        self.assertEqual(marker.read_text(encoding="utf-8"), '{"legacy": true}')
        self.assertTrue((legacy / "workspace" / "brief.md").is_file())

    def test_new_analysis_template_covers_exploration_and_validation(self) -> None:
        for question in self.config.questions:
            with self.subTest(question=question):
                analysis = (
                    self.case_dir / "questions" / question / "analysis.md"
                ).read_text(encoding="utf-8")
                self.assertIn(f"# {question} 分析", analysis)
                for required in (
                    "问题与信息边界",
                    "探索发现与模型影响",
                    "建模选择与验证计划",
                    "实际检验证据与修正",
                    "采用结论与剩余风险",
                    "未检查、通过、失败、不适用",
                    "无数据题",
                    "允许库外方法",
                    "QC 不证明科学有效",
                ):
                    self.assertIn(required, analysis)

    def test_reinitialize_preserves_existing_analysis_bytes(self) -> None:
        path = self.case_dir / "questions" / "Q1" / "analysis.md"
        original = "# 已有推理\r\n\r\n用户正文和未完成假设。\r\n".encode("utf-8")
        path.write_bytes(original)
        self.repository.initialize_case("FAST-C")
        self.assertEqual(path.read_bytes(), original)

    def test_legacy_analysis_preserved_when_fast_layout_is_added(self) -> None:
        question_dir = self.root / "cases" / "LEGACY" / "questions" / "Q1"
        question_dir.mkdir(parents=True)
        path = question_dir / "analysis.md"
        original = "# 历史分析\n不得覆盖。\n".encode("utf-8")
        path.write_bytes(original)
        self.repository.initialize_case("LEGACY", ("Q1", "Q2"))
        self.assertEqual(path.read_bytes(), original)
        new_analysis = question_dir.parent / "Q2" / "analysis.md"
        self.assertIn("实际检验证据与修正", new_analysis.read_text(encoding="utf-8"))

    def test_intake_extracts_text_and_inventories_data(self) -> None:
        inventory = self.prepare_raw()
        self.assertTrue(inventory["ready"])
        self.assertEqual(inventory["data_files"][0]["metadata"]["column_count"], 2)
        self.assertIn(
            "数学建模题目",
            (self.case_dir / "workspace" / "problem.md").read_text(encoding="utf-8"),
        )

    def test_initialization_layout_and_status_progression(self) -> None:
        initialization = self.case_dir / "initialization"
        self.assertTrue((initialization / "README.md").is_file())
        self.assertTrue((initialization / "figures").is_dir())
        self.assertEqual(
            build_status(self.repository, "FAST-C")["initialization"]["status"],
            "WAITING_FOR_RAW",
        )
        self.prepare_raw()
        self.assertEqual(
            build_status(self.repository, "FAST-C")["initialization"]["status"],
            "NOT_STARTED",
        )
        (initialization / "plan.md").touch()
        self.assertEqual(
            build_status(self.repository, "FAST-C")["initialization"]["status"],
            "NOT_STARTED",
        )
        (initialization / "plan.md").write_text("# 数据计划\n", encoding="utf-8")
        self.assertEqual(
            build_status(self.repository, "FAST-C")["initialization"]["status"],
            "ENGINEERING",
        )
        (initialization / "engineer_report.md").write_text(
            "# 数据审计与 EDA\n", encoding="utf-8"
        )
        self.assertEqual(
            build_status(self.repository, "FAST-C")["initialization"]["status"],
            "SYNTHESIS",
        )
        (initialization / "summary.md").write_text(
            "# 初始化总结\n", encoding="utf-8"
        )
        self.assertEqual(
            build_status(self.repository, "FAST-C")["initialization"]["status"],
            "FIGURES",
        )
        (initialization / "figures" / "eda.svg").write_text(
            "<svg></svg>\n", encoding="utf-8"
        )
        self.assertEqual(
            build_status(self.repository, "FAST-C")["initialization"]["status"],
            "WRITING",
        )
        (initialization / "front_matter.md").write_text(
            "# 前置正文\n", encoding="utf-8"
        )
        status = build_status(self.repository, "FAST-C")["initialization"]
        self.assertEqual(status["status"], "READY_FOR_Q1")
        self.assertTrue(status["user_review_required"])

    def test_loading_existing_case_restores_missing_initialization_scaffold(self) -> None:
        initialization = self.case_dir / "initialization"
        (initialization / "README.md").unlink()
        (initialization / "figures").rmdir()

        status = build_status(self.repository, "FAST-C")["initialization"]

        self.assertTrue((initialization / "README.md").is_file())
        self.assertTrue((initialization / "figures").is_dir())
        self.assertEqual(status["status"], "WAITING_FOR_RAW")

    def test_intake_rejects_broken_xlsx(self) -> None:
        (self.case_dir / "raw" / "problem.txt").write_text(
            "这是一份长度足够的数学建模题面，用来测试损坏工作簿能被识别。",
            encoding="utf-8",
        )
        (self.case_dir / "raw" / "broken.xlsx").write_bytes(b"not a zip")
        inventory = RawIntakeService(self.repository).sync("FAST-C")
        self.assertFalse(inventory["ready"])
        self.assertIn("无法检查", "\n".join(inventory["errors"]))

    @unittest.skipIf(Workbook is None, "openpyxl is required for XLSX conversion")
    def test_chat_ingest_copies_attachments_and_exports_each_sheet_to_csv(self) -> None:
        incoming = self.root / "chat-attachments"
        incoming.mkdir()
        problem = incoming / "problem.txt"
        problem.write_text(
            "这是一份由桌面对话附件提供的数学建模题目，文本长度足以通过题面检查。",
            encoding="utf-8",
        )
        workbook_path = incoming / "data.xlsx"
        workbook = Workbook()
        first = workbook.active
        first.title = "原始数据"
        first.append(["编号", "数值"])
        first.append([1, 2.5])
        second = workbook.create_sheet("分组")
        second.append(["组别", "数量"])
        second.append(["A", 3])
        workbook.save(workbook_path)
        workbook.close()

        result = RawIntakeService(self.repository).ingest(
            "FAST-C", [problem, workbook_path]
        )
        inventory = result["inventory"]
        self.assertTrue(inventory["ready"])
        self.assertEqual(len(result["copied_files"]), 2)
        self.assertEqual(len(inventory["derived_csv_files"]), 2)
        self.assertTrue((self.case_dir / "raw" / "data.xlsx").is_file())
        first_csv = self.case_dir / inventory["derived_csv_files"][0]["path"]
        self.assertEqual(
            first_csv.read_text(encoding="utf-8").splitlines(),
            ["编号,数值", "1,2.5"],
        )

    def test_run_qc_and_status(self) -> None:
        self.prepare_raw()
        self.create_experiment()
        result = ExperimentRunner(self.repository).run("FAST-C", "Q1", "EXP-BASE")
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertTrue(all(item["exists"] for item in result["outputs"]))
        report = DeterministicQC(self.repository).run("FAST-C", "Q1", "EXP-BASE")
        self.assertEqual(report["decision"], "PASS")
        selection = select_experiment(
            self.repository,
            "FAST-C",
            "Q1",
            "EXP-BASE",
            reason="基线结果完整且可解释",
        )
        self.assertEqual(selection["current"]["experiment_id"], "EXP-BASE")
        status = build_status(self.repository, "FAST-C")
        self.assertTrue(status["raw_ready"])
        self.assertEqual(
            status["questions"][0]["selected_experiment"]["experiment_id"],
            "EXP-BASE",
        )

    def test_qc_detects_output_drift_and_force_selection_records_risk(self) -> None:
        self.prepare_raw()
        self.create_experiment()
        ExperimentRunner(self.repository).run("FAST-C", "Q1", "EXP-BASE")
        output = (
            self.repository.experiment_dir("FAST-C", "Q1", "EXP-BASE")
            / "outputs"
            / "metrics.json"
        )
        output.write_text(json.dumps({"score": 99}), encoding="utf-8")
        report = DeterministicQC(self.repository).run("FAST-C", "Q1", "EXP-BASE")
        self.assertEqual(report["decision"], "FAIL")
        with self.assertRaises(ValidationError):
            select_experiment(
                self.repository, "FAST-C", "Q1", "EXP-BASE", reason="测试"
            )
        selection = select_experiment(
            self.repository,
            "FAST-C",
            "Q1",
            "EXP-BASE",
            reason="用户知晓输出已变化，仍保留该方案",
            force=True,
        )
        self.assertTrue(selection["current"]["forced"])

    def test_input_hash_change_blocks_run(self) -> None:
        self.prepare_raw()
        self.create_experiment()
        (self.case_dir / "raw" / "data.csv").write_text(
            "id,value\n1,999\n", encoding="utf-8"
        )
        with self.assertRaises(ValidationError):
            ExperimentRunner(self.repository).run("FAST-C", "Q1", "EXP-BASE")

    def test_expected_output_must_stay_under_outputs(self) -> None:
        self.prepare_raw()
        with self.assertRaises(ValidationError):
            self.repository.create_experiment(
                "FAST-C",
                "Q1",
                "EXP-UNSAFE",
                title="非法输出",
                objective="确认输出边界",
                command=("python", "code/main.py"),
                seed=2026,
                inputs=("raw/data.csv",),
                expected_outputs=("code/main.py",),
            )

    def test_batch_runs_independent_experiments(self) -> None:
        self.prepare_raw()
        for experiment_id in ("EXP-A", "EXP-B"):
            self.create_experiment(experiment_id)
        results = ExperimentRunner(self.repository).run_batch(
            "FAST-C", "Q1", ("EXP-A", "EXP-B"), max_workers=8
        )
        self.assertEqual([item["status"] for item in results], ["SUCCEEDED", "SUCCEEDED"])

    def test_experiment_environment_does_not_inherit_api_keys(self) -> None:
        old = os.environ.get("EXAMPLE_API_KEY")
        os.environ["EXAMPLE_API_KEY"] = "secret"
        try:
            environment = ExperimentRunner._experiment_environment()
        finally:
            if old is None:
                os.environ.pop("EXAMPLE_API_KEY", None)
            else:
                os.environ["EXAMPLE_API_KEY"] = old
        self.assertNotIn("EXAMPLE_API_KEY", environment)


if __name__ == "__main__":
    unittest.main()
