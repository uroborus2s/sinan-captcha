from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.auto_train import opencode_runtime


class AutoTrainOpenCodeRuntimeTests(unittest.TestCase):
    def test_subprocess_runner_uses_utf8_replace_and_normalizes_empty_streams(self) -> None:
        class Completed:
            stdout = None
            stderr = None
            returncode = 0

        with patch("core.auto_train.opencode_runtime.subprocess.run", return_value=Completed()) as run_mock:
            result = opencode_runtime.subprocess_runner(
                ["opencode", "run"],
                cwd=Path("/tmp"),
                timeout_seconds=5.0,
            )

        kwargs = run_mock.call_args.kwargs
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_runtime_emits_trace_with_command_markdown_and_attached_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            command_dir = root / ".opencode" / "commands"
            skill_dir = root / ".opencode" / "skills" / "training-judge"
            command_dir.mkdir(parents=True, exist_ok=True)
            skill_dir.mkdir(parents=True, exist_ok=True)
            (command_dir / "judge-trial.md").write_text("judge prompt body", encoding="utf-8")
            (skill_dir / "SKILL.md").write_text("training judge skill body", encoding="utf-8")
            attached = root / "result_summary.json"
            attached.write_text('{"metric": 0.85}', encoding="utf-8")
            traces: list[opencode_runtime.OpenCodeTraceRecord] = []

            def fake_runner(command: list[str], *, cwd: Path, timeout_seconds: float) -> opencode_runtime.OpenCodeInvocationResult:
                return opencode_runtime.OpenCodeInvocationResult(
                    stdout='{"decision":"RETUNE"}',
                    stderr="",
                    command=tuple(command),
                    returncode=0,
                )

            runtime = opencode_runtime.OpenCodeRuntimeAdapter(
                config=opencode_runtime.OpenCodeRuntimeConfig(
                    project_root=root,
                    trace_sink=traces.append,
                ),
                runner=fake_runner,
            )

            runtime.judge_trial(
                study_name="study_001",
                task="group1",
                trial_id="trial_0004",
                files=[attached],
            )

            self.assertEqual(len(traces), 1)
            trace = traces[0]
            self.assertEqual(trace.command_name, "judge-trial")
            self.assertEqual(trace.arguments, ("study_001", "group1", "trial_0004"))
            self.assertEqual(trace.command_markdown_text, "judge prompt body")
            self.assertEqual(trace.skill_markdown_text, "training judge skill body")
            self.assertEqual(len(trace.attached_files), 1)
            self.assertEqual(trace.attached_files[0].content_text, '{"metric": 0.85}')
            self.assertEqual(trace.stdout, '{"decision":"RETUNE"}')
            self.assertTrue(trace.success)

    def test_judge_trial_builds_command_and_uses_project_root(self) -> None:
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
            (skill_dir / "SKILL.md").write_text("Use training judge skill.", encoding="utf-8")
            captured: dict[str, object] = {}
            attached = root / "result_summary.json"
            attached.write_text("{}", encoding="utf-8")

            def fake_runner(command: list[str], *, cwd: Path, timeout_seconds: float) -> opencode_runtime.OpenCodeInvocationResult:
                captured["command"] = command
                captured["cwd"] = cwd
                captured["timeout_seconds"] = timeout_seconds
                return opencode_runtime.OpenCodeInvocationResult(
                    stdout='{"decision":"RETUNE"}',
                    stderr="",
                    command=tuple(command),
                    returncode=0,
                )

            runtime = opencode_runtime.OpenCodeRuntimeAdapter(
                config=opencode_runtime.OpenCodeRuntimeConfig(
                    project_root=root,
                    attach_url="http://127.0.0.1:4096",
                    model="gemma4",
                    timeout_seconds=30.0,
                ),
                runner=fake_runner,
            )

            result = runtime.judge_trial(
                study_name="study_001",
                task="group1",
                trial_id="trial_0004",
                files=[attached],
            )

            self.assertEqual(result.stdout, '{"decision":"RETUNE"}')
            self.assertEqual(captured["cwd"], root)
            self.assertEqual(captured["timeout_seconds"], 30.0)
            command = captured["command"]
            self.assertEqual(command[0:6], ["opencode", "run", "--format", "json", "--agent", "build"])
            self.assertIn("--attach", command)
            self.assertIn("--model", command)
            self.assertNotIn("--file", command)
            self.assertEqual(command[-2], "--")
            self.assertIn("Judge study_001 group1 trial_0004 and return only JSON.", command[-1])
            self.assertIn(str(attached), command[-1])

    def test_result_read_builds_expected_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            command_dir = root / ".opencode" / "commands"
            skill_dir = root / ".opencode" / "skills" / "result-reader"
            command_dir.mkdir(parents=True, exist_ok=True)
            skill_dir.mkdir(parents=True, exist_ok=True)
            (command_dir / "result-read.md").write_text(
                "---\ndescription: Read trial artifacts and return result_summary.json\nagent: build\n---\n\n"
                "Summarize $1 $2 $3 $4 $5 $6 and return only JSON.",
                encoding="utf-8",
            )
            (skill_dir / "SKILL.md").write_text("Use result reader skill.", encoding="utf-8")
            captured: dict[str, object] = {}
            test_file = root / "test.json"
            test_file.write_text("{}", encoding="utf-8")

            def fake_runner(command: list[str], *, cwd: Path, timeout_seconds: float) -> opencode_runtime.OpenCodeInvocationResult:
                captured["command"] = command
                return opencode_runtime.OpenCodeInvocationResult(
                    stdout='{"study_name":"study_001"}',
                    stderr="",
                    command=tuple(command),
                    returncode=0,
                )

            runtime = opencode_runtime.OpenCodeRuntimeAdapter(
                config=opencode_runtime.OpenCodeRuntimeConfig(project_root=root),
                runner=fake_runner,
            )
            runtime.result_read(
                study_name="study_001",
                task="group1",
                trial_id="trial_0004",
                dataset_version="firstpass_r0004",
                train_name="trial_0004",
                primary_metric="map50_95",
                files=[test_file],
            )

            command = captured["command"]
            self.assertEqual(command[0:6], ["opencode", "run", "--format", "json", "--agent", "build"])
            self.assertEqual(command[-2], "--")
            self.assertIn("Summarize study_001 group1 trial_0004 firstpass_r0004 trial_0004 map50_95 and return only JSON.", command[-1])

    def test_study_status_builds_expected_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            command_dir = root / ".opencode" / "commands"
            skill_dir = root / ".opencode" / "skills" / "study-archivist"
            command_dir.mkdir(parents=True, exist_ok=True)
            skill_dir.mkdir(parents=True, exist_ok=True)
            (command_dir / "study-status.md").write_text(
                "---\ndescription: Summarize the current study and return study_status.json\nagent: build\n---\n\n"
                "Summarize study $1 task $2 and return only JSON.",
                encoding="utf-8",
            )
            (skill_dir / "SKILL.md").write_text("Use study archivist skill.", encoding="utf-8")
            captured: dict[str, object] = {}
            study_file = root / "study.json"
            leaderboard_file = root / "leaderboard.json"
            study_file.write_text("{}", encoding="utf-8")
            leaderboard_file.write_text("{}", encoding="utf-8")

            def fake_runner(command: list[str], *, cwd: Path, timeout_seconds: float) -> opencode_runtime.OpenCodeInvocationResult:
                captured["command"] = command
                return opencode_runtime.OpenCodeInvocationResult(
                    stdout='{"study_name":"study_001"}',
                    stderr="",
                    command=tuple(command),
                    returncode=0,
                )

            runtime = opencode_runtime.OpenCodeRuntimeAdapter(
                config=opencode_runtime.OpenCodeRuntimeConfig(project_root=root),
                runner=fake_runner,
            )
            runtime.study_status(
                study_name="study_001",
                task="group1",
                files=[study_file, leaderboard_file],
            )

            command = captured["command"]
            self.assertEqual(command[0:6], ["opencode", "run", "--format", "json", "--agent", "build"])
            self.assertEqual(command[-2], "--")
            self.assertIn("Summarize study study_001 task group1 and return only JSON.", command[-1])

    def test_plan_dataset_builds_expected_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            command_dir = root / ".opencode" / "commands"
            skill_dir = root / ".opencode" / "skills" / "dataset-planner"
            command_dir.mkdir(parents=True, exist_ok=True)
            skill_dir.mkdir(parents=True, exist_ok=True)
            (command_dir / "plan-dataset.md").write_text(
                "---\ndescription: Plan the next dataset action and return dataset_plan.json\nagent: build\n---\n\n"
                "Plan dataset for $1 $2 $3 and return only JSON.",
                encoding="utf-8",
            )
            (skill_dir / "SKILL.md").write_text("Use dataset planner skill.", encoding="utf-8")
            captured: dict[str, object] = {}
            summary_file = root / "result_summary.json"
            summary_file.write_text("{}", encoding="utf-8")

            def fake_runner(command: list[str], *, cwd: Path, timeout_seconds: float) -> opencode_runtime.OpenCodeInvocationResult:
                captured["command"] = command
                return opencode_runtime.OpenCodeInvocationResult(
                    stdout='{"study_name":"study_001"}',
                    stderr="",
                    command=tuple(command),
                    returncode=0,
                )

            runtime = opencode_runtime.OpenCodeRuntimeAdapter(
                config=opencode_runtime.OpenCodeRuntimeConfig(project_root=root),
                runner=fake_runner,
            )
            runtime.plan_dataset(
                study_name="study_001",
                task="group1",
                trial_id="trial_0004",
                files=[summary_file],
            )

            command = captured["command"]
            self.assertEqual(command[0:6], ["opencode", "run", "--format", "json", "--agent", "build"])
            self.assertEqual(command[-2], "--")
            self.assertIn("Plan dataset for study_001 group1 trial_0004 and return only JSON.", command[-1])

    def test_runtime_raises_when_opencode_process_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            command_dir = root / ".opencode" / "commands"
            skill_dir = root / ".opencode" / "skills" / "training-judge"
            command_dir.mkdir(parents=True, exist_ok=True)
            skill_dir.mkdir(parents=True, exist_ok=True)
            (command_dir / "judge-trial.md").write_text("judge prompt body", encoding="utf-8")
            (skill_dir / "SKILL.md").write_text("training judge skill body", encoding="utf-8")
            attached = root / "result_summary.json"
            attached.write_text("{}", encoding="utf-8")
            traces: list[opencode_runtime.OpenCodeTraceRecord] = []

            def fake_runner(command: list[str], *, cwd: Path, timeout_seconds: float) -> opencode_runtime.OpenCodeInvocationResult:
                return opencode_runtime.OpenCodeInvocationResult(
                    stdout="",
                    stderr="invalid provider",
                    command=tuple(command),
                    returncode=2,
                )

            runtime = opencode_runtime.OpenCodeRuntimeAdapter(
                config=opencode_runtime.OpenCodeRuntimeConfig(project_root=root, trace_sink=traces.append),
                runner=fake_runner,
            )

            with self.assertRaises(opencode_runtime.OpenCodeRuntimeError) as ctx:
                runtime.judge_trial(
                    study_name="study_001",
                    task="group1",
                    trial_id="trial_0004",
                    files=[attached],
                )

            self.assertEqual(ctx.exception.command_name, "judge-trial")
            self.assertEqual(ctx.exception.returncode, 2)
            self.assertIn("opencode_command_failed", str(ctx.exception))
            self.assertEqual(len(traces), 1)
            self.assertFalse(traces[0].success)
            self.assertIn("opencode_command_failed", traces[0].error_message or "")
            self.assertEqual(traces[0].stderr, "invalid provider")

    def test_runtime_raises_on_timeout(self) -> None:
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
            (skill_dir / "SKILL.md").write_text("Use training judge skill.", encoding="utf-8")
            attached = root / "result_summary.json"
            attached.write_text("{}", encoding="utf-8")

            def fake_runner(command: list[str], *, cwd: Path, timeout_seconds: float) -> opencode_runtime.OpenCodeInvocationResult:
                raise subprocess.TimeoutExpired(command, timeout_seconds)

            runtime = opencode_runtime.OpenCodeRuntimeAdapter(
                config=opencode_runtime.OpenCodeRuntimeConfig(project_root=root, timeout_seconds=5.0),
                runner=fake_runner,
            )

            with self.assertRaises(opencode_runtime.OpenCodeRuntimeError) as ctx:
                runtime.judge_trial(
                    study_name="study_001",
                    task="group1",
                    trial_id="trial_0004",
                    files=[attached],
                )

            self.assertEqual(ctx.exception.command_name, "judge-trial")
            self.assertIn("opencode_timeout", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
