"""Task-specific autonomous training policies for group1 and group2 studies."""

from __future__ import annotations

from dataclasses import dataclass

from auto_train import contracts
from group2_semantics import (
    GROUP2_DATASET_GAP_POINT_HIT_THRESHOLD,
    GROUP2_LOCALIZATION_ALERT_CENTER_ERROR_PX,
)


@dataclass(frozen=True)
class TaskPolicy:
    task: str
    primary_metric: str
    secondary_metric: str
    business_metric: str | None = None
    penalty_metric: str | None = None
    plateau_window: int = 3
    min_delta: float = 0.005
    promote_primary_threshold: float = 0.0
    promote_secondary_threshold: float = 0.0
    promote_business_threshold: float | None = None
    promote_penalty_max: float | None = None
    abandon_primary_floor: float = 0.0
    abandon_delta_vs_best: float = -0.05

    def __post_init__(self) -> None:
        if self.task not in contracts.ALLOWED_TASKS:
            raise ValueError(f"unsupported policy task: {self.task}")
        if not self.primary_metric.strip():
            raise ValueError("primary_metric must not be empty")
        if not self.secondary_metric.strip():
            raise ValueError("secondary_metric must not be empty")
        if self.business_metric is not None and not self.business_metric.strip():
            raise ValueError("business_metric must not be empty when provided")
        if self.penalty_metric is not None and not self.penalty_metric.strip():
            raise ValueError("penalty_metric must not be empty when provided")
        if self.plateau_window <= 0:
            raise ValueError("plateau_window must be greater than 0")
        if self.min_delta < 0:
            raise ValueError("min_delta must not be negative")


@dataclass(frozen=True)
class PolicyRecommendation:
    task: str
    decision: str
    reason: str
    evidence: list[str]

    def __post_init__(self) -> None:
        if self.task not in contracts.ALLOWED_TASKS:
            raise ValueError(f"unsupported recommendation task: {self.task}")
        if self.decision not in contracts.ALLOWED_DECISIONS:
            raise ValueError(f"unsupported recommendation decision: {self.decision}")
        if not self.reason.strip():
            raise ValueError("reason must not be empty")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("evidence entries must be non-empty strings")


GROUP1_POLICY = TaskPolicy(
    task="group1",
    primary_metric="map50_95",
    secondary_metric="recall",
    business_metric="full_sequence_hit_rate",
    plateau_window=3,
    min_delta=0.005,
    promote_primary_threshold=0.82,
    promote_secondary_threshold=0.88,
    promote_business_threshold=0.85,
    abandon_primary_floor=0.75,
    abandon_delta_vs_best=-0.06,
)

GROUP2_POLICY = TaskPolicy(
    task="group2",
    primary_metric="point_hit_rate",
    secondary_metric="mean_iou",
    penalty_metric="mean_center_error_px",
    plateau_window=3,
    min_delta=0.01,
    promote_primary_threshold=0.93,
    promote_secondary_threshold=0.85,
    promote_penalty_max=8.0,
    abandon_primary_floor=0.75,
    abandon_delta_vs_best=-0.08,
)

_POLICIES = {
    GROUP1_POLICY.task: GROUP1_POLICY,
    GROUP2_POLICY.task: GROUP2_POLICY,
}

_GROUP1_DATA_FAILURES = {"sequence_consistency", "order_errors"}
_GROUP1_RETUNE_FAILURES = {"detection_precision", "detection_recall", "strict_localization"}
_GROUP2_DATA_FAILURES = {"point_hits", "low_iou"}
_GROUP2_RETUNE_FAILURES = {"center_offset"}


def policy_for_task(task: str) -> TaskPolicy:
    try:
        return _POLICIES[task]
    except KeyError as exc:
        raise ValueError(f"unsupported policy task: {task}") from exc


def evaluate_summary(summary: contracts.ResultSummaryRecord) -> PolicyRecommendation:
    policy = policy_for_task(summary.task)
    if policy.task == "group1":
        return _evaluate_group1(policy, summary)
    return _evaluate_group2(policy, summary)


