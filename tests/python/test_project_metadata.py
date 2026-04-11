from __future__ import annotations

import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import project_metadata


class ProjectMetadataTests(unittest.TestCase):
    def test_runtime_version_matches_package_pyproject(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        version = tomllib.loads(
            (repo_root / "packages" / "sinan-captcha" / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["version"]
        self.assertEqual(project_metadata.get_runtime_version(), version)

    def test_runtime_version_falls_back_to_installed_metadata_when_package_root_is_unavailable(self) -> None:
        with (
            patch("project_metadata.package_root", side_effect=ValueError("no source root")),
            patch("project_metadata.importlib.metadata.version", return_value="9.9.9") as version_mock,
        ):
            version = project_metadata.get_runtime_version()

        self.assertEqual(version, "9.9.9")
        version_mock.assert_called_once_with(project_metadata.PACKAGE_NAME)


if __name__ == "__main__":
    unittest.main()
