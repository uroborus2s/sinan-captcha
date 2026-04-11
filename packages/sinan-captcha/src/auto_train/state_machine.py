"""State machine and recovery helpers for autonomous training studies."""

from __future__ import annotations

from pathlib import Path

from auto_train.recovery import build_recovery_plan

STAGES: tuple[str, ...] = (
    "PLAN",
    "BUILD_DATASET",
    "TRAIN",
    "TEST",
    "EVALUATE",
    "SUMMARIZE",
    "JUDGE",
    "NEXT_ACTION",
    "STOP",
)
TERMINAL_STAGES = {"STOP"}

def next_stage(current_stage: str) -> str:
    """Return the next sequential stage, keeping STOP terminal."""

    _validate_stage(current_stage)
    if current_stage == "STOP":
        return "STOP"
    index = STAGES.index(current_stage)
    return STAGES[index + 1]


def is_terminal_stage(stage: str) -> bool:
    """Return whether a stage is terminal."""

    _validate_stage(stage)
    return stage in TERMINAL_STAGES


def infer_resume_stage(trial_dir: Path, stop_file: Path | None = None) -> str:
    """Infer the next stage from persisted artifacts."""

    plan = build_recovery_plan(trial_dir, stop_file=stop_file)
    return plan.resume_stage


def _validate_stage(stage: str) -> None:
    if stage not in STAGES:
        allowed = ", ".join(STAGES)
        raise ValueError(f"stage must be one of: {allowed}")