def _evaluate_group1(policy: TaskPolicy, summary: contracts.ResultSummaryRecord) -> PolicyRecommendation:
    primary_score = _metric(summary, policy.primary_metric)
    recall = _metric(summary, policy.secondary_metric)
    full_sequence_hit_rate = _metric(summary, policy.business_metric)
    failure_patterns = set(summary.failure_patterns)

    if _meets_group1_targets(policy, summary, primary_score, recall, full_sequence_hit_rate):
        return _recommend(
            summary.task,
            "PROMOTE_BRANCH",
            "group1_targets_met",
            primary_score=primary_score,
            recall=recall,
            business_metric=full_sequence_hit_rate,
        )

    if _is_regressed_branch(policy, summary, primary_score):
        return _recommend(
            summary.task,
            "ABANDON_BRANCH",
            "group1_regressed_branch",
            primary_score=primary_score,
            delta_vs_best=summary.delta_vs_best,
        )

    if summary.weak_classes or failure_patterns & _GROUP1_DATA_FAILURES:
        return _recommend(
            summary.task,
            "REGENERATE_DATA",
            "group1_data_quality_gap",
            primary_score=primary_score,
            recall=recall,
            business_metric=full_sequence_hit_rate,
            weak_classes=summary.weak_classes,
            failure_patterns=summary.failure_patterns,
        )

    if "detection_recall" in failure_patterns or (recall is not None and recall < policy.promote_secondary_threshold):
        return _recommend(
            summary.task,
            "RETUNE",
            "group1_recall_bottleneck",
            primary_score=primary_score,
            recall=recall,
            failure_patterns=summary.failure_patterns,
        )

    if failure_patterns & _GROUP1_RETUNE_FAILURES:
        return _recommend(
            summary.task,
            "RETUNE",
            "group1_detection_bottleneck",
            primary_score=primary_score,
            recall=recall,
            failure_patterns=summary.failure_patterns,
        )

    return _recommend(
        summary.task,
        "RETUNE",
        "group1_continue_tuning",
        primary_score=primary_score,
        recall=recall,
        business_metric=full_sequence_hit_rate,
        trend=summary.trend,
    )


def _evaluate_group2(policy: TaskPolicy, summary: contracts.ResultSummaryRecord) -> PolicyRecommendation:
    point_hit_rate = _metric(summary, policy.primary_metric)
    mean_iou = _metric(summary, policy.secondary_metric)
    center_error = _metric(summary, policy.penalty_metric)
    failure_patterns = set(summary.failure_patterns)

    if _meets_group2_targets(policy, summary, point_hit_rate, mean_iou, center_error):
        return _recommend(
            summary.task,
            "PROMOTE_BRANCH",
            "group2_targets_met",
            primary_score=point_hit_rate,
            secondary_score=mean_iou,
            penalty_metric=center_error,
        )

    if _is_regressed_branch(policy, summary, point_hit_rate):
        return _recommend(
            summary.task,
            "ABANDON_BRANCH",
            "group2_regressed_branch",
            primary_score=point_hit_rate,
            delta_vs_best=summary.delta_vs_best,
        )

    if (
        (point_hit_rate is not None and point_hit_rate < GROUP2_DATASET_GAP_POINT_HIT_THRESHOLD)
        or "low_iou" in failure_patterns
        or ("point_hits" in failure_patterns and (summary.failure_count or 0) >= 6)
    ):
        return _recommend(
            summary.task,
            "REGENERATE_DATA",
            "group2_dataset_contract_gap",
            primary_score=point_hit_rate,
            secondary_score=mean_iou,
            penalty_metric=center_error,
            failure_patterns=summary.failure_patterns,
        )

    if (
        "center_offset" in failure_patterns
        or (center_error is not None and center_error > GROUP2_LOCALIZATION_ALERT_CENTER_ERROR_PX)
    ):
        return _recommend(
            summary.task,
            "RETUNE",
            "group2_localization_offset",
            primary_score=point_hit_rate,
            secondary_score=mean_iou,
            penalty_metric=center_error,
            failure_patterns=summary.failure_patterns,
        )

    return _recommend(
        summary.task,
        "RETUNE",
        "group2_continue_tuning",
        primary_score=point_hit_rate,
        secondary_score=mean_iou,
        penalty_metric=center_error,
        trend=summary.trend,
    )


