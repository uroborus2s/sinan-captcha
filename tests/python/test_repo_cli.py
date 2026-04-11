from __future__ import annotations

import io
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import repo_tools.repo_cli as repo_cli


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

    def test_main_dispatches_publish_sinan(self) -> None:
        layout = self._make_layout()
        with patch("repo_tools.repo_cli.publish_sinan_distribution") as publish_mock:
            code = repo_cli.main(["publish-sinan"], layout=layout)

        self.assertEqual(code, 0)
        publish_mock.assert_called_once_with(
            repo_cli.PublishReleaseRequest(project_dir=layout.repo_root, token_env=None)
        )

    def test_main_dispatches_publish_solver(self) -> None:
        layout = self._make_layout()
        with patch("repo_tools.repo_cli.publish_solver_distribution") as publish_mock:
            code = repo_cli.main(["publish-solver"], layout=layout)

        self.assertEqual(code, 0)
        publish_mock.assert_called_once_with(
            repo_cli.PublishReleaseRequest(project_dir=layout.repo_root, token_env=None)
        )

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

    def test_default_layout_prefers_current_working_dir_repo_root(self) -> None:
        layout = self._make_layout()
        current_dir = Path.cwd()
        try:
            os.chdir(layout.repo_root)
            detected = repo_cli.default_layout()
        finally:
            os.chdir(current_dir)

        self.assertEqual(detected.repo_root, layout.repo_root.resolve())
        self.assertEqual(detected.sinan_dir, layout.sinan_dir.resolve())
        self.assertEqual(detected.generator_dir, layout.generator_dir.resolve())
        self.assertEqual(detected.solver_dir, layout.solver_dir.resolve())


if __name__ == "__main__":
    unittest.main()
