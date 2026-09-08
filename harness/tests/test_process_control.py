from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from harness.process_control import run_process


class ProcessControlTests(unittest.TestCase):
    def test_process_output_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outcome = run_process(
                (sys.executable, "-c", "print('x' * 5000)"),
                cwd=root,
                environment=os.environ,
                stdout_path=root / "stdout.log",
                stderr_path=root / "stderr.log",
                timeout_seconds=10,
                max_log_bytes=1024,
            )
            self.assertEqual(outcome.exit_code, 0)
            self.assertTrue(outcome.stdout_truncated)
            self.assertLess((root / "stdout.log").stat().st_size, 1200)

    def test_timeout_terminates_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outcome = run_process(
                (sys.executable, "-c", "import time; time.sleep(10)"),
                cwd=root,
                environment=os.environ,
                stdout_path=root / "stdout.log",
                stderr_path=root / "stderr.log",
                timeout_seconds=1,
                max_log_bytes=1024,
            )
            self.assertTrue(outcome.timed_out)


if __name__ == "__main__":
    unittest.main()
