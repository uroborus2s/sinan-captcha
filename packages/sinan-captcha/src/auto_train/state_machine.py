"""State machine and recovery helpers for autonomous training studies."""

from __future__ import annotations

from pathlib import Path

from auto_train.recovery import build_recovery_plan

LEGACY_STAGES: tuple[str, ...] = (
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
GROUP1_STAGES: tuple[str, ...] = (
    "PLAN",
    "BUILD_DATASET",
    "TRAIN_QUERY",
    "QUERY_GATE",
    "TRAIN_SCENE",
    "SCENE_GATE",
    "TRAIN_EMBEDDER_BASE",
    "TEST",
    "EVALUATE",
    "SUMMARIZE",
    "JUDGE",
    "NEXT_ACTION",
    "STOP",
)
STAGES: tuple[str, ...] = tuple(dict.fromkeys((*LEGACY_STAGES, *GROUP1_STAGES)))
TERMINAL_STAGES = {"STOP"}

def next_stage(current_stage: str, *, task: str | None = None) -> str:
    """Return the next sequential stage, keeping STOP terminal."""

    stages = _stages_for_task(task)
    _validate_stage(current_stage, stages=stages)
    if current_stage == "STOP":
        return "STOP"
    index = stages.index(current_stage)
    return stages[index + 1]


def is_terminal_stage(stage: str, *, task: str | None = None) -> bool:
    """Return whether a stage is terminal."""

    _validate_stage(stage, stages=_stages_for_task(task))
    return stage in TERMINAL_STAGES


def infer_resume_stage(trial_dir: Path, *, task: str | None = None, stop_file: Path | None = None) -> str:
    """Infer the next stage from persisted artifacts."""

    plan = build_recovery_plan(trial_dir, task=task, stop_file=stop_file)
    return plan.resume_stage


def _stages_for_task(task: str | None) -> tuple[str, ...]:
    if task == "group1":
        return GROUP1_STAGES
    return LEGACY_STAGES


def _validate_stage(stage: str, *, stages: tuple[str, ...]) -> None:
    if stage not in stages:
        allowed = ", ".join(stages)
        raise ValueError(f"stage must be one of: {allowed}")
