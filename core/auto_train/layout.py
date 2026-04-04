"""Study directory layout helpers for autonomous training artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.auto_train.contracts import ALLOWED_TASKS

_TRIAL_ID_PATTERN = re.compile(r"^trial_(\d{4})$")


def format_trial_id(index: int) -> str:
    """Return a zero-padded trial identifier like ``trial_0001``."""

    if index <= 0:
        raise ValueError("index must be greater than 0")
    return f"trial_{index:04d}"


def parse_trial_id(trial_id: str) -> int:
    """Parse a trial identifier and return its numeric index."""

    match = _TRIAL_ID_PATTERN.fullmatch(trial_id)
    if match is None:
        raise ValueError("trial_id must match trial_0001 style naming")
    return int(match.group(1))


@dataclass(frozen=True)
class StudyPaths:
    studies_root: Path
    task: str
    study_name: str

    def __post_init__(self) -> None:
        if self.task not in ALLOWED_TASKS:
            allowed = ", ".join(sorted(ALLOWED_TASKS))
            raise ValueError(f"task must be one of: {allowed}")
        if not self.study_name.strip():
            raise ValueError("study_name must not be empty")

    @property
    def group_root(self) -> Path:
        return self.studies_root / self.task

    @property
    def study_root(self) -> Path:
        return self.group_root / self.study_name

    @property
    def study_file(self) -> Path:
        return self.study_root / "study.json"

    @property
    def best_trial_file(self) -> Path:
        return self.study_root / "best_trial.json"

    @property
    def trial_history_file(self) -> Path:
        return self.study_root / "trial_history.jsonl"

    @property
    def decisions_file(self) -> Path:
        return self.study_root / "decisions.jsonl"

    @property
    def leaderboard_file(self) -> Path:
        return self.study_root / "leaderboard.json"

    @property
    def summary_file(self) -> Path:
        return self.study_root / "summary.md"

    @property
    def stop_file(self) -> Path:
        return self.study_root / "STOP"

    @property
    def trials_root(self) -> Path:
        return self.study_root / "trials"

    def ensure_layout(self) -> None:
        """Create the study root and trials directory when absent."""

        self.trials_root.mkdir(parents=True, exist_ok=True)

    def trial_dir(self, trial_id: str) -> Path:
        parse_trial_id(trial_id)
        return self.trials_root / trial_id

    def ensure_trial_dir(self, trial_id: str) -> Path:
        trial_dir = self.trial_dir(trial_id)
        trial_dir.mkdir(parents=True, exist_ok=True)
        return trial_dir

    def input_file(self, trial_id: str) -> Path:
        return self.trial_dir(trial_id) / "input.json"

    def dataset_file(self, trial_id: str) -> Path:
        return self.trial_dir(trial_id) / "dataset.json"

    def train_file(self, trial_id: str) -> Path:
        return self.trial_dir(trial_id) / "train.json"

    def test_file(self, trial_id: str) -> Path:
        return self.trial_dir(trial_id) / "test.json"

    def evaluate_file(self, trial_id: str) -> Path:
        return self.trial_dir(trial_id) / "evaluate.json"

    def result_summary_file(self, trial_id: str) -> Path:
        return self.trial_dir(trial_id) / "result_summary.json"

    def decision_file(self, trial_id: str) -> Path:
        return self.trial_dir(trial_id) / "decision.json"

    def trial_summary_file(self, trial_id: str) -> Path:
        return self.trial_dir(trial_id) / "summary.md"
