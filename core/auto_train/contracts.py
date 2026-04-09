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
ALLOWED_BUDGET_PRESSURE = {"low", "medium", "high"}
ALLOWED_BUSINESS_GATE_STATUS = {"passed", "failed", "error"}
ALLOWED_DATASET_ACTIONS = {"reuse", "new_version", "freeze"}
ALLOWED_GENERATOR_OVERRIDE_TOP_LEVEL = {"project", "sampling", "effects"}
ALLOWED_GENERATOR_OVERRIDE_PROJECT_FIELDS = {"sample_count"}
ALLOWED_GENERATOR_OVERRIDE_SAMPLING_FIELDS = {
    "target_count_min",
    "target_count_max",
    "distractor_count_min",
    "distractor_count_max",
}
ALLOWED_GENERATOR_OVERRIDE_EFFECTS_SECTIONS = {"common", "click", "slide"}
ALLOWED_GENERATOR_OVERRIDE_COMMON_EFFECTS_FIELDS = {
    "scene_veil_strength",
    "background_blur_radius_min",
    "background_blur_radius_max",
}
ALLOWED_GENERATOR_OVERRIDE_CLICK_EFFECTS_FIELDS = {
    "icon_shadow_alpha_min",
    "icon_shadow_alpha_max",
    "icon_shadow_offset_x_min",
    "icon_shadow_offset_x_max",
    "icon_shadow_offset_y_min",
    "icon_shadow_offset_y_max",
    "icon_edge_blur_radius_min",
    "icon_edge_blur_radius_max",
}
ALLOWED_GENERATOR_OVERRIDE_SLIDE_EFFECTS_FIELDS = {
    "gap_shadow_alpha_min",
    "gap_shadow_alpha_max",
    "gap_shadow_offset_x_min",
    "gap_shadow_offset_x_max",
    "gap_shadow_offset_y_min",
    "gap_shadow_offset_y_max",
    "tile_edge_blur_radius_min",
    "tile_edge_blur_radius_max",
}
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
class BusinessEvalConfig:
    cases_root: str
    success_threshold: float = 0.95
    min_cases: int = 50
    sample_size: int = 50
    point_tolerance_px: int = 5
    iou_threshold: float = 0.5

    def __post_init__(self) -> None:
        _require_non_empty(self.cases_root, "cases_root")
        _require_ratio(self.success_threshold, "success_threshold")
        _require_positive_int(self.min_cases, "min_cases")
        _require_positive_int(self.sample_size, "sample_size")
        if self.min_cases < self.sample_size:
            raise ValueError("min_cases must be greater than or equal to sample_size")
        _require_positive_int(self.point_tolerance_px, "point_tolerance_px")
        _require_ratio(self.iou_threshold, "iou_threshold")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "BusinessEvalConfig":
        return cls(
            cases_root=_string(payload, "cases_root"),
            success_threshold=_float(payload, "success_threshold"),
            min_cases=_int(payload, "min_cases"),
            sample_size=_int(payload, "sample_size"),
            point_tolerance_px=_int(payload, "point_tolerance_px"),
            iou_threshold=_float(payload, "iou_threshold"),
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
    business_eval: BusinessEvalConfig | None = None
    started_at: str | None = None
    current_trial_id: str | None = None
    best_trial_id: str | None = None
    final_reason: str | None = None
    final_detail: str | None = None
    goal_only_stop: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(self.study_name, "study_name")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_in(self.status, "status", ALLOWED_STUDY_STATUS)
        _require_in(self.mode, "mode", ALLOWED_STUDY_MODES)
        _require_non_empty(self.train_root, "train_root")
        _require_non_empty(self.generator_workspace, "generator_workspace")
        if self.started_at is not None:
            _require_non_empty(self.started_at, "started_at")
        if self.current_trial_id is not None:
            _require_non_empty(self.current_trial_id, "current_trial_id")
        if self.best_trial_id is not None:
            _require_non_empty(self.best_trial_id, "best_trial_id")
        if self.final_reason is not None:
            _require_non_empty(self.final_reason, "final_reason")
        if self.final_detail is not None:
            _require_non_empty(self.final_detail, "final_detail")

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
            "business_eval": None if self.business_eval is None else self.business_eval.to_dict(),
            "started_at": self.started_at,
            "current_trial_id": self.current_trial_id,
            "best_trial_id": self.best_trial_id,
            "final_reason": self.final_reason,
            "final_detail": self.final_detail,
            "goal_only_stop": self.goal_only_stop,
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
            business_eval=(
                None
                if payload.get("business_eval") is None
                else BusinessEvalConfig.from_dict(_mapping(payload, "business_eval"))
            ),
            started_at=_optional_string(payload, "started_at"),
            current_trial_id=_optional_string(payload, "current_trial_id"),
            best_trial_id=_optional_string(payload, "best_trial_id"),
            final_reason=_optional_string(payload, "final_reason"),
            final_detail=_optional_string(payload, "final_detail"),
            goal_only_stop=_optional_bool(payload, "goal_only_stop") or False,
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
    dataset_preset: str | None = None
    dataset_override: dict[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.trial_id, "trial_id")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.dataset_version, "dataset_version")
        if self.dataset_preset is not None:
            _require_non_empty(self.dataset_preset, "dataset_preset")
        if self.dataset_override is not None:
            _validate_generator_overrides(self.dataset_override, "dataset_override")
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
            dataset_preset=_optional_string(payload, "dataset_preset"),
            dataset_override=_optional_mapping(payload, "dataset_override"),
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
            key=lambda entry: (
                -_leaderboard_ranking_score(entry),
                -entry.primary_score,
                entry.trial_id,
            ),
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


