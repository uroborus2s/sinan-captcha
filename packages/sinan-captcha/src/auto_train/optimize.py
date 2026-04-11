"""Optimization boundaries for Optuna-backed retune flows."""

from __future__ import annotations

from dataclasses import dataclass
import importlib

from auto_train import contracts, policies


@dataclass(frozen=True)
class SearchSpace:
    task: str
    parameters: dict[str, tuple[contracts.JsonValue, ...]]

    def __post_init__(self) -> None:
        if self.task not in contracts.ALLOWED_TASKS:
            raise ValueError(f"unsupported search space task: {self.task}")
        for name, values in self.parameters.items():
            if not name.strip():
                raise ValueError("parameter names must not be empty")
            if not values:
                raise ValueError(f"parameter {name} must provide at least one value")


@dataclass(frozen=True)
class OptimizationPlan:
    task: str
    decision: str
    use_optuna: bool
    engine: str
    reason: str
    dataset_action: str
    train_action: str
    base_run: str | None
    search_space: SearchSpace
    fallback_parameters: dict[str, contracts.JsonValue]

    def __post_init__(self) -> None:
        if self.task not in contracts.ALLOWED_TASKS:
            raise ValueError(f"unsupported optimization task: {self.task}")
        if self.decision not in contracts.ALLOWED_DECISIONS:
            raise ValueError(f"unsupported optimization decision: {self.decision}")
        if self.engine not in {"optuna", "rules", "disabled"}:
            raise ValueError("engine must be one of: disabled, optuna, rules")
        if not self.reason.strip():
            raise ValueError("reason must not be empty")
        if not self.dataset_action.strip():
            raise ValueError("dataset_action must not be empty")
        if not self.train_action.strip():
            raise ValueError("train_action must not be empty")
        if self.base_run is not None and not self.base_run.strip():
            raise ValueError("base_run must not be empty when provided")


@dataclass(frozen=True)
class PruningRequest:
    summary: contracts.ResultSummaryRecord
    decision: contracts.DecisionRecord
    plateau_detected: bool
    no_improve_trials: int
    max_no_improve_trials: int | None = None

    def __post_init__(self) -> None:
        if self.no_improve_trials < 0:
            raise ValueError("no_improve_trials must not be negative")
        if self.max_no_improve_trials is not None and self.max_no_improve_trials <= 0:
            raise ValueError("max_no_improve_trials must be greater than 0")


@dataclass(frozen=True)
class PruningDecision:
    should_prune: bool
    should_stop_search: bool
    fallback_to_rules: bool
    reason: str
    fallback_decision: str | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("reason must not be empty")
        if self.fallback_decision is not None and self.fallback_decision not in contracts.ALLOWED_DECISIONS:
            raise ValueError(f"unsupported fallback decision: {self.fallback_decision}")


GROUP1_SEARCH_SPACE = SearchSpace(
    task="group1",
    parameters={
        "model": ("yolo26n.pt", "yolo26s.pt"),
        "epochs": (100, 120, 140, 160),
        "batch": (8, 16),
        "imgsz": (512, 640),
    },
)

GROUP2_SEARCH_SPACE = SearchSpace(
    task="group2",
    parameters={
        "model": ("paired_cnn_v1",),
        "epochs": (80, 100, 120, 140),
        "batch": (8, 16),
        "imgsz": (160, 192, 224),
    },
)

_SEARCH_SPACES = {
    "group1": GROUP1_SEARCH_SPACE,
    "group2": GROUP2_SEARCH_SPACE,
}


def search_space_for(task: str) -> SearchSpace:
    try:
        return _SEARCH_SPACES[task]
    except KeyError as exc:
        raise ValueError(f"unsupported search space task: {task}") from exc


def is_optuna_available() -> bool:
    try:
        importlib.import_module("optuna")
    except Exception:
        return False
    return True


