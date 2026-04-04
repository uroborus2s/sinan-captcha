"""Typed contracts for autonomous training study, trial, and leaderboard state."""

from __future__ import annotations

from dataclasses import asdict, dataclass

JsonPrimitive = str | int | float | bool | None
JsonValue = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]

ALLOWED_TASKS = {"group1", "group2"}
ALLOWED_STUDY_STATUS = {"draft", "running", "paused", "completed", "failed", "stopped"}
ALLOWED_STUDY_MODES = {"full_auto", "review_auto"}
ALLOWED_TRAIN_MODES = {"fresh", "resume", "from_run"}
ALLOWED_SUMMARY_TRENDS = {"baseline", "improving", "declining", "plateau"}
ALLOWED_DECISIONS = {
    "RETUNE",
    "REGENERATE_DATA",
    "RESUME",
    "PROMOTE_BRANCH",
    "ABANDON_BRANCH",
}


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_in(value: str, field_name: str, allowed: set[str]) -> None:
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {allowed_text}")


def _require_ratio(value: float, field_name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


def _require_positive_int(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than 0")


def _require_positive_number(value: float, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than 0")


@dataclass(frozen=True)
class JudgeConfig:
    provider: str
    model: str

    def __post_init__(self) -> None:
        _require_non_empty(self.provider, "provider")
        _require_non_empty(self.model, "model")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "JudgeConfig":
        return cls(
            provider=_string(payload, "provider"),
            model=_string(payload, "model"),
        )


@dataclass(frozen=True)
class StudyBudget:
    max_trials: int
    max_hours: float
    max_new_datasets: int | None = None
    max_no_improve_trials: int | None = None

    def __post_init__(self) -> None:
        _require_positive_int(self.max_trials, "max_trials")
        _require_positive_number(self.max_hours, "max_hours")
        if self.max_new_datasets is not None:
            _require_positive_int(self.max_new_datasets, "max_new_datasets")
        if self.max_no_improve_trials is not None:
            _require_positive_int(self.max_no_improve_trials, "max_no_improve_trials")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "StudyBudget":
        return cls(
            max_trials=_int(payload, "max_trials"),
            max_hours=_float(payload, "max_hours"),
            max_new_datasets=_optional_int(payload, "max_new_datasets"),
            max_no_improve_trials=_optional_int(payload, "max_no_improve_trials"),
        )


@dataclass(frozen=True)
class StudyRecord:
    study_name: str
    task: str
    status: str
    mode: str
    train_root: str
    generator_workspace: str
    judge: JudgeConfig
    budget: StudyBudget
    current_trial_id: str | None = None
    best_trial_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.study_name, "study_name")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_in(self.status, "status", ALLOWED_STUDY_STATUS)
        _require_in(self.mode, "mode", ALLOWED_STUDY_MODES)
        _require_non_empty(self.train_root, "train_root")
        _require_non_empty(self.generator_workspace, "generator_workspace")
        if self.current_trial_id is not None:
            _require_non_empty(self.current_trial_id, "current_trial_id")
        if self.best_trial_id is not None:
            _require_non_empty(self.best_trial_id, "best_trial_id")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "study_name": self.study_name,
            "task": self.task,
            "status": self.status,
            "mode": self.mode,
            "train_root": self.train_root,
            "generator_workspace": self.generator_workspace,
            "judge": self.judge.to_dict(),
            "budget": self.budget.to_dict(),
            "current_trial_id": self.current_trial_id,
            "best_trial_id": self.best_trial_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "StudyRecord":
        return cls(
            study_name=_string(payload, "study_name"),
            task=_string(payload, "task"),
            status=_string(payload, "status"),
            mode=_string(payload, "mode"),
            train_root=_string(payload, "train_root"),
            generator_workspace=_string(payload, "generator_workspace"),
            judge=JudgeConfig.from_dict(_mapping(payload, "judge")),
            budget=StudyBudget.from_dict(_mapping(payload, "budget")),
            current_trial_id=_optional_string(payload, "current_trial_id"),
            best_trial_id=_optional_string(payload, "best_trial_id"),
        )


@dataclass(frozen=True)
class TrialInputRecord:
    trial_id: str
    task: str
    dataset_version: str
    train_name: str
    train_mode: str
    base_run: str | None
    params: dict[str, JsonValue]

    def __post_init__(self) -> None:
        _require_non_empty(self.trial_id, "trial_id")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.dataset_version, "dataset_version")
        _require_non_empty(self.train_name, "train_name")
        _require_in(self.train_mode, "train_mode", ALLOWED_TRAIN_MODES)
        if self.train_mode == "from_run" and not self.base_run:
            raise ValueError("base_run is required when train_mode is from_run")
        if self.base_run is not None:
            _require_non_empty(self.base_run, "base_run")
        if not self.params:
            raise ValueError("params must not be empty")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "TrialInputRecord":
        return cls(
            trial_id=_string(payload, "trial_id"),
            task=_string(payload, "task"),
            dataset_version=_string(payload, "dataset_version"),
            train_name=_string(payload, "train_name"),
            train_mode=_string(payload, "train_mode"),
            base_run=_optional_string(payload, "base_run"),
            params=_mapping(payload, "params"),
        )


@dataclass(frozen=True)
class DatasetRecord:
    task: str
    dataset_version: str
    dataset_root: str
    manifest_path: str | None = None
    label_source: str | None = None
    sample_counts: dict[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.dataset_version, "dataset_version")
        _require_non_empty(self.dataset_root, "dataset_root")
        if self.manifest_path is not None:
            _require_non_empty(self.manifest_path, "manifest_path")
        if self.label_source is not None:
            _require_non_empty(self.label_source, "label_source")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "DatasetRecord":
        return cls(
            task=_string(payload, "task"),
            dataset_version=_string(payload, "dataset_version"),
            dataset_root=_string(payload, "dataset_root"),
            manifest_path=_optional_string(payload, "manifest_path"),
            label_source=_optional_string(payload, "label_source"),
            sample_counts=_optional_mapping(payload, "sample_counts"),
        )


@dataclass(frozen=True)
class TrainRecord:
    task: str
    train_name: str
    run_dir: str
    params: dict[str, JsonValue]
    best_weights: str | None = None
    last_weights: str | None = None
    resumed_from: str | None = None

    def __post_init__(self) -> None:
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.train_name, "train_name")
        _require_non_empty(self.run_dir, "run_dir")
        if not self.params:
            raise ValueError("params must not be empty")
        if self.best_weights is not None:
            _require_non_empty(self.best_weights, "best_weights")
        if self.last_weights is not None:
            _require_non_empty(self.last_weights, "last_weights")
        if self.resumed_from is not None:
            _require_non_empty(self.resumed_from, "resumed_from")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "TrainRecord":
        return cls(
            task=_string(payload, "task"),
            train_name=_string(payload, "train_name"),
            run_dir=_string(payload, "run_dir"),
            params=_mapping(payload, "params"),
            best_weights=_optional_string(payload, "best_weights"),
            last_weights=_optional_string(payload, "last_weights"),
            resumed_from=_optional_string(payload, "resumed_from"),
        )


