from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.auto_train import opencode_commands


class AutoTrainOpenCodeCommandsTests(unittest.TestCase):
    def test_command_registry_is_fixed_to_four_commands(self) -> None:
        registry = opencode_commands.command_registry()

        self.assertEqual(
            tuple(registry.keys()),
            ("result-read", "judge-trial", "plan-dataset", "study-status"),
        )
        self.assertEqual(registry["result-read"].output_artifact, "result_summary.json")
        self.assertEqual(registry["judge-trial"].output_artifact, "decision.json")
        self.assertEqual(registry["plan-dataset"].output_artifact, "dataset_plan.json")
        self.assertEqual(registry["study-status"].output_artifact, "study_status.json")

    def test_headless_invocation_uses_command_flag_and_attached_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "one.json"
            second = root / "two.json"
            first.write_text("{}", encoding="utf-8")
            second.write_text("{}", encoding="utf-8")

            command = opencode_commands.build_headless_invocation(
                "judge-trial",
                arguments=["study_001", "group1", "trial_0004"],
                files=[first, second],
                attach_url="http://127.0.0.1:4096",
            )

            self.assertEqual(command[0:6], ["opencode", "run", "--format", "json", "--command", "judge-trial"])
            self.assertIn("--attach", command)
            self.assertIn("http://127.0.0.1:4096", command)
            self.assertEqual(command.count("--file"), 2)
            self.assertEqual(command[-4:], ["--", "study_001", "group1", "trial_0004"])

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
            for argument_name in spec.message_arguments:
                self.assertIn(argument_name, text)
            for file_name in spec.required_files:
                self.assertIn(file_name, text)
            self.assertIn(spec.output_artifact, text)


if __name__ == "__main__":
    unittest.main()
