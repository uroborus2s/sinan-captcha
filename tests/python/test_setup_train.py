from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.ops import setup_train


class SetupTrainTests(unittest.TestCase):
    def test_resolve_torch_backend_from_cuda_version(self) -> None:
        backend = setup_train.resolve_torch_backend("12.6", override="auto")
        self.assertEqual(backend.name, "cu126")
        self.assertEqual(backend.index_url, "https://download.pytorch.org/whl/cu126")

    def test_resolve_torch_backend_supports_cuda_13(self) -> None:
        backend = setup_train.resolve_torch_backend("13.2", override="auto")
        self.assertEqual(backend.name, "cu130")
        self.assertEqual(backend.index_url, "https://download.pytorch.org/whl/cu130")

    def test_resolve_torch_backend_rejects_unsupported_cuda(self) -> None:
        with self.assertRaises(ValueError):
            setup_train.resolve_torch_backend("12.4", override="auto")

    def test_prepare_training_root_writes_runtime_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir) / "sinan-captcha-work"
            plan = setup_train.TrainingSetupPlan(
                train_root=train_root,
                package_spec="sinan-captcha[train]==0.1.3",
                torch_backend=setup_train.resolve_torch_backend("12.6", override="auto"),
                cuda_version="12.6",
                python_version="3.12",
            )

            setup_train.prepare_training_root(plan)

            self.assertTrue((train_root / ".python-version").exists())
            pyproject = (train_root / "pyproject.toml").read_text(encoding="utf-8")
            self.assertIn('sinan-captcha[train]==0.1.3', pyproject)
            self.assertIn('torch', pyproject)
            self.assertIn('name = "pytorch-cu126"', pyproject)
            self.assertTrue((train_root / "datasets" / "group1").exists())
            self.assertTrue((train_root / "datasets" / "group2").exists())
            self.assertTrue((train_root / "README-训练机使用说明.txt").exists())

    def test_sync_training_root_runs_uv_install_and_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir)
            with patch("core.ops.setup_train.subprocess.run") as subprocess_run:
                subprocess_run.return_value.returncode = 0
                setup_train.sync_training_root(train_root)

            commands = [call.args[0] for call in subprocess_run.call_args_list]
            self.assertEqual(commands[0], ["uv", "python", "install", "3.12"])
            self.assertEqual(commands[1], ["uv", "sync"])

    def test_cli_supports_yes_mode_without_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir) / "work"
            with patch("core.ops.setup_train.sync_training_root") as sync_training_root:
                code = setup_train.main(
                    [
                        "--train-root",
                        str(train_root),
                        "--yes",
                        "--torch-backend",
                        "cpu",
                        "--package-spec",
                        "sinan-captcha[train]==0.1.3",
                    ]
                )

            self.assertEqual(code, 0)
            sync_training_root.assert_called_once_with(train_root.resolve())
