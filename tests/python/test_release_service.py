from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.release.service import (
    BuildReleaseRequest,
    PackageWindowsRequest,
    PublishReleaseRequest,
    build_distribution,
    package_windows_bundle,
    publish_distribution,
)


class ReleaseServiceTests(unittest.TestCase):
    def test_build_distribution_invokes_uv_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            with patch("core.release.service.subprocess.run") as subprocess_run:
                subprocess_run.return_value.returncode = 0
                build_distribution(BuildReleaseRequest(project_dir=project_dir))

            subprocess_run.assert_called_once_with(["uv", "build"], check=True, cwd=project_dir)

    def test_publish_distribution_reads_token_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
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

    def test_package_windows_bundle_copies_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dist_dir = root / "dist"
            dist_dir.mkdir()
            wheel = dist_dir / "sinan_captcha-0.1.13-py3-none-any.whl"
            wheel.write_text("wheel", encoding="utf-8")

            generator_exe = root / "generator" / "dist" / "generator" / "windows-amd64" / "sinan-generator.exe"
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