@dataclass(frozen=True)
class TestRecord:
    task: str
    dataset_version: str
    train_name: str
    metrics: dict[str, JsonValue]
    predict_output_dir: str
    val_output_dir: str
    report_dir: str

    def __post_init__(self) -> None:
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.dataset_version, "dataset_version")
        _require_non_empty(self.train_name, "train_name")
        if not self.metrics:
            raise ValueError("metrics must not be empty")
        _require_non_empty(self.predict_output_dir, "predict_output_dir")
        _require_non_empty(self.val_output_dir, "val_output_dir")
        _require_non_empty(self.report_dir, "report_dir")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "TestRecord":
        return cls(
            task=_string(payload, "task"),
            dataset_version=_string(payload, "dataset_version"),
            train_name=_string(payload, "train_name"),
            metrics=_mapping(payload, "metrics"),
            predict_output_dir=_string(payload, "predict_output_dir"),
            val_output_dir=_string(payload, "val_output_dir"),
            report_dir=_string(payload, "report_dir"),
        )


@dataclass(frozen=True)
class EvaluateRecord:
    available: bool
    task: str
    metrics: dict[str, JsonValue]
    failure_count: int
    report_dir: str

    def __post_init__(self) -> None:
        _require_in(self.task, "task", ALLOWED_TASKS)
        if self.failure_count < 0:
            raise ValueError("failure_count must not be negative")
        _require_non_empty(self.report_dir, "report_dir")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "EvaluateRecord":
        return cls(
            available=_bool(payload, "available"),
            task=_string(payload, "task"),
            metrics=_mapping(payload, "metrics"),
            failure_count=_int(payload, "failure_count"),
            report_dir=_string(payload, "report_dir"),
        )