def _meets_group1_targets(
    policy: TaskPolicy,
    summary: contracts.ResultSummaryRecord,
    primary_score: float | None,
    recall: float | None,
    full_sequence_hit_rate: float | None,
) -> bool:
    if not summary.evaluation_available:
        return False
    if summary.weak_classes or set(summary.failure_patterns) & _GROUP1_DATA_FAILURES:
        return False
    if primary_score is None or recall is None or full_sequence_hit_rate is None:
        return False
    return (
        primary_score >= policy.promote_primary_threshold
        and recall >= policy.promote_secondary_threshold
        and full_sequence_hit_rate >= (policy.promote_business_threshold or 0.0)
    )


def _meets_group2_targets(
    policy: TaskPolicy,
    summary: contracts.ResultSummaryRecord,
    point_hit_rate: float | None,
    mean_iou: float | None,
    center_error: float | None,
) -> bool:
    if not summary.evaluation_available:
        return False
    if set(summary.failure_patterns) & (_GROUP2_DATA_FAILURES | _GROUP2_RETUNE_FAILURES):
        return False
    if point_hit_rate is None or mean_iou is None or center_error is None:
        return False
    return (
        point_hit_rate >= policy.promote_primary_threshold
        and mean_iou >= policy.promote_secondary_threshold
        and center_error <= (policy.promote_penalty_max or 0.0)
    )


def _is_regressed_branch(
    policy: TaskPolicy,
    summary: contracts.ResultSummaryRecord,
    primary_score: float | None,
) -> bool:
    return (
        summary.trend == "declining"
        and summary.delta_vs_best is not None
        and summary.delta_vs_best <= policy.abandon_delta_vs_best
        and primary_score is not None
        and primary_score < policy.abandon_primary_floor
    )


def _recommend(
    task: str,
    decision: str,
    reason: str,
    *,
    primary_score: float | None = None,
    recall: float | None = None,
    secondary_score: float | None = None,
    business_metric: float | None = None,
    penalty_metric: float | None = None,
    delta_vs_best: float | None = None,
    weak_classes: list[str] | None = None,
    failure_patterns: list[str] | None = None,
    trend: str | None = None,
) -> PolicyRecommendation:
    evidence: list[str] = []
    if primary_score is not None:
        evidence.append(f"primary_score={primary_score:.6f}")
    if recall is not None:
        evidence.append(f"recall={recall:.6f}")
    if secondary_score is not None:
        evidence.append(f"secondary_score={secondary_score:.6f}")
    if business_metric is not None:
        evidence.append(f"business_metric={business_metric:.6f}")
    if penalty_metric is not None:
        evidence.append(f"penalty_metric={penalty_metric:.6f}")
    if delta_vs_best is not None:
        evidence.append(f"delta_vs_best={delta_vs_best:+.6f}")
    if weak_classes:
        evidence.append(f"weak_classes={', '.join(weak_classes)}")
    if failure_patterns:
        evidence.append(f"failure_patterns={', '.join(failure_patterns)}")
    if trend is not None:
        evidence.append(f"trend={trend}")
    if not evidence:
        evidence.append("policy_evaluation")
    return PolicyRecommendation(
        task=task,
        decision=decision,
        reason=reason,
        evidence=evidence,
    )


def _metric(summary: contracts.ResultSummaryRecord, key: str | None) -> float | None:
    if key is None:
        return None
    if key == summary.primary_metric and summary.primary_score is not None:
        return float(summary.primary_score)
    for source in (summary.evaluation_metrics, summary.test_metrics):
        value = source.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        return float(value)
    return None
