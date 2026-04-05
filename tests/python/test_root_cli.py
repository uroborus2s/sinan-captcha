from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from core import cli


class RootCliTests(unittest.TestCase):
    def test_prints_help_without_args(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main([])
        self.assertEqual(code, 0)
        self.assertIn("uv run sinan <command>", buffer.getvalue())

    def test_dispatches_train_group1(self) -> None:
        with patch("core.cli.train_group1_cli.main", return_value=0) as handler:
            code = cli.main(["train", "group1", "--dry-run"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(["--dry-run"])

    def test_dispatches_predict_group1(self) -> None:
        with patch("core.cli.predict_cli.main", return_value=0) as handler:
            code = cli.main(["predict", "group1", "--dry-run"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(["group1", "--dry-run"])

    def test_dispatches_test_group2(self) -> None:
        with patch("core.cli.modeltest_cli.main", return_value=0) as handler:
            code = cli.main(["test", "group2", "--dry-run"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(["group2", "--dry-run"])

    def test_dispatches_env_setup_train(self) -> None:
        with patch("core.cli.setup_train_cli.main", return_value=0) as handler:
            code = cli.main(["env", "setup-train", "--yes"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(["--yes"])

    def test_dispatches_release_build(self) -> None:
        with patch("core.cli.release_cli.main", return_value=0) as handler:
            code = cli.main(["release", "build", "--project-dir", "."])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(["build", "--project-dir", "."])

    def test_dispatches_solve_run(self) -> None:
        with patch("core.cli.solve_cli.main", return_value=0) as handler:
            code = cli.main(["solve", "run", "--bundle-dir", "bundles/current", "--request", "req.json"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(["run", "--bundle-dir", "bundles/current", "--request", "req.json"])

    def test_dispatches_auto_train_run(self) -> None:
        with patch("core.cli.auto_train_cli.main", return_value=0) as handler:
            code = cli.main(["auto-train", "run", "group1", "--study-name", "study_001"])
        self.assertEqual(code, 0)
        handler.assert_called_once_with(["run", "group1", "--study-name", "study_001"])

    def test_returns_error_for_unknown_command(self) -> None:
        code = cli.main(["unknown"])
        self.assertEqual(code, 1)

    def test_removed_dataset_build_yolo_is_unknown_command(self) -> None:
        code = cli.main(["dataset", "build-yolo"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
