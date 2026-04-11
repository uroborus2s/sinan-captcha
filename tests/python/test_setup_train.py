from __future__ import annotations

import importlib
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from ops import setup_train


class SetupTrainTests(unittest.TestCase):
    @staticmethod
    def _repo_version() -> str:
        return tomllib.loads(
            (
                Path(__file__).resolve().parents[2]
                / "packages"
                / "sinan-captcha"
                / "pyproject.toml"
            ).read_text(encoding="utf-8")
        )["project"]["version"]

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

    def test_setup_train_module_imports_without_loading_auto_train_package_init(self) -> None:
        original_auto_train = sys.modules.pop("auto_train", None)
        original_business_eval = sys.modules.pop("auto_train.business_eval", None)
        original_setup_train = sys.modules.pop("ops.setup_train", None)
        try:
            module = importlib.import_module("ops.setup_train")
            self.assertTrue(hasattr(module, "copy_opencode_assets"))
            self.assertNotIn("auto_train.business_eval", sys.modules)
        finally:
            sys.modules.pop("ops.setup_train", None)
            if original_setup_train is not None:
                sys.modules["ops.setup_train"] = original_setup_train
            sys.modules.pop("auto_train", None)
            if original_auto_train is not None:
                sys.modules["auto_train"] = original_auto_train
            sys.modules.pop("auto_train.business_eval", None)
            if original_business_eval is not None:
                sys.modules["auto_train.business_eval"] = original_business_eval

    def test_prepare_training_root_writes_runtime_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir) / "sinan-captcha-work"
            package_version = self._repo_version()
            plan = setup_train.TrainingSetupPlan(
                train_root=train_root,
                package_spec=f"sinan-captcha[train]=={package_version}",
                torch_backend=setup_train.resolve_torch_backend("12.6", override="auto"),
                cuda_version="12.6",
                python_version="3.12",
            )

            setup_train.prepare_training_root(plan)

            self.assertTrue((train_root / ".python-version").exists())
            pyproject = (train_root / "pyproject.toml").read_text(encoding="utf-8")
            self.assertIn(f'sinan-captcha[train]=={package_version}', pyproject)
            self.assertIn('torch', pyproject)
            self.assertIn('name = "pytorch-cu126"', pyproject)
            self.assertTrue((train_root / "datasets" / "group1").exists())
            self.assertTrue((train_root / "datasets" / "group2").exists())
            self.assertTrue((train_root / "README-训练机使用说明.txt").exists())
            self.assertTrue((train_root / ".opencode" / "commands" / "judge-trial.md").exists())
            self.assertTrue((train_root / ".opencode" / "skills" / "training-judge" / "SKILL.md").exists())
            readme = (train_root / "README-训练机使用说明.txt").read_text(encoding="utf-8")
            self.assertIn(".opencode/commands", readme)
            self.assertIn("opencode serve --port 4096", readme)

    def test_sync_training_root_runs_uv_install_and_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir)
            with patch("ops.setup_train.subprocess.run") as subprocess_run:
                subprocess_run.return_value.returncode = 0
                setup_train.sync_training_root(train_root)

            commands = [call.args[0] for call in subprocess_run.call_args_list]
            self.assertEqual(commands[0], ["uv", "python", "install", "3.12"])
            self.assertEqual(commands[1], ["uv", "sync"])

    def test_cli_supports_yes_mode_without_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            train_root = Path(tmpdir) / "work"
            package_version = self._repo_version()
            with patch("ops.setup_train.sync_training_root") as sync_training_root:
                code = setup_train.main(
                    [
                        "--train-root",
                        str(train_root),
                        "--yes",
                        "--torch-backend",
                        "cpu",
                        "--package-spec",
                        f"sinan-captcha[train]=={package_version}",
                    ]
                )

            self.assertEqual(code, 0)
            sync_training_root.assert_called_once_with(train_root.resolve())