def build_optimization_plan(
    *,
    summary: contracts.ResultSummaryRecord,
    decision: contracts.DecisionRecord,
    optuna_available: bool | None = None,
) -> OptimizationPlan:
    search_space = search_space_for(summary.task)
    dataset_action = _action_value(decision.next_action, "dataset_action", default="reuse")
    train_action = _action_value(decision.next_action, "train_action", default="from_run")
    base_run = _optional_action_value(decision.next_action, "base_run") or summary.train_name
    fallback_parameters = deterministic_fallback_parameters(summary)

    if decision.decision != "RETUNE":
        return OptimizationPlan(
            task=summary.task,
            decision=decision.decision,
            use_optuna=False,
            engine="disabled",
            reason="decision_not_retune",
            dataset_action=dataset_action,
            train_action=train_action,
            base_run=base_run,
            search_space=SearchSpace(task=summary.task, parameters={}),
            fallback_parameters={},
        )

    available = optuna_available if optuna_available is not None else is_optuna_available()
    if not available:
        return OptimizationPlan(
            task=summary.task,
            decision=decision.decision,
            use_optuna=False,
            engine="rules",
            reason="optuna_unavailable",
            dataset_action=dataset_action,
            train_action=train_action,
            base_run=base_run,
            search_space=search_space,
            fallback_parameters=fallback_parameters,
        )

    return OptimizationPlan(
        task=summary.task,
        decision=decision.decision,
        use_optuna=True,
        engine="optuna",
        reason="retune_search_enabled",
        dataset_action=dataset_action,
        train_action=train_action,
        base_run=base_run,
        search_space=search_space,
        fallback_parameters=fallback_parameters,
    )


def deterministic_fallback_parameters(summary: contracts.ResultSummaryRecord) -> dict[str, contracts.JsonValue]:
    failure_patterns = set(summary.failure_patterns)
    if summary.task == "group1":
        return {
            "model": "yolo26s.pt" if "strict_localization" in failure_patterns else "yolo26n.pt",
            "epochs": 140 if summary.trend != "improving" or "detection_recall" in failure_patterns else 120,
            "batch": 8 if {"detection_recall", "strict_localization"} & failure_patterns else 16,
            "imgsz": 640,
        }

    return {
        "model": "paired_cnn_v1",
        "epochs": 120 if summary.trend != "improving" or failure_patterns else 100,
        "batch": 8 if "low_iou" in failure_patterns else 16,
        "imgsz": 224 if {"center_offset", "low_iou"} & failure_patterns else 192,
    }


def assess_pruning(request: PruningRequest) -> PruningDecision:
    if request.decision.decision != "RETUNE":
        return PruningDecision(
            should_prune=False,
            should_stop_search=False,
            fallback_to_rules=False,
            reason="decision_not_retune",
        )

    rule_recommendation = policies.evaluate_summary(request.summary)

    if (
        request.max_no_improve_trials is not None
        and request.no_improve_trials >= request.max_no_improve_trials
    ):
        return PruningDecision(
            should_prune=True,
            should_stop_search=True,
            fallback_to_rules=True,
            reason="no_improve_limit_reached",
            fallback_decision=rule_recommendation.decision,
        )

    if rule_recommendation.decision != "RETUNE":
        return PruningDecision(
            should_prune=False,
            should_stop_search=True,
            fallback_to_rules=True,
            reason="rule_boundary_override",
            fallback_decision=rule_recommendation.decision,
        )

    if request.plateau_detected:
        return PruningDecision(
            should_prune=True,
            should_stop_search=False,
            fallback_to_rules=False,
            reason="plateau_prune_candidate",
        )

    return PruningDecision(
        should_prune=False,
        should_stop_search=False,
        fallback_to_rules=False,
        reason="continue_search",
    )


def _action_value(payload: dict[str, contracts.JsonValue], key: str, *, default: str) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return default


def _optional_action_value(payload: dict[str, contracts.JsonValue], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None
