from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from auto_train import opencode_commands


class AutoTrainOpenCodeCommandsTests(unittest.TestCase):
    def test_command_registry_is_fixed_to_six_commands(self) -> None:
        registry = opencode_commands.command_registry()

        self.assertEqual(
            tuple(registry.keys()),
            (
                "result-read",
                "judge-trial",
                "review-embedder",
                "plan-dataset",
                "plan-retune",
                "study-status",
            ),
        )
        self.assertEqual(registry["result-read"].output_artifact, "result_summary.json")
        self.assertEqual(registry["judge-trial"].output_artifact, "decision.json")
        self.assertEqual(registry["review-embedder"].output_artifact, "embedder_review.json")
        self.assertEqual(registry["plan-dataset"].output_artifact, "dataset_plan.json")
        self.assertEqual(registry["plan-retune"].output_artifact, "retune_plan.json")
        self.assertEqual(registry["study-status"].output_artifact, "study_status.json")

    def test_headless_invocation_inlines_files_into_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            command_dir = root / ".opencode" / "commands"
            skill_dir = root / ".opencode" / "skills" / "training-judge"
            command_dir.mkdir(parents=True, exist_ok=True)
            skill_dir.mkdir(parents=True, exist_ok=True)
            (command_dir / "judge-trial.md").write_text(
                "---\ndescription: Judge one summarized trial and return decision.json\nagent: build\n---\n\n"
                "Judge $1 $2 $3 and return only JSON.",
                encoding="utf-8",
            )
            (skill_dir / "SKILL.md").write_text(
                "---\nname: training-judge\n---\n\nUse training judge skill.\nReturn JSON only.",
                encoding="utf-8",
            )
            first = root / "one.json"
            second = root / "two.json"
            first.write_text("{}", encoding="utf-8")
            second.write_text("{}", encoding="utf-8")

            command = opencode_commands.build_headless_invocation(
                "judge-trial",
                arguments=["study_001", "group1", "trial_0004"],
                files=[first, second],
                project_root=root,
                attach_url="http://127.0.0.1:4096",
            )

            self.assertEqual(command[0:6], ["opencode", "run", "--format", "json", "--agent", "build"])
            self.assertIn("--attach", command)
            self.assertIn("http://127.0.0.1:4096", command)
            self.assertNotIn("--file", command)
            self.assertEqual(command[-2], "--")
            self.assertIn("Judge study_001 group1 trial_0004 and return only JSON.", command[-1])
            self.assertIn("Local skill guidance (`training-judge`", command[-1])
            self.assertIn("Use training judge skill.", command[-1])
            self.assertIn("Return JSON only.", command[-1])
            self.assertIn("Tool usage constraints:", command[-1])
            self.assertIn("Do not call the `skill` tool.", command[-1])
            self.assertIn("do not call any file, search, or glob tools", command[-1])
            self.assertNotIn("call the `skill` tool with exact name `training-judge`", command[-1])
            self.assertIn("--- Begin file:", command[-1])
            self.assertIn(str(first), command[-1])
            self.assertIn(str(second), command[-1])

    def test_markdown_command_files_match_registered_specs(self) -> None:
        project_root = Path("/Users/uroborus/AiProject/sinan-captcha")
        registry = opencode_commands.command_registry()

        for name, spec in registry.items():
            path = project_root / ".opencode" / "commands" / f"{name}.md"
            self.assertTrue(path.exists(), f"missing command file: {path}")
            text = path.read_text(encoding="utf-8")
            self.assertIn(f"description: {spec.description}", text)
            self.assertIn("agent: build", text)
            self.assertNotIn("subtask: true", text)
            self.assertIn("Return only one JSON object", text)
            self.assertNotIn("using the `skill` tool", text)
            for argument_name in spec.message_arguments:
                self.assertIn(argument_name, text)
            for file_name in spec.required_files:
                self.assertIn(file_name, text)
            self.assertIn(spec.output_artifact, text)


if __name__ == "__main__":
    unittest.main()