@dataclass(frozen=True)
class AgentRef:
    provider: str
    name: str
    model: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.provider, "provider")
        _require_non_empty(self.name, "name")
        if self.model is not None:
            _require_non_empty(self.model, "model")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "AgentRef":
        return cls(
            provider=_string(payload, "provider"),
            name=_string(payload, "name"),
            model=_optional_string(payload, "model"),
        )


@dataclass(frozen=True)
class JudgeDecisionPayload:
    decision: str
    reason: str
    confidence: float
    next_action: dict[str, JsonValue]
    evidence: list[str]

    def __post_init__(self) -> None:
        _require_in(self.decision, "decision", ALLOWED_DECISIONS)
        _require_non_empty(self.reason, "reason")
        _require_ratio(self.confidence, "confidence")
        if not isinstance(self.next_action, dict):
            raise ValueError("next_action must be a mapping")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("evidence entries must be non-empty strings")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "JudgeDecisionPayload":
        evidence_payload = payload.get("evidence")
        if not isinstance(evidence_payload, list):
            raise ValueError("evidence must be a list")
        evidence = [_coerce_string(item, "evidence") for item in evidence_payload]
        return cls(
            decision=_string(payload, "decision"),
            reason=_string(payload, "reason"),
            confidence=_float(payload, "confidence"),
            next_action=_mapping(payload, "next_action"),
            evidence=evidence,
        )


@dataclass(frozen=True)
class DecisionRecord:
    trial_id: str
    decision: str
    confidence: float
    reason: str
    next_action: dict[str, JsonValue]
    evidence: list[str]
    agent: AgentRef

    def __post_init__(self) -> None:
        _require_non_empty(self.trial_id, "trial_id")
        _require_in(self.decision, "decision", ALLOWED_DECISIONS)
        _require_ratio(self.confidence, "confidence")
        _require_non_empty(self.reason, "reason")
        if not isinstance(self.next_action, dict):
            raise ValueError("next_action must be a mapping")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("evidence entries must be non-empty strings")

    def to_dict(self) -> dict[str, JsonValue]:
        payload = asdict(self)
        payload["agent"] = self.agent.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "DecisionRecord":
        evidence_payload = payload.get("evidence")
        if not isinstance(evidence_payload, list):
            raise ValueError("evidence must be a list")
        evidence = [_coerce_string(item, "evidence") for item in evidence_payload]
        return cls(
            trial_id=_string(payload, "trial_id"),
            decision=_string(payload, "decision"),
            confidence=_float(payload, "confidence"),
            reason=_string(payload, "reason"),
            next_action=_mapping(payload, "next_action"),
            evidence=evidence,
            agent=AgentRef.from_dict(_mapping(payload, "agent")),
        )


@dataclass(frozen=True)
class LeaderboardEntry:
    trial_id: str
    dataset_version: str
    train_name: str
    primary_score: float
    metrics: dict[str, JsonValue]
    decision: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.trial_id, "trial_id")
        _require_non_empty(self.dataset_version, "dataset_version")
        _require_non_empty(self.train_name, "train_name")
        if self.decision is not None:
            _require_in(self.decision, "decision", ALLOWED_DECISIONS)
        if not self.metrics:
            raise ValueError("metrics must not be empty")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "LeaderboardEntry":
        return cls(
            trial_id=_string(payload, "trial_id"),
            dataset_version=_string(payload, "dataset_version"),
            train_name=_string(payload, "train_name"),
            primary_score=_float(payload, "primary_score"),
            metrics=_mapping(payload, "metrics"),
            decision=_optional_string(payload, "decision"),
        )


