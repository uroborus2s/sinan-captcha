from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_train import opencode_assets


class OpenCodeAssetsTests(unittest.TestCase):
    def test_stage_repo_opencode_assets_uses_single_source_and_can_be_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / ".opencode"
            package_dir = root / "packages" / "sinan-captcha"
            command_path = source_root / "commands" / "judge-trial.md"
            skill_path = source_root / "skills" / "training-judge" / "SKILL.md"
            command_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            package_dir.mkdir(parents=True, exist_ok=True)
            command_path.write_text("judge command", encoding="utf-8")
            skill_path.write_text("judge skill", encoding="utf-8")

            staged_root = opencode_assets.stage_repo_opencode_assets(package_dir, source_root=source_root)

            self.assertEqual(
                staged_root,
                (package_dir / "src" / "auto_train" / "resources" / "opencode").resolve(),
            )
            self.assertEqual(
                (staged_root / "commands" / "judge-trial.md").read_text(encoding="utf-8"),
                "judge command",
            )
            self.assertEqual(
                (staged_root / "skills" / "training-judge" / "SKILL.md").read_text(encoding="utf-8"),
                "judge skill",
            )

            opencode_assets.clear_staged_opencode_assets(package_dir)

            self.assertFalse(staged_root.exists())

    def test_resolve_opencode_assets_root_falls_back_to_packaged_assets_when_repo_root_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            packaged_root = Path(tmpdir) / "resources" / "opencode"
            (packaged_root / "commands").mkdir(parents=True, exist_ok=True)
            (packaged_root / "commands" / "judge-trial.md").write_text("judge command", encoding="utf-8")

            with (
                patch("auto_train.opencode_assets.repo_opencode_root", return_value=None),
                patch("auto_train.opencode_assets.packaged_opencode_root", return_value=packaged_root),
            ):
                resolved = opencode_assets.resolve_opencode_assets_root()

            self.assertEqual(resolved, packaged_root)


if __name__ == "__main__":
    unittest.main()
