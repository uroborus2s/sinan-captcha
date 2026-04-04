"""Stop policy evaluation for autonomous training studies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopPolicy:
    max_trials: int
    max_hours: float
    plateau_window: int | None = None
    min_delta: float = 0.0
    max_no_improve_trials: int | None = None

    def __post_init__(self) -> None:
        if self.max_trials <= 0:
            raise ValueError("max_trials must be greater than 0")
        if self.max_hours <= 0:
            raise ValueError("max_hours must be greater than 0")
        if self.plateau_window is not None and self.plateau_window <= 0:
            raise ValueError("plateau_window must be greater than 0")
        if self.min_delta < 0:
            raise ValueError("min_delta must not be negative")
        if self.max_no_improve_trials is not None and self.max_no_improve_trials <= 0:
            raise ValueError("max_no_improve_trials must be greater than 0")


@dataclass(frozen=True)
class StopSnapshot:
    completed_trials: int
    elapsed_hours: float
    recent_primary_scores: list[float]
    no_improve_trials: int = 0
    stop_file_present: bool = False
    fatal_error: str | None = None

    def __post_init__(self) -> None:
        if self.completed_trials < 0:
            raise ValueError("completed_trials must not be negative")
        if self.elapsed_hours < 0:
            raise ValueError("elapsed_hours must not be negative")
        if self.no_improve_trials < 0:
            raise ValueError("no_improve_trials must not be negative")


@dataclass(frozen=True)
class StopDecision:
    should_stop: bool
    reason: str
    detail: str | None = None


def evaluate_stop(policy: StopPolicy, snapshot: StopSnapshot) -> StopDecision:
    """Evaluate whether a study should stop."""

    if snapshot.stop_file_present:
        return StopDecision(True, "stop_file_detected", "STOP file is present")
    if snapshot.fatal_error:
        return StopDecision(True, "fatal_failure", snapshot.fatal_error)
    if snapshot.completed_trials >= policy.max_trials:
        return StopDecision(True, "max_trials_reached", f"{snapshot.completed_trials}/{policy.max_trials}")
    if snapshot.elapsed_hours >= policy.max_hours:
        return StopDecision(True, "max_hours_reached", f"{snapshot.elapsed_hours:.2f}/{policy.max_hours:.2f}")
    if (
        policy.max_no_improve_trials is not None
        and snapshot.no_improve_trials >= policy.max_no_improve_trials
    ):
        return StopDecision(
            True,
            "no_improve_limit_reached",
            f"{snapshot.no_improve_trials}/{policy.max_no_improve_trials}",
        )
    if _is_plateau(policy, snapshot):
        return StopDecision(True, "plateau_detected", "recent scores did not improve enough")
    return StopDecision(False, "continue")


def _is_plateau(policy: StopPolicy, snapshot: StopSnapshot) -> bool:
    if policy.plateau_window is None:
        return False
    scores = snapshot.recent_primary_scores[-policy.plateau_window :]
    if len(scores) < policy.plateau_window:
        return False
    improvement = max(scores) - min(scores)
    return improvement < policy.min_delta