@dataclass(frozen=True)
class BusinessEvalCaseRecord:
    case_id: str
    sample_id: str
    success: bool
    reason_code: str
    reason_cn: str
    input_images: dict[str, JsonValue]
    metrics: dict[str, JsonValue]
    prediction: dict[str, JsonValue] | None = None
    reference: dict[str, JsonValue] | None = None
    evidence: list[str] | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty(self.sample_id, "sample_id")
        _require_non_empty(self.reason_code, "reason_code")
        _require_non_empty(self.reason_cn, "reason_cn")
        if not self.input_images:
            raise ValueError("input_images must not be empty")
        for key, value in self.input_images.items():
            _require_non_empty(key, "input_images key")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("input_images values must be non-empty strings")
        if any(not isinstance(key, str) or not key.strip() for key in self.metrics):
            raise ValueError("metrics keys must be non-empty strings")
        if self.evidence is not None:
            if not isinstance(self.evidence, list):
                raise ValueError("evidence must be a list or null")
            if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
                raise ValueError("evidence entries must be non-empty strings")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "BusinessEvalCaseRecord":
        return cls(
            case_id=_string(payload, "case_id"),
            sample_id=_string(payload, "sample_id"),
            success=_bool(payload, "success"),
            reason_code=_string(payload, "reason_code"),
            reason_cn=_string(payload, "reason_cn"),
            input_images=_mapping(payload, "input_images"),
            metrics=_mapping(payload, "metrics"),
            prediction=_optional_mapping(payload, "prediction"),
            reference=_optional_mapping(payload, "reference"),
            evidence=_optional_string_list(payload, "evidence"),
        )


