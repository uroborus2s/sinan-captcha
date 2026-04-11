from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import cli


class RootCliTests(unittest.TestCase):
    def test_prints_help_without_args(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main([])
        self.assertEqual(code, 0)
        self.assertIn("uv run sinan <command>", buffer.getvalue())

    def test_dispatches_train_group1(self) -> None:
        with patch("cli._run_command", return_value=0) as handler:
            code = cli.main(["train", "group1", "--dry-run"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with("train.group1.cli", ["--dry-run"])

    def test_dispatches_predict_group1(self) -> None:
        with patch("cli._run_command", return_value=0) as handler:
            code = cli.main(["predict", "group1", "--dry-run"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with("predict.cli", ["group1", "--dry-run"])

    def test_dispatches_test_group2(self) -> None:
        with patch("cli._run_command", return_value=0) as handler:
            code = cli.main(["test", "group2", "--dry-run"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with("modeltest.cli", ["group2", "--dry-run"])

    def test_dispatches_env_setup_train(self) -> None:
        with patch("cli._run_command", return_value=0) as handler:
            code = cli.main(["env", "setup-train", "--yes"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with("ops.setup_train", ["--yes"])

    def test_dispatches_materials_audit_group1_query(self) -> None:
        with patch("cli._run_command", return_value=0) as handler:
            code = cli.main(["materials", "audit-group1-query", "--query-dir", "query", "--model", "qwen2.5vl:7b"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(
            "materials.query_audit_cli",
            ["--query-dir", "query", "--model", "qwen2.5vl:7b"],
        )

    def test_dispatches_solve_run(self) -> None:
        with patch("cli._run_command", return_value=0) as handler:
            code = cli.main(["solve", "run", "--bundle-dir", "bundles/current", "--request", "req.json"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(
            "solve.cli",
            ["run", "--bundle-dir", "bundles/current", "--request", "req.json"],
        )

    def test_dispatches_auto_train_run(self) -> None:
        with patch("cli._run_command", return_value=0) as handler:
            code = cli.main(["auto-train", "run", "group1", "--study-name", "study_001"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(
            "auto_train.cli",
            ["run", "group1", "--study-name", "study_001"],
        )

    def test_dispatches_exam_prepare(self) -> None:
        with patch("cli._run_command", return_value=0) as handler:
            code = cli.main(["exam", "prepare", "--task", "group1"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with("exam.cli", ["prepare", "--task", "group1"])

    def test_returns_error_for_unknown_command(self) -> None:
        code = cli.main(["unknown"])
        self.assertEqual(code, 1)

    def test_removed_dataset_build_yolo_is_unknown_command(self) -> None:
        code = cli.main(["dataset", "build-yolo"])
        self.assertEqual(code, 1)

    def test_release_is_unknown_command(self) -> None:
        code = cli.main(["release", "build"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
