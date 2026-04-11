from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_release import (
    BuildAllReleaseRequest,
    BuildGeneratorRequest,
    BuildReleaseRequest,
    BuildSolverRequest,
    PackageWindowsRequest,
    PublishReleaseRequest,
    StageSolverAssetsRequest,
    build_all_distributions,
    build_generator_distribution,
    build_distribution,
    build_solver_distribution,
    package_windows_bundle,
    publish_distribution,
    stage_solver_assets,
)


class ReleaseServiceTests(unittest.TestCase):
    def _write_package_pyproject(self, project_dir: Path, version: str) -> None:
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

    def _create_repo_layout(self, root: Path) -> tuple[Path, Path, Path]:
        sinan_dir = root / "packages" / "sinan-captcha"
        solver_dir = root / "packages" / "solver"
        generator_dir = root / "packages" / "generator"
        (sinan_dir / "src").mkdir(parents=True, exist_ok=True)
        (sinan_dir / "src" / "cli.py").write_text("def main(argv=None):\n    return 0\n", encoding="utf-8")
        solver_dir.mkdir(parents=True, exist_ok=True)
        generator_dir.mkdir(parents=True, exist_ok=True)
        return sinan_dir, solver_dir, generator_dir

    def test_build_distribution_invokes_uv_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sinan_dir, _, _ = self._create_repo_layout(project_dir)
            self._write_package_pyproject(sinan_dir, "0.0.0")
            source_root = project_dir / ".opencode" / "commands"
            source_root.mkdir(parents=True)
            (source_root / "judge-trial.md").write_text("judge", encoding="utf-8")
            dist_dir = sinan_dir / "dist"
            dist_dir.mkdir()
            (dist_dir / "stale.whl").write_text("old", encoding="utf-8")
            (dist_dir / ".gitignore").write_text("*\n", encoding="utf-8")
            with patch("repo_release._build_setuptools_distribution") as build_dist:
                build_distribution(BuildReleaseRequest(project_dir=project_dir))

            self.assertFalse((dist_dir / "stale.whl").exists())
            self.assertTrue((dist_dir / ".gitignore").exists())
            build_dist.assert_called_once_with(package_dir=sinan_dir.resolve(), output_dir=dist_dir.resolve())

    def test_build_generator_distribution_cleans_target_dir_and_uses_resolved_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            _, _, generator_dir = self._create_repo_layout(project_dir)
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

            with patch("repo_release.subprocess.run", side_effect=fake_run) as subprocess_run:
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
            _, _, generator_dir = self._create_repo_layout(project_dir)
            (generator_dir / "go.mod").write_text("module example/generator\n", encoding="utf-8")

            def fake_run(*args, **kwargs):
                if args and args[0] == ["go", "env", "GOOS", "GOARCH"]:
                    return subprocess.CompletedProcess(args[0], 0, stdout="windows\namd64\n")
                return subprocess.CompletedProcess(args[0], 0)

            with patch("repo_release.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(ValueError, "expected generator binary was not created"):
                    build_generator_distribution(BuildGeneratorRequest(project_dir=project_dir))

    def test_build_solver_distribution_invokes_uv_build_in_solver_dist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            _, solver_dir, _ = self._create_repo_layout(project_dir)
            (solver_dir / "pyproject.toml").write_text("[project]\nname='solver'\nversion='0.0.0'\n", encoding="utf-8")
            dist_dir = solver_dir / "dist"
            dist_dir.mkdir()
            (dist_dir / "stale.whl").write_text("old", encoding="utf-8")
            (dist_dir / ".gitignore").write_text("*\n", encoding="utf-8")
            with patch("repo_release._build_setuptools_distribution") as build_dist:
                build_solver_distribution(BuildSolverRequest(project_dir=project_dir))

            self.assertFalse((dist_dir / "stale.whl").exists())
            self.assertTrue((dist_dir / ".gitignore").exists())
            build_dist.assert_called_once_with(package_dir=solver_dir.resolve(), output_dir=dist_dir.resolve())

    def test_stage_and_clear_repo_opencode_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sinan_dir, _, _ = self._create_repo_layout(project_dir)
            source_root = project_dir / ".opencode" / "commands"
            source_root.mkdir(parents=True)
            (source_root / "judge-trial.md").write_text("judge", encoding="utf-8")

            staged = __import__("repo_release", fromlist=["_stage_repo_opencode_assets"])._stage_repo_opencode_assets(
                sinan_dir
            )

            self.assertEqual(
                staged,
                sinan_dir / "src" / "auto_train" / "resources" / "opencode",
            )
            self.assertEqual(
                (staged / "commands" / "judge-trial.md").read_text(encoding="utf-8"),
                "judge",
            )

            __import__("repo_release", fromlist=["_clear_staged_opencode_assets"])._clear_staged_opencode_assets(
                sinan_dir
            )
            self.assertFalse(staged.exists())

    def test_build_all_distributions_runs_three_build_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            self._create_repo_layout(project_dir)
            request = BuildAllReleaseRequest(project_dir=project_dir, goos="windows", goarch="amd64")

            with patch("repo_release.build_distribution") as build_root:
                with patch("repo_release.build_generator_distribution") as build_generator:
                    with patch("repo_release.build_solver_distribution") as build_solver:
                        build_all_distributions(request)

            build_root.assert_called_once_with(BuildReleaseRequest(project_dir=project_dir.resolve()))
            build_generator.assert_called_once_with(
                BuildGeneratorRequest(project_dir=project_dir.resolve(), goos="windows", goarch="amd64")
            )
            build_solver.assert_called_once_with(BuildSolverRequest(project_dir=project_dir.resolve()))

    def test_stage_solver_assets_copies_models_metadata_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            _, solver_dir, _ = self._create_repo_layout(project_dir)
            resource_dir = solver_dir / "resources"
            models_dir = resource_dir / "models"
            metadata_dir = resource_dir / "metadata"
            models_dir.mkdir(parents=True)
            metadata_dir.mkdir(parents=True)
            (models_dir / "README.md").write_text("keep", encoding="utf-8")
            (metadata_dir / "README.md").write_text("keep", encoding="utf-8")
            (models_dir / "stale.onnx").write_text("old", encoding="utf-8")
            (metadata_dir / "stale.json").write_text("old", encoding="utf-8")

            asset_dir = project_dir / "dist" / "solver-assets" / "20260410"
            source_models_dir = asset_dir / "models"
            source_metadata_dir = asset_dir / "metadata"
            source_models_dir.mkdir(parents=True)
            source_metadata_dir.mkdir(parents=True)
            (asset_dir / "manifest.json").write_text('{"asset_version":"20260410"}', encoding="utf-8")
            (source_models_dir / "slider_gap_locator.onnx").write_text("onnx", encoding="utf-8")
            (source_metadata_dir / "slider_gap_locator.json").write_text('{"model_id":"slider_gap_locator"}', encoding="utf-8")
            (source_metadata_dir / "export_report.json").write_text('{"group2_run":"best"}', encoding="utf-8")

            stage_solver_assets(
                StageSolverAssetsRequest(
                    project_dir=project_dir,
                    asset_dir=asset_dir,
                )
            )

            self.assertTrue((resource_dir / "manifest.json").exists())
            self.assertTrue((models_dir / "slider_gap_locator.onnx").exists())
            self.assertTrue((metadata_dir / "slider_gap_locator.json").exists())
            self.assertTrue((metadata_dir / "export_report.json").exists())
            self.assertFalse((models_dir / "stale.onnx").exists())
            self.assertFalse((metadata_dir / "stale.json").exists())
            self.assertTrue((models_dir / "README.md").exists())
            self.assertTrue((metadata_dir / "README.md").exists())

    def test_publish_distribution_reads_token_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            package_version = "9.8.7"
            sinan_dir, _, _ = self._create_repo_layout(project_dir)
            self._write_package_pyproject(sinan_dir, package_version)
            dist_dir = sinan_dir / "dist"
            dist_dir.mkdir()
            (dist_dir / f"sinan_captcha-{package_version}-py3-none-any.whl").write_text("wheel", encoding="utf-8")
            (dist_dir / f"sinan_captcha-{package_version}.tar.gz").write_text("sdist", encoding="utf-8")
            (dist_dir / "sinan_captcha-0.1.13-py3-none-any.whl").write_text("old", encoding="utf-8")
            request = PublishReleaseRequest(project_dir=project_dir, token_env="PYPI_TOKEN")
            env = os.environ.copy()
            env["PYPI_TOKEN"] = "secret-token"
            with patch.dict(os.environ, env, clear=True):
                with patch("repo_release.subprocess.run") as subprocess_run:
                    subprocess_run.return_value.returncode = 0
                    publish_distribution(request)

            command = subprocess_run.call_args.kwargs["args"]
            self.assertIn("--publish-url", command)
            self.assertIn("https://upload.pypi.org/legacy/", command)
            self.assertEqual(subprocess_run.call_args.kwargs["env"]["UV_PUBLISH_TOKEN"], "secret-token")
            self.assertEqual(
                subprocess_run.call_args.kwargs["env"]["UV_CACHE_DIR"],
                str((project_dir / "work_home" / ".cache" / "uv").resolve()),
            )
            self.assertEqual(
                subprocess_run.call_args.kwargs["env"]["GOCACHE"],
                str((project_dir / "work_home" / ".cache" / "go").resolve()),
            )
            self.assertTrue(any(item.endswith(f"sinan_captcha-{package_version}-py3-none-any.whl") for item in command))
            self.assertTrue(any(item.endswith(f"sinan_captcha-{package_version}.tar.gz") for item in command))
            self.assertFalse(any(item.endswith("sinan_captcha-0.1.13-py3-none-any.whl") for item in command))

    def test_package_windows_bundle_copies_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sinan_dir, _, generator_dir = self._create_repo_layout(root)
            dist_dir = sinan_dir / "dist"
            dist_dir.mkdir()
            package_version = tomllib.loads(
                (
                    Path(__file__).resolve().parents[2]
                    / "packages"
                    / "sinan-captcha"
                    / "pyproject.toml"
                ).read_text(encoding="utf-8")
            )["project"]["version"]
            wheel = dist_dir / f"sinan_captcha-{package_version}-py3-none-any.whl"
            wheel.write_text("wheel", encoding="utf-8")

            generator_exe = generator_dir / "dist" / "windows-amd64" / "sinan-generator.exe"
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