@dataclass(frozen=True)
class BusinessEvalRecord:
    trial_id: str
    task: str
    train_name: str
    cases_root: str
    available_cases: int
    total_cases: int
    passed_cases: int
    success_rate: float
    success_threshold: float
    min_cases: int
    sample_size: int
    commercial_ready: bool
    point_tolerance_px: int
    iou_threshold: float
    sampled_source: str
    report_dir: str
    prediction_dir: str
    evaluation_report_dir: str
    case_results: list[BusinessEvalCaseRecord]
    evidence: list[str]

    def __post_init__(self) -> None:
        _require_non_empty(self.trial_id, "trial_id")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.train_name, "train_name")
        _require_non_empty(self.cases_root, "cases_root")
        _require_non_empty(self.report_dir, "report_dir")
        if self.available_cases < 0:
            raise ValueError("available_cases must not be negative")
        if self.total_cases < 0:
            raise ValueError("total_cases must not be negative")
        if self.total_cases > self.available_cases:
            raise ValueError("total_cases must not exceed available_cases")
        if self.passed_cases < 0:
            raise ValueError("passed_cases must not be negative")
        if self.passed_cases > self.total_cases:
            raise ValueError("passed_cases must not exceed total_cases")
        _require_ratio(self.success_rate, "success_rate")
        _require_ratio(self.success_threshold, "success_threshold")
        _require_positive_int(self.min_cases, "min_cases")
        _require_positive_int(self.sample_size, "sample_size")
        if self.min_cases < self.sample_size:
            raise ValueError("min_cases must be greater than or equal to sample_size")
        _require_positive_int(self.point_tolerance_px, "point_tolerance_px")
        _require_ratio(self.iou_threshold, "iou_threshold")
        _require_non_empty(self.sampled_source, "sampled_source")
        _require_non_empty(self.report_dir, "report_dir")
        _require_non_empty(self.prediction_dir, "prediction_dir")
        _require_non_empty(self.evaluation_report_dir, "evaluation_report_dir")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("evidence entries must be non-empty strings")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "trial_id": self.trial_id,
            "task": self.task,
            "train_name": self.train_name,
            "cases_root": self.cases_root,
            "available_cases": self.available_cases,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "success_rate": self.success_rate,
            "success_threshold": self.success_threshold,
            "min_cases": self.min_cases,
            "sample_size": self.sample_size,
            "commercial_ready": self.commercial_ready,
            "point_tolerance_px": self.point_tolerance_px,
            "iou_threshold": self.iou_threshold,
            "sampled_source": self.sampled_source,
            "report_dir": self.report_dir,
            "prediction_dir": self.prediction_dir,
            "evaluation_report_dir": self.evaluation_report_dir,
            "case_results": [item.to_dict() for item in self.case_results],
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "BusinessEvalRecord":
        case_payload = payload.get("case_results")
        if not isinstance(case_payload, list):
            raise ValueError("case_results must be a list")
        total_cases = _int(payload, "total_cases")
        return cls(
            trial_id=_string(payload, "trial_id"),
            task=_string(payload, "task"),
            train_name=_string(payload, "train_name"),
            cases_root=_string(payload, "cases_root"),
            available_cases=_optional_int(payload, "available_cases") or total_cases,
            total_cases=total_cases,
            passed_cases=_int(payload, "passed_cases"),
            success_rate=_float(payload, "success_rate"),
            success_threshold=_float(payload, "success_threshold"),
            min_cases=_int(payload, "min_cases"),
            sample_size=_int(payload, "sample_size"),
            commercial_ready=_bool(payload, "commercial_ready"),
            point_tolerance_px=_int(payload, "point_tolerance_px"),
            iou_threshold=_float(payload, "iou_threshold"),
            sampled_source=_string(payload, "sampled_source"),
            report_dir=_string(payload, "report_dir"),
            prediction_dir=_string(payload, "prediction_dir"),
            evaluation_report_dir=_string(payload, "evaluation_report_dir"),
            case_results=[BusinessEvalCaseRecord.from_dict(_coerce_mapping(item, "case_results")) for item in case_payload],
            evidence=_string_list(payload, "evidence"),
        )


