from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

import project_metadata


class ProjectMetadataTests(unittest.TestCase):
    def test_runtime_version_matches_package_pyproject(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        version = tomllib.loads(
            (repo_root / "packages" / "sinan-captcha" / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["version"]
        self.assertEqual(project_metadata.get_runtime_version(), version)


if __name__ == "__main__":
    unittest.main()
