"""Stable OpenCode skill contracts for autonomous training."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OpenCodeSkillSpec:
    name: str
    description: str
    primary_output: str

    def markdown_path(self, project_root: Path) -> Path:
        return project_root / ".opencode" / "skills" / self.name / "SKILL.md"


def skill_registry() -> "OrderedDict[str, OpenCodeSkillSpec]":
    """Return the fixed V1 OpenCode skill set for autonomous training."""

    registry: "OrderedDict[str, OpenCodeSkillSpec]" = OrderedDict()
    registry["result-reader"] = OpenCodeSkillSpec(
        name="result-reader",
        description=(
            "Use when a command or agent needs to compress test and evaluate artifacts into "
            "result_summary.json for one trial."
        ),
        primary_output="result_summary.json",
    )
    registry["training-judge"] = OpenCodeSkillSpec(
        name="training-judge",
        description=(
            "Use when a command or agent needs to judge one summarized trial and return "
            "decision.json using the allowed action set only."
        ),
        primary_output="decision.json",
    )
    registry["dataset-planner"] = OpenCodeSkillSpec(
        name="dataset-planner",
        description=(
            "Use when a command or agent needs to turn weak classes and failure patterns into "
            "dataset_plan.json without choosing training parameters."
        ),
        primary_output="dataset_plan.json",
    )
    registry["study-archivist"] = OpenCodeSkillSpec(
        name="study-archivist",
        description=(
            "Use when a command or agent needs to summarize study state into study_status.json "
            "or archive advice from study and leaderboard artifacts."
        ),
        primary_output="study_status.json",
    )
    return registry