@dataclass(frozen=True)
class LeaderboardRecord:
    study_name: str
    task: str
    primary_metric: str
    entries: list[LeaderboardEntry]

    def __post_init__(self) -> None:
        _require_non_empty(self.study_name, "study_name")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.primary_metric, "primary_metric")
        normalized_entries = sorted(
            self.entries,
            key=lambda entry: (-entry.primary_score, entry.trial_id),
        )
        object.__setattr__(self, "entries", normalized_entries)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "study_name": self.study_name,
            "task": self.task,
            "primary_metric": self.primary_metric,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "LeaderboardRecord":
        entries_payload = payload.get("entries")
        if not isinstance(entries_payload, list):
            raise ValueError("entries must be a list")
        return cls(
            study_name=_string(payload, "study_name"),
            task=_string(payload, "task"),
            primary_metric=_string(payload, "primary_metric"),
            entries=[LeaderboardEntry.from_dict(_coerce_mapping(item, "entries")) for item in entries_payload],
        )

    @property
    def best_entry(self) -> LeaderboardEntry | None:
        if not self.entries:
            return None
        return self.entries[0]


@dataclass(frozen=True)
class BestTrialRecord:
    study_name: str
    task: str
    trial_id: str
    primary_metric: str
    primary_score: float
    dataset_version: str
    train_name: str
    metrics: dict[str, JsonValue]
    decision: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.study_name, "study_name")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.trial_id, "trial_id")
        _require_non_empty(self.primary_metric, "primary_metric")
        _require_non_empty(self.dataset_version, "dataset_version")
        _require_non_empty(self.train_name, "train_name")
        if self.decision is not None:
            _require_in(self.decision, "decision", ALLOWED_DECISIONS)
        if not self.metrics:
            raise ValueError("metrics must not be empty")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "BestTrialRecord":
        return cls(
            study_name=_string(payload, "study_name"),
            task=_string(payload, "task"),
            trial_id=_string(payload, "trial_id"),
            primary_metric=_string(payload, "primary_metric"),
            primary_score=_float(payload, "primary_score"),
            dataset_version=_string(payload, "dataset_version"),
            train_name=_string(payload, "train_name"),
            metrics=_mapping(payload, "metrics"),
            decision=_optional_string(payload, "decision"),
        )

    @classmethod
    def from_leaderboard_entry(
        cls,
        *,
        study_name: str,
        task: str,
        primary_metric: str,
        entry: LeaderboardEntry,
    ) -> "BestTrialRecord":
        return cls(
            study_name=study_name,
            task=task,
            trial_id=entry.trial_id,
            primary_metric=primary_metric,
            primary_score=entry.primary_score,
            dataset_version=entry.dataset_version,
            train_name=entry.train_name,
            metrics=entry.metrics,
            decision=entry.decision,
        )


@dataclass(frozen=True)
class ResultSummarySnapshot:
    trial_id: str
    dataset_version: str
    train_name: str
    primary_score: float | None
    metrics: dict[str, JsonValue]
    decision: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.trial_id, "trial_id")
        _require_non_empty(self.dataset_version, "dataset_version")
        _require_non_empty(self.train_name, "train_name")
        if self.decision is not None:
            _require_in(self.decision, "decision", ALLOWED_DECISIONS)
        if not isinstance(self.metrics, dict):
            raise ValueError("metrics must be an object")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "ResultSummarySnapshot":
        return cls(
            trial_id=_string(payload, "trial_id"),
            dataset_version=_string(payload, "dataset_version"),
            train_name=_string(payload, "train_name"),
            primary_score=_optional_float(payload, "primary_score"),
            metrics=_mapping(payload, "metrics"),
            decision=_optional_string(payload, "decision"),
        )


