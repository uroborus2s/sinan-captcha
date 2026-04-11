from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from common import paths


class CommonPathsTests(unittest.TestCase):
    def test_repository_root_falls_back_to_current_directory_when_repo_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            with patch("common.paths.package_root", side_effect=ValueError("no package root")):
                resolved = paths.repository_root(cwd)

        self.assertEqual(resolved, cwd.resolve())

    def test_workspace_paths_falls_back_to_current_directory_in_installed_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            with patch("common.paths.package_root", side_effect=ValueError("no package root")):
                result = paths.workspace_paths(cwd)

        self.assertEqual(result.repo_root, cwd.resolve())
        self.assertEqual(result.package_root, cwd.resolve())
        self.assertEqual(result.work_root, cwd.resolve())
        self.assertEqual(result.materials_dir, cwd.resolve() / "materials")
        self.assertEqual(result.reports_dir, cwd.resolve() / "reports")
        self.assertEqual(result.cache_dir, cwd.resolve() / ".cache")


if __name__ == "__main__":
    unittest.main()
