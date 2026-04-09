from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

import core


class ProjectMetadataTests(unittest.TestCase):
    def test_core_version_matches_root_pyproject(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        version = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        self.assertEqual(core.__version__, version)


if __name__ == "__main__":
    unittest.main()
