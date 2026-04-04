from __future__ import annotations

import unittest
from pathlib import Path

from core.auto_train import opencode_skills


class AutoTrainOpenCodeSkillsTests(unittest.TestCase):
    def test_skill_registry_is_fixed_to_four_skills(self) -> None:
        registry = opencode_skills.skill_registry()

        self.assertEqual(
            tuple(registry.keys()),
            ("result-reader", "training-judge", "dataset-planner", "study-archivist"),
        )
        self.assertEqual(registry["result-reader"].primary_output, "result_summary.json")
        self.assertEqual(registry["training-judge"].primary_output, "decision.json")
        self.assertEqual(registry["dataset-planner"].primary_output, "dataset_plan.json")
        self.assertEqual(registry["study-archivist"].primary_output, "study_status.json")

    def test_skill_files_exist_with_valid_frontmatter_and_boundaries(self) -> None:
        project_root = Path("/Users/uroborus/AiProject/sinan-captcha")
        registry = opencode_skills.skill_registry()

        for name, spec in registry.items():
            path = project_root / ".opencode" / "skills" / name / "SKILL.md"
            self.assertTrue(path.exists(), f"missing skill file: {path}")
            text = path.read_text(encoding="utf-8")
            self.assertIn(f"name: {name}", text)
            self.assertIn(f"description: {spec.description}", text)
            self.assertIn(spec.primary_output, text)
            self.assertIn("Do not run shell commands", text)
            self.assertIn("Return JSON", text)


if __name__ == "__main__":
    unittest.main()