@dataclass(frozen=True)
class StudyStatusRecord:
    study_name: str
    task: str
    status: str
    current_trial_id: str | None
    best_trial_id: str | None
    latest_decision: str | None
    best_primary_score: float | None
    budget_pressure: str
    summary_cn: str
    next_actions_cn: list[str]
    evidence: list[str]
    business_success_rate: float | None = None
    business_success_threshold: float | None = None
    commercial_ready: bool | None = None
    latest_gate_status: str | None = None
    final_reason: str | None = None
    final_detail: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.study_name, "study_name")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_in(self.status, "status", ALLOWED_STUDY_STATUS)
        _require_in(self.budget_pressure, "budget_pressure", ALLOWED_BUDGET_PRESSURE)
        _require_non_empty(self.summary_cn, "summary_cn")
        if self.current_trial_id is not None:
            _require_non_empty(self.current_trial_id, "current_trial_id")
        if self.best_trial_id is not None:
            _require_non_empty(self.best_trial_id, "best_trial_id")
        if self.latest_decision is not None:
            _require_in(self.latest_decision, "latest_decision", ALLOWED_DECISIONS)
        if self.business_success_rate is not None:
            _require_ratio(self.business_success_rate, "business_success_rate")
        if self.business_success_threshold is not None:
            _require_ratio(self.business_success_threshold, "business_success_threshold")
        if self.latest_gate_status is not None:
            _require_in(self.latest_gate_status, "latest_gate_status", ALLOWED_BUSINESS_GATE_STATUS)
        if self.final_reason is not None:
            _require_non_empty(self.final_reason, "final_reason")
        if self.final_detail is not None:
            _require_non_empty(self.final_detail, "final_detail")
        if any(not isinstance(item, str) or not item.strip() for item in self.next_actions_cn):
            raise ValueError("next_actions_cn entries must be non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("evidence entries must be non-empty strings")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "StudyStatusRecord":
        return cls(
            study_name=_string(payload, "study_name"),
            task=_string(payload, "task"),
            status=_string(payload, "status"),
            current_trial_id=_optional_string(payload, "current_trial_id"),
            best_trial_id=_optional_string(payload, "best_trial_id"),
            latest_decision=_optional_string(payload, "latest_decision"),
            best_primary_score=_optional_float(payload, "best_primary_score"),
            budget_pressure=_string(payload, "budget_pressure"),
            business_success_rate=_optional_float(payload, "business_success_rate"),
            business_success_threshold=_optional_float(payload, "business_success_threshold"),
            commercial_ready=_optional_bool(payload, "commercial_ready"),
            latest_gate_status=_optional_string(payload, "latest_gate_status"),
            final_reason=_optional_string(payload, "final_reason"),
            final_detail=_optional_string(payload, "final_detail"),
            summary_cn=_string(payload, "summary_cn"),
            next_actions_cn=_string_list(payload, "next_actions_cn"),
            evidence=_string_list(payload, "evidence"),
        )


@dataclass(frozen=True)
class DatasetPlanRecord:
    study_name: str
    task: str
    trial_id: str
    dataset_action: str
    boost_classes: list[str]
    focus_failure_patterns: list[str]
    rationale_cn: str
    evidence: list[str]
    generator_preset: str | None = None
    generator_overrides: dict[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.study_name, "study_name")
        _require_in(self.task, "task", ALLOWED_TASKS)
        _require_non_empty(self.trial_id, "trial_id")
        _require_in(self.dataset_action, "dataset_action", ALLOWED_DATASET_ACTIONS)
        if self.generator_preset is not None:
            _require_non_empty(self.generator_preset, "generator_preset")
        if self.generator_overrides is not None:
            _validate_generator_overrides(self.generator_overrides, "generator_overrides")
        _require_non_empty(self.rationale_cn, "rationale_cn")
        if any(not isinstance(item, str) or not item.strip() for item in self.boost_classes):
            raise ValueError("boost_classes entries must be non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in self.focus_failure_patterns):
            raise ValueError("focus_failure_patterns entries must be non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("evidence entries must be non-empty strings")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> "DatasetPlanRecord":
        return cls(
            study_name=_string(payload, "study_name"),
            task=_string(payload, "task"),
            trial_id=_string(payload, "trial_id"),
            dataset_action=_string(payload, "dataset_action"),
            generator_preset=_optional_string(payload, "generator_preset"),
            generator_overrides=_optional_mapping(payload, "generator_overrides"),
            boost_classes=_string_list(payload, "boost_classes"),
            focus_failure_patterns=_string_list(payload, "focus_failure_patterns"),
            rationale_cn=_string(payload, "rationale_cn"),
            evidence=_string_list(payload, "evidence"),
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


def _leaderboard_ranking_score(entry: LeaderboardEntry) -> float:
    value = entry.metrics.get("ranking_score")
    if isinstance(value, bool):
        return entry.primary_score
    if isinstance(value, (int, float)):
        return float(value)
    return entry.primary_score


def _bool(payload: dict[str, JsonValue], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _optional_bool(payload: dict[str, JsonValue], field_name: str) -> bool | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean or null")
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


def _int_list(payload: dict[str, JsonValue], field_name: str, *, expected_length: int) -> list[int]:
    value = payload.get(field_name)
    if not isinstance(value, list) or len(value) != expected_length:
        raise ValueError(f"{field_name} must be a list of {expected_length} integers")
    result: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"{field_name} must be a list of {expected_length} integers")
        result.append(item)
    return result


def _optional_int_list(
    payload: dict[str, JsonValue],
    field_name: str,
    *,
    expected_length: int,
) -> list[int] | None:
    if payload.get(field_name) is None:
        return None
    return _int_list(payload, field_name, expected_length=expected_length)


def _optional_string_list(payload: dict[str, JsonValue], field_name: str) -> list[str] | None:
    if payload.get(field_name) is None:
        return None
    return _string_list(payload, field_name)


def _require_bbox(value: list[int], field_name: str) -> None:
    if len(value) != 4:
        raise ValueError(f"{field_name} must contain 4 integers")


def _require_point(value: list[int], field_name: str) -> None:
    if len(value) != 2:
        raise ValueError(f"{field_name} must contain 2 integers")


def _validate_generator_overrides(payload: dict[str, JsonValue], field_name: str) -> None:
    if not payload:
        raise ValueError(f"{field_name} must not be empty")
    _validate_allowed_keys(payload, field_name, ALLOWED_GENERATOR_OVERRIDE_TOP_LEVEL)
    project = payload.get("project")
    if project is not None:
        _validate_numeric_mapping(
            _coerce_mapping(project, f"{field_name}.project"),
            f"{field_name}.project",
            integer_fields=ALLOWED_GENERATOR_OVERRIDE_PROJECT_FIELDS,
            number_fields=set(),
        )
    sampling = payload.get("sampling")
    if sampling is not None:
        _validate_numeric_mapping(
            _coerce_mapping(sampling, f"{field_name}.sampling"),
            f"{field_name}.sampling",
            integer_fields=ALLOWED_GENERATOR_OVERRIDE_SAMPLING_FIELDS,
            number_fields=set(),
        )
    effects = payload.get("effects")
    if effects is not None:
        _validate_effects_mapping(_coerce_mapping(effects, f"{field_name}.effects"), f"{field_name}.effects")


def _validate_effects_mapping(payload: dict[str, JsonValue], field_name: str) -> None:
    if not payload:
        raise ValueError(f"{field_name} must not be empty")
    _validate_allowed_keys(payload, field_name, ALLOWED_GENERATOR_OVERRIDE_EFFECTS_SECTIONS)
    common = payload.get("common")
    if common is not None:
        _validate_numeric_mapping(
            _coerce_mapping(common, f"{field_name}.common"),
            f"{field_name}.common",
            integer_fields={"background_blur_radius_min", "background_blur_radius_max"},
            number_fields={"scene_veil_strength"},
        )
    click = payload.get("click")
    if click is not None:
        _validate_numeric_mapping(
            _coerce_mapping(click, f"{field_name}.click"),
            f"{field_name}.click",
            integer_fields={
                "icon_shadow_offset_x_min",
                "icon_shadow_offset_x_max",
                "icon_shadow_offset_y_min",
                "icon_shadow_offset_y_max",
                "icon_edge_blur_radius_min",
                "icon_edge_blur_radius_max",
            },
            number_fields={"icon_shadow_alpha_min", "icon_shadow_alpha_max"},
        )
    slide = payload.get("slide")
    if slide is not None:
        _validate_numeric_mapping(
            _coerce_mapping(slide, f"{field_name}.slide"),
            f"{field_name}.slide",
            integer_fields={
                "gap_shadow_offset_x_min",
                "gap_shadow_offset_x_max",
                "gap_shadow_offset_y_min",
                "gap_shadow_offset_y_max",
                "tile_edge_blur_radius_min",
                "tile_edge_blur_radius_max",
            },
            number_fields={"gap_shadow_alpha_min", "gap_shadow_alpha_max"},
        )


def _validate_numeric_mapping(
    payload: dict[str, JsonValue],
    field_name: str,
    *,
    integer_fields: set[str],
    number_fields: set[str],
) -> None:
    if not payload:
        raise ValueError(f"{field_name} must not be empty")
    allowed_fields = integer_fields | number_fields
    _validate_allowed_keys(payload, field_name, allowed_fields)
    for key, value in payload.items():
        if key in integer_fields:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{field_name}.{key} must be an integer")
        elif key in number_fields:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field_name}.{key} must be a number")


def _validate_allowed_keys(payload: dict[str, JsonValue], field_name: str, allowed: set[str]) -> None:
    unexpected = sorted(key for key in payload if key not in allowed)
    if unexpected:
        raise ValueError(f"{field_name} has unsupported keys: {', '.join(unexpected)}")
