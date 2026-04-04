"""Stable OpenCode command contracts for autonomous training."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OpenCodeCommandSpec:
    name: str
    description: str
    message_arguments: tuple[str, ...]
    required_files: tuple[str, ...]
    optional_files: tuple[str, ...]
    output_artifact: str
    agent: str = "plan"
    subtask: bool = True

    def markdown_path(self, project_root: Path) -> Path:
        return project_root / ".opencode" / "commands" / f"{self.name}.md"


def command_registry() -> "OrderedDict[str, OpenCodeCommandSpec]":
    """Return the fixed V1 OpenCode command set for autonomous training."""

    registry: "OrderedDict[str, OpenCodeCommandSpec]" = OrderedDict()
    registry["result-read"] = OpenCodeCommandSpec(
        name="result-read",
        description="Read trial artifacts and return result_summary.json",
        message_arguments=("study_name", "task", "trial_id", "primary_metric"),
        required_files=("test.json",),
        optional_files=("evaluate.json", "best_trial.json", "recent result_summary.json"),
        output_artifact="result_summary.json",
    )
    registry["judge-trial"] = OpenCodeCommandSpec(
        name="judge-trial",
        description="Judge one summarized trial and return decision.json",
        message_arguments=("study_name", "task", "trial_id"),
        required_files=("study.json", "result_summary.json"),
        optional_files=("leaderboard.json", "decisions.jsonl"),
        output_artifact="decision.json",
    )
    registry["plan-dataset"] = OpenCodeCommandSpec(
        name="plan-dataset",
        description="Plan the next dataset action and return dataset_plan.json",
        message_arguments=("study_name", "task", "trial_id"),
        required_files=("result_summary.json",),
        optional_files=("leaderboard.json", "best_trial.json"),
        output_artifact="dataset_plan.json",
    )
    registry["study-status"] = OpenCodeCommandSpec(
        name="study-status",
        description="Summarize the current study and return study_status.json",
        message_arguments=("study_name", "task"),
        required_files=("study.json", "leaderboard.json"),
        optional_files=("best_trial.json", "decisions.jsonl"),
        output_artifact="study_status.json",
    )
    return registry


def get_command_spec(name: str) -> OpenCodeCommandSpec:
    """Return one registered command spec or raise on unsupported names."""

    registry = command_registry()
    try:
        return registry[name]
    except KeyError as exc:
        allowed = ", ".join(registry.keys())
        raise ValueError(f"unsupported OpenCode command: {name}; allowed: {allowed}") from exc


def build_headless_invocation(
    name: str,
    *,
    arguments: list[str],
    files: list[Path],
    attach_url: str | None = None,
    model: str | None = None,
) -> list[str]:
    """Build a stable ``opencode run`` invocation for one autonomous-training command."""

    spec = get_command_spec(name)
    if len(arguments) != len(spec.message_arguments):
        expected = ", ".join(spec.message_arguments)
        raise ValueError(f"{name} expects {len(spec.message_arguments)} arguments: {expected}")

    command = ["opencode", "run", "--command", spec.name, "--format", "json"]
    if attach_url is not None:
        command.extend(["--attach", attach_url])
    if model is not None:
        command.extend(["--model", model])
    for file in files:
        command.extend(["--file", str(file)])
    command.extend(arguments)
    return command
