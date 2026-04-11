from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import repo_cli


class RepoCliTests(unittest.TestCase):
    def _make_layout(self) -> repo_cli.RepoLayout:
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
        return repo_cli.RepoLayout(
            repo_root=root,
            packages_dir=packages_dir,
            sinan_dir=sinan_dir,
            solver_dir=solver_dir,
            generator_dir=generator_dir,
        )

    def test_main_dispatches_publish(self) -> None:
        layout = self._make_layout()
        with patch("repo_cli.publish_distribution") as publish_mock:
            code = repo_cli.main(["publish"], layout=layout)

        self.assertEqual(code, 0)
        publish_mock.assert_called_once_with(repo_cli.PublishRequest(project_dir=layout.repo_root, token_env=None))

    def test_publish_uses_pypi_token_by_default(self) -> None:
        layout = self._make_layout()
        (layout.sinan_dir / "pyproject.toml").write_text(
            "[project]\nname='sinan-captcha'\nversion='1.2.3'\n",
            encoding="utf-8",
        )
        dist_dir = layout.sinan_dir / "dist"
        dist_dir.mkdir()
        (dist_dir / "sinan_captcha-1.2.3-py3-none-any.whl").write_text("wheel", encoding="utf-8")
        (dist_dir / "sinan_captcha-1.2.3.tar.gz").write_text("sdist", encoding="utf-8")

        with (
            patch.dict(repo_cli.os.environ, {"PYPI_TOKEN": "secret"}, clear=True),
            patch.object(repo_cli.subprocess, "run") as run_mock,
        ):
            repo_cli.publish_distribution(repo_cli.PublishRequest(project_dir=layout.repo_root))

        self.assertEqual(run_mock.call_args.kwargs["env"]["UV_PUBLISH_TOKEN"], "secret")
        self.assertIn("https://upload.pypi.org/legacy/", run_mock.call_args.kwargs["args"])

    def test_publish_falls_back_to_uv_publish_token(self) -> None:
        layout = self._make_layout()
        (layout.sinan_dir / "pyproject.toml").write_text(
            "[project]\nname='sinan-captcha'\nversion='1.2.3'\n",
            encoding="utf-8",
        )
        dist_dir = layout.sinan_dir / "dist"
        dist_dir.mkdir()
        (dist_dir / "sinan_captcha-1.2.3-py3-none-any.whl").write_text("wheel", encoding="utf-8")
        (dist_dir / "sinan_captcha-1.2.3.tar.gz").write_text("sdist", encoding="utf-8")

        with (
            patch.dict(repo_cli.os.environ, {"UV_PUBLISH_TOKEN": "secret"}, clear=True),
            patch.object(repo_cli.subprocess, "run") as run_mock,
        ):
            repo_cli.publish_distribution(repo_cli.PublishRequest(project_dir=layout.repo_root))

        self.assertEqual(run_mock.call_args.kwargs["env"]["UV_PUBLISH_TOKEN"], "secret")

    def test_main_prints_paths(self) -> None:
        layout = self._make_layout()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = repo_cli.main(["paths"], layout=layout)

        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn(f"repo_root={layout.repo_root}", output)
        self.assertIn(f"sinan_captcha={layout.sinan_dir}", output)
        self.assertIn(f"generator={layout.generator_dir}", output)
        self.assertIn(f"solver={layout.solver_dir}", output)


if __name__ == "__main__":
    unittest.main()
