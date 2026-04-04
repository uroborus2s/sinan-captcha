"""Recovery planning helpers based on sequential study artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_RECOVERY_RULES: tuple[tuple[str, str, str], ...] = (
    ("input.json", "PLAN", "PLAN"),
    ("dataset.json", "BUILD_DATASET", "BUILD_DATASET"),
    ("train.json", "TRAIN", "TRAIN"),
    ("test.json", "TEST", "TEST"),
    ("evaluate.json", "EVALUATE", "EVALUATE"),
    ("result_summary.json", "SUMMARIZE", "SUMMARIZE"),
    ("decision.json", "NEXT_ACTION", "JUDGE"),
)


@dataclass(frozen=True)
class RecoveryPlan:
    resume_stage: str
    last_completed_stage: str | None
    completed_stages: tuple[str, ...]
    missing_artifacts: list[str]
    trial_complete: bool


def build_recovery_plan(trial_dir: Path, stop_file: Path | None = None) -> RecoveryPlan:
    """Return the earliest safe resume boundary for a trial directory."""

    if stop_file is not None and stop_file.exists():
        return RecoveryPlan(
            resume_stage="STOP",
            last_completed_stage=None,
            completed_stages=(),
            missing_artifacts=[],
            trial_complete=False,
        )

    completed_stages: list[str] = []
    for artifact_name, completed_stage, resume_stage in _RECOVERY_RULES:
        if not (trial_dir / artifact_name).exists():
            last_completed = completed_stages[-1] if completed_stages else None
            return RecoveryPlan(
                resume_stage=resume_stage,
                last_completed_stage=last_completed,
                completed_stages=tuple(completed_stages),
                missing_artifacts=[artifact_name],
                trial_complete=False,
            )
        completed_stages.append(completed_stage)

    return RecoveryPlan(
        resume_stage="NEXT_ACTION",
        last_completed_stage="NEXT_ACTION",
        completed_stages=tuple(completed_stages),
        missing_artifacts=[],
        trial_complete=True,
    )
