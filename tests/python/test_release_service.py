from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from core.release.service import (
    BuildAllReleaseRequest,
    BuildGeneratorRequest,
    BuildReleaseRequest,
    BuildSolverRequest,
    PackageWindowsRequest,
    PublishReleaseRequest,
    build_all_distributions,
    build_generator_distribution,
    build_distribution,
    build_solver_distribution,
    package_windows_bundle,
    publish_distribution,
)


class ReleaseServiceTests(unittest.TestCase):
    def _write_project_pyproject(self, project_dir: Path, version: str) -> None:
        (project_dir / "pyproject.toml").write_text(
            textwrap.dedent(
                f"""
                [project]
                name = "sinan-captcha"
                version = "{version}"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def test_build_distribution_invokes_uv_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            dist_dir = project_dir / "dist"
            dist_dir.mkdir()
            (dist_dir / "stale.whl").write_text("old", encoding="utf-8")
            (dist_dir / ".gitignore").write_text("*\n", encoding="utf-8")
            with patch("core.release.service.subprocess.run") as subprocess_run:
                subprocess_run.return_value.returncode = 0
                build_distribution(BuildReleaseRequest(project_dir=project_dir))

            self.assertFalse((dist_dir / "stale.whl").exists())
            self.assertTrue((dist_dir / ".gitignore").exists())
            subprocess_run.assert_called_once_with(
                ["uv", "build", "--out-dir", "dist"],
                check=True,
                cwd=project_dir.resolve(),
            )

    def test_build_generator_distribution_cleans_target_dir_and_uses_resolved_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            generator_dir = project_dir / "generator"
            generator_dir.mkdir()
            (generator_dir / "go.mod").write_text("module example/generator\n", encoding="utf-8")
            output_dir = generator_dir / "dist" / "windows-amd64"
            output_dir.mkdir(parents=True)
            (output_dir / "stale.txt").write_text("old", encoding="utf-8")

            def fake_run(*args, **kwargs):
                if args and args[0] == ["go", "env", "GOOS", "GOARCH"]:
                    return subprocess.CompletedProcess(args[0], 0, stdout="windows\namd64\n")
                if args and args[0][:3] == ["go", "build", "-o"]:
                    Path(args[0][3]).write_text("exe", encoding="utf-8")
                return subprocess.CompletedProcess(args[0], 0)

            with patch("core.release.service.subprocess.run", side_effect=fake_run) as subprocess_run:
                current_dir = Path.cwd()
                os.chdir(project_dir)
                try:
                    build_generator_distribution(BuildGeneratorRequest(project_dir=Path(".")))
                finally:
                    os.chdir(current_dir)

            output_path = output_dir / "sinan-generator.exe"
            self.assertFalse((output_dir / "stale.txt").exists())
            self.assertTrue(output_path.exists())
            self.assertEqual(subprocess_run.call_args_list[0].args[0], ["go", "env", "GOOS", "GOARCH"])
            self.assertEqual(
                subprocess_run.call_args_list[1].args[0],
                ["go", "build", "-o", str(output_path.resolve()), "./cmd/sinan-generator"],
            )
            self.assertEqual(subprocess_run.call_args_list[1].kwargs["cwd"], generator_dir.resolve())
            self.assertEqual(subprocess_run.call_args_list[1].kwargs["env"]["GOOS"], "windows")
            self.assertEqual(subprocess_run.call_args_list[1].kwargs["env"]["GOARCH"], "amd64")

    def test_build_generator_distribution_raises_when_binary_is_missing_after_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            generator_dir = project_dir / "generator"
            generator_dir.mkdir()
            (generator_dir / "go.mod").write_text("module example/generator\n", encoding="utf-8")

            def fake_run(*args, **kwargs):
                if args and args[0] == ["go", "env", "GOOS", "GOARCH"]:
                    return subprocess.CompletedProcess(args[0], 0, stdout="windows\namd64\n")
                return subprocess.CompletedProcess(args[0], 0)

            with patch("core.release.service.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(ValueError, "expected generator binary was not created"):
                    build_generator_distribution(BuildGeneratorRequest(project_dir=project_dir))

    def test_build_solver_distribution_invokes_uv_build_in_solver_dist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            solver_dir = project_dir / "solver"
            solver_dir.mkdir()
            (solver_dir / "pyproject.toml").write_text("[project]\nname='solver'\nversion='0.0.0'\n", encoding="utf-8")
            dist_dir = solver_dir / "dist"
            dist_dir.mkdir()
            (dist_dir / "stale.whl").write_text("old", encoding="utf-8")
            (dist_dir / ".gitignore").write_text("*\n", encoding="utf-8")
            with patch("core.release.service.subprocess.run") as subprocess_run:
                subprocess_run.return_value.returncode = 0
                build_solver_distribution(BuildSolverRequest(project_dir=project_dir))

            self.assertFalse((dist_dir / "stale.whl").exists())
            self.assertTrue((dist_dir / ".gitignore").exists())
            subprocess_run.assert_called_once_with(
                ["uv", "build", "--out-dir", "dist"],
                check=True,
                cwd=solver_dir.resolve(),
            )

    def test_build_all_distributions_runs_three_build_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            request = BuildAllReleaseRequest(project_dir=project_dir, goos="windows", goarch="amd64")

            with patch("core.release.service.build_distribution") as build_root:
                with patch("core.release.service.build_generator_distribution") as build_generator:
                    with patch("core.release.service.build_solver_distribution") as build_solver:
                        build_all_distributions(request)

            build_root.assert_called_once_with(BuildReleaseRequest(project_dir=project_dir.resolve()))
            build_generator.assert_called_once_with(
                BuildGeneratorRequest(project_dir=project_dir.resolve(), goos="windows", goarch="amd64")
            )
            build_solver.assert_called_once_with(BuildSolverRequest(project_dir=project_dir.resolve()))

    def test_publish_distribution_reads_token_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            package_version = "9.8.7"
            self._write_project_pyproject(project_dir, package_version)
            dist_dir = project_dir / "dist"
            dist_dir.mkdir()
            (dist_dir / f"sinan_captcha-{package_version}-py3-none-any.whl").write_text("wheel", encoding="utf-8")
            (dist_dir / f"sinan_captcha-{package_version}.tar.gz").write_text("sdist", encoding="utf-8")
            (dist_dir / "sinan_captcha-0.1.13-py3-none-any.whl").write_text("old", encoding="utf-8")
            request = PublishReleaseRequest(project_dir=project_dir, repository="pypi", token_env="PYPI_TOKEN")
            env = os.environ.copy()
            env["PYPI_TOKEN"] = "secret-token"
            with patch.dict(os.environ, env, clear=True):
                with patch("core.release.service.subprocess.run") as subprocess_run:
                    subprocess_run.return_value.returncode = 0
                    publish_distribution(request)

            command = subprocess_run.call_args.kwargs["args"]
            self.assertIn("--publish-url", command)
            self.assertIn("https://upload.pypi.org/legacy/", command)
            self.assertEqual(subprocess_run.call_args.kwargs["env"]["UV_PUBLISH_TOKEN"], "secret-token")
            self.assertTrue(any(item.endswith(f"sinan_captcha-{package_version}-py3-none-any.whl") for item in command))
            self.assertTrue(any(item.endswith(f"sinan_captcha-{package_version}.tar.gz") for item in command))
            self.assertFalse(any(item.endswith("sinan_captcha-0.1.13-py3-none-any.whl") for item in command))

    def test_package_windows_bundle_copies_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dist_dir = root / "dist"
            dist_dir.mkdir()
            package_version = tomllib.loads(
                (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8")
            )["project"]["version"]
            wheel = dist_dir / f"sinan_captcha-{package_version}-py3-none-any.whl"
            wheel.write_text("wheel", encoding="utf-8")

            generator_exe = root / "generator" / "dist" / "windows-amd64" / "sinan-generator.exe"
            generator_exe.parent.mkdir(parents=True)
            generator_exe.write_text("exe", encoding="utf-8")
            bundle_dir = root / "bundles" / "solver" / "current"
            manifest_path = bundle_dir / "manifest.json"
            model_path = bundle_dir / "models" / "group2" / "locator" / "model.pt"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text('{"bundle_version":"bundle_20260405"}', encoding="utf-8")
            model_path.write_text("model", encoding="utf-8")

            output_dir = root / "bundle"
            package_windows_bundle(
                PackageWindowsRequest(
                    project_dir=root,
                    generator_exe=generator_exe,
                    output_dir=output_dir,
                    bundle_dir=bundle_dir,
                )
            )

            self.assertTrue((output_dir / "python" / wheel.name).exists())
            self.assertTrue((output_dir / "generator" / "sinan-generator.exe").exists())
            self.assertTrue((output_dir / "bundle" / "manifest.json").exists())
            self.assertTrue((output_dir / "bundle" / "models" / "group2" / "locator" / "model.pt").exists())
            self.assertTrue((output_dir / "README-交付包说明.txt").exists())
            readme = (output_dir / "README-交付包说明.txt").read_text(encoding="utf-8")
            self.assertIn(".\\sinan-generator.exe", readme)
            self.assertIn("firstpass 预设一次生成 200 条", readme)
            self.assertIn("bundle\\manifest.json", readme)