@dataclass(frozen=True)
class ResultSummaryRecord:
    study_name: str
    task: str
    trial_id: str
    dataset_version: str
    train_name: str
    primary_metric: str
    primary_score: float | None
    test_metrics: dict[str, JsonValue]
    evaluation_available: bool
    evaluation_metrics: dict[str, JsonValue]
    failure_count: int | None
    trend: str
    delta_vs_previous: float | None
    delta_vs_best: float | None
    weak_classes: list[str]
    failure_patterns: list[str]
    recent_trials: list[ResultSummarySnapshot]
    best_trial: ResultSummarySnapshot | None
    evidence: list[str]

    def __post_init__(self) -> None:
        _require_non_empty(self.study_name, "study_name")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.trial_id, "trial_id")
        _require_non_empty(self.dataset_version, "dataset_version")
        _require_non_empty(self.train_name, "train_name")
        _require_non_empty(self.primary_metric, "primary_metric")
        _require_in(self.trend, "trend", ALLOWED_SUMMARY_TRENDS)
        if not isinstance(self.test_metrics, dict):
            raise ValueError("test_metrics must be an object")
        if not isinstance(self.evaluation_metrics, dict):
            raise ValueError("evaluation_metrics must be an object")
        if self.failure_count is not None and self.failure_count < 0:
            raise ValueError("failure_count must not be negative")
        if any(not isinstance(item, str) or not item.strip() for item in self.weak_classes):
            raise ValueError("weak_classes entries must be non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in self.failure_patterns):
            raise ValueError("failure_patterns entries must be non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("evidence entries must be non-empty strings")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "study_name": self.study_name,
            "task": self.task,
            "trial_id": self.trial_id,
            "dataset_version": self.dataset_version,
            "train_name": self.train_name,
            "primary_metric": self.primary_metric,
            "primary_score": self.primary_score,
            "test_metrics": self.test_metrics,
            "evaluation_available": self.evaluation_available,
            "evaluation_metrics": self.evaluation_metrics,
            "failure_count": self.failure_count,
            "trend": self.trend,
            "delta_vs_previous": self.delta_vs_previous,
            "delta_vs_best": self.delta_vs_best,
            "weak_classes": self.weak_classes,
            "failure_patterns": self.failure_patterns,
            "recent_trials": [item.to_dict() for item in self.recent_trials],
            "best_trial": None if self.best_trial is None else self.best_trial.to_dict(),
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "ResultSummaryRecord":
        weak_classes = _string_list(payload, "weak_classes")
        failure_patterns = _string_list(payload, "failure_patterns")
        evidence = _string_list(payload, "evidence")
        recent_payload = payload.get("recent_trials")
        if not isinstance(recent_payload, list):
            raise ValueError("recent_trials must be a list")
        best_trial_payload = payload.get("best_trial")
        if best_trial_payload is not None and not isinstance(best_trial_payload, dict):
            raise ValueError("best_trial must be an object or null")
        return cls(
            study_name=_string(payload, "study_name"),
            task=_string(payload, "task"),
            trial_id=_string(payload, "trial_id"),
            dataset_version=_string(payload, "dataset_version"),
            train_name=_string(payload, "train_name"),
            primary_metric=_string(payload, "primary_metric"),
            primary_score=_optional_float(payload, "primary_score"),
            test_metrics=_mapping(payload, "test_metrics"),
            evaluation_available=_bool(payload, "evaluation_available"),
            evaluation_metrics=_mapping(payload, "evaluation_metrics"),
            failure_count=_optional_int(payload, "failure_count"),
            trend=_string(payload, "trend"),
            delta_vs_previous=_optional_float(payload, "delta_vs_previous"),
            delta_vs_best=_optional_float(payload, "delta_vs_best"),
            weak_classes=weak_classes,
            failure_patterns=failure_patterns,
            recent_trials=[ResultSummarySnapshot.from_dict(_coerce_mapping(item, "recent_trials")) for item in recent_payload],
            best_trial=None
            if best_trial_payload is None
            else ResultSummarySnapshot.from_dict(best_trial_payload),
            evidence=evidence,
        )


def _string(payload: dict[str, JsonValue], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _optional_string(payload: dict[str, JsonValue], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    return value


def _int(payload: dict[str, JsonValue], field_name: str) -> int:
    value = payload.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _optional_int(payload: dict[str, JsonValue], field_name: str) -> int | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer or null")
    return value


def _float(payload: dict[str, JsonValue], field_name: str) -> float:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    return float(value)


def _optional_float(payload: dict[str, JsonValue], field_name: str) -> float | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number or null")
    return float(value)


def _bool(payload: dict[str, JsonValue], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _mapping(payload: dict[str, JsonValue], field_name: str) -> dict[str, JsonValue]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _optional_mapping(payload: dict[str, JsonValue], field_name: str) -> dict[str, JsonValue] | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object or null")
    return value


def _coerce_string(value: JsonValue, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} entries must be strings")
    return value


def _coerce_mapping(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} entries must be objects")
    return value


def _string_list(payload: dict[str, JsonValue], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return [_coerce_string(item, field_name) for item in value]
