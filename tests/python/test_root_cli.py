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

    def test_returns_error_for_unknown_command(self) -> None:
        code = cli.main(["unknown"])
        self.assertEqual(code, 1)

    def test_removed_dataset_build_yolo_is_unknown_command(self) -> None:
        code = cli.main(["dataset", "build-yolo"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
