from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


def _load_repo_script():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "repo.py"
    spec = importlib.util.spec_from_file_location("repo_script", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load repo script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RepoScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = _load_repo_script()

    def _make_layout(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        packages_dir = root / "packages"
        sinan_dir = packages_dir / "sinan-captcha"
        solver_dir = packages_dir / "solver"
        generator_dir = packages_dir / "generator"
        sinan_dir.mkdir(parents=True)
        solver_dir.mkdir(parents=True)
        generator_dir.mkdir(parents=True)
        return self.repo.RepoLayout(
            repo_root=root,
            packages_dir=packages_dir,
            sinan_dir=sinan_dir,
            solver_dir=solver_dir,
            generator_dir=generator_dir,
        )

    def test_build_sinan_captcha_uses_workspace_build_command(self) -> None:
        layout = self._make_layout()
        (layout.sinan_dir / "pyproject.toml").write_text("[project]\nname='sinan-captcha'\n", encoding="utf-8")
        (layout.sinan_dir / "dist" / "stale.txt").parent.mkdir(parents=True)
        (layout.sinan_dir / "dist" / "stale.txt").write_text("old", encoding="utf-8")

        with patch.object(self.repo.subprocess, "run") as run_mock:
            self.repo.build_target("sinan-captcha", layout=layout)

        self.assertTrue((layout.sinan_dir / "dist").is_dir())
        self.assertFalse((layout.sinan_dir / "dist" / "stale.txt").exists())
        run_mock.assert_called_once_with(
            [
                "uv",
                "build",
                "--package",
                "sinan-captcha",
                "--out-dir",
                "packages/sinan-captcha/dist",
            ],
            check=True,
            cwd=layout.repo_root,
        )

    def test_build_generator_uses_package_dist_target(self) -> None:
        layout = self._make_layout()
        (layout.generator_dir / "go.mod").write_text("module example.com/generator\n", encoding="utf-8")

        def fake_go_env(command, cwd, env, text):
            self.assertEqual(cwd, layout.generator_dir)
            self.assertEqual(env["GOOS"], "windows")
            self.assertEqual(env["GOARCH"], "amd64")
            self.assertTrue(text)
            return "windows\n" if command[-1] == "GOOS" else "amd64\n"

        with (
            patch.object(self.repo.subprocess, "check_output", side_effect=fake_go_env) as output_mock,
            patch.object(self.repo.subprocess, "run") as run_mock,
        ):
            self.repo.build_target("generator", layout=layout, goos="windows", goarch="amd64")

        output_mock.assert_any_call(
            ["go", "env", "GOOS"],
            cwd=layout.generator_dir,
            env=unittest.mock.ANY,
            text=True,
        )
        run_mock.assert_called_once_with(
            [
                "go",
                "build",
                "-o",
                str((layout.generator_dir / "dist" / "windows-amd64" / "sinan-generator.exe").resolve()),
                "./cmd/sinan-generator",
            ],
            check=True,
            cwd=layout.generator_dir,
            env=unittest.mock.ANY,
        )

    def test_build_all_dispatches_all_members(self) -> None:
        layout = self._make_layout()
        (layout.sinan_dir / "pyproject.toml").write_text("[project]\nname='sinan-captcha'\n", encoding="utf-8")
        (layout.solver_dir / "pyproject.toml").write_text("[project]\nname='sinanz'\n", encoding="utf-8")
        (layout.generator_dir / "go.mod").write_text("module example.com/generator\n", encoding="utf-8")

        with (
            patch.object(self.repo.subprocess, "check_output", side_effect=["darwin\n", "arm64\n"]),
            patch.object(self.repo.subprocess, "run") as run_mock,
        ):
            self.repo.build_target("all", layout=layout)

        self.assertEqual(run_mock.call_count, 3)


if __name__ == "__main__":
    unittest.main()
