"""Early intervention rules for group1 component quality gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass

QUERY_COMPONENT = "query-detector"
PROPOSAL_COMPONENT = "proposal-detector"
EMBEDDER_COMPONENT = "icon-embedder"

QUERY_ITEM_RECALL_SEVERE_MIN = 0.995
QUERY_EXACT_COUNT_SEVERE_MIN = 0.990
QUERY_STRICT_HIT_SEVERE_MIN = 0.990

PROPOSAL_OBJECT_RECALL_SEVERE_MIN = 0.992
PROPOSAL_FULL_RECALL_SEVERE_MIN = 0.950
PROPOSAL_STRICT_HIT_SEVERE_MIN = 0.900
PROPOSAL_FALSE_POSITIVE_SEVERE_MAX = 0.250

EMBEDDER_SCENE_RECALL_AT_1_SEVERE_MIN = 0.940
EMBEDDER_SCENE_RECALL_AT_3_SEVERE_MIN = 0.980
EMBEDDER_IDENTITY_RECALL_AT_1_SEVERE_MIN = 0.750
EMBEDDER_SAME_TEMPLATE_ERROR_SEVERE_MAX = 0.500


@dataclass(frozen=True)
class EarlyIntervention:
    stage: str
    component: str
    reason: str
    failure_patterns: list[str]
    evidence: list[str]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def assess_group1_gate(
    *,
    stage: str,
    component: str,
    gate_payload: dict[str, object],
) -> EarlyIntervention | None:
    """Return an intervention when a failed component gate should stop downstream work."""

    if _gate_status(gate_payload) != "failed":
        return None
    metrics = _gate_numeric_metrics(gate_payload)
    if component == QUERY_COMPONENT:
        return _assess_query(stage=stage, component=component, metrics=metrics)
    if component == PROPOSAL_COMPONENT:
        return _assess_proposal(stage=stage, component=component, metrics=metrics)
    if component == EMBEDDER_COMPONENT:
        return _assess_embedder(stage=stage, component=component, metrics=metrics)
    return None


def _assess_query(
    *,
    stage: str,
    component: str,
    metrics: dict[str, float],
) -> EarlyIntervention | None:
    patterns: list[str] = []
    reasons: list[str] = []
    if _below(metrics, "query_item_recall", QUERY_ITEM_RECALL_SEVERE_MIN):
        patterns.append("detection_recall")
        reasons.append("query_gate_severe_recall_gap")
    if _below(metrics, "query_exact_count_rate", QUERY_EXACT_COUNT_SEVERE_MIN):
        patterns.append("detection_recall")
        reasons.append("query_gate_severe_exact_count_gap")
    if _below(metrics, "query_strict_hit_rate", QUERY_STRICT_HIT_SEVERE_MIN):
        patterns.append("strict_localization")
        reasons.append("query_gate_severe_strict_hit_gap")
    if not reasons:
        return None
    reason = _first_reason(reasons)
    return EarlyIntervention(
        stage=stage,
        component=component,
        reason=reason,
        failure_patterns=_unique(patterns),
        evidence=_evidence(
            stage=stage,
            component=component,
            reason=reason,
            metrics=metrics,
            keys=(
                "query_item_recall",
                "query_exact_count_rate",
                "query_strict_hit_rate",
            ),
        ),
        metrics=metrics,
    )


def _assess_proposal(
    *,
    stage: str,
    component: str,
    metrics: dict[str, float],
) -> EarlyIntervention | None:
    patterns: list[str] = []
    reasons: list[str] = []
    if _below(metrics, "proposal_object_recall", PROPOSAL_OBJECT_RECALL_SEVERE_MIN):
        patterns.append("detection_recall")
        reasons.append("proposal_gate_severe_recall_gap")
    if _below(metrics, "proposal_full_recall_rate", PROPOSAL_FULL_RECALL_SEVERE_MIN):
        patterns.append("detection_recall")
        reasons.append("proposal_gate_severe_full_recall_gap")
    if _below(metrics, "proposal_strict_hit_rate", PROPOSAL_STRICT_HIT_SEVERE_MIN):
        patterns.append("strict_localization")
        reasons.append("proposal_gate_severe_strict_hit_gap")
    if _above(metrics, "proposal_false_positive_per_sample", PROPOSAL_FALSE_POSITIVE_SEVERE_MAX):
        patterns.append("detection_precision")
        reasons.append("proposal_gate_severe_false_positive_gap")
    if not reasons:
        return None
    reason = _first_reason(reasons)
    return EarlyIntervention(
        stage=stage,
        component=component,
        reason=reason,
        failure_patterns=_unique(patterns),
        evidence=_evidence(
            stage=stage,
            component=component,
            reason=reason,
            metrics=metrics,
            keys=(
                "proposal_object_recall",
                "proposal_full_recall_rate",
                "proposal_strict_hit_rate",
                "proposal_false_positive_per_sample",
            ),
        ),
        metrics=metrics,
    )


def _assess_embedder(
    *,
    stage: str,
    component: str,
    metrics: dict[str, float],
) -> EarlyIntervention | None:
    patterns: list[str] = []
    reasons: list[str] = []
    if _below(metrics, "embedding_scene_recall_at_1", EMBEDDER_SCENE_RECALL_AT_1_SEVERE_MIN):
        patterns.append("embedding_recall")
        reasons.append("embedder_gate_severe_scene_recall_gap")
    if _below(metrics, "embedding_scene_recall_at_3", EMBEDDER_SCENE_RECALL_AT_3_SEVERE_MIN):
        patterns.append("embedding_recall")
        reasons.append("embedder_gate_severe_scene_recall_gap")
    if _below(metrics, "embedding_identity_recall_at_1", EMBEDDER_IDENTITY_RECALL_AT_1_SEVERE_MIN):
        patterns.append("embedding_identity")
        reasons.append("embedder_gate_severe_identity_gap")
    if _above(
        metrics,
        "embedding_same_template_top1_error_rate",
        EMBEDDER_SAME_TEMPLATE_ERROR_SEVERE_MAX,
    ):
        patterns.append("same_template_confusion")
        reasons.append("embedder_gate_severe_same_template_confusion")
    if not reasons:
        return None
    reason = _first_reason(reasons)
    return EarlyIntervention(
        stage=stage,
        component=component,
        reason=reason,
        failure_patterns=_unique(patterns),
        evidence=_evidence(
            stage=stage,
            component=component,
            reason=reason,
            metrics=metrics,
            keys=(
                "embedding_scene_recall_at_1",
                "embedding_scene_recall_at_3",
                "embedding_identity_recall_at_1",
                "embedding_same_template_top1_error_rate",
            ),
        ),
        metrics=metrics,
    )


def _gate_status(gate_payload: dict[str, object]) -> str:
    status = gate_payload.get("status")
    if isinstance(status, str) and status.strip():
        return status
    gate = gate_payload.get("gate")
    if isinstance(gate, dict):
        gate_status = gate.get("status")
        if isinstance(gate_status, str) and gate_status.strip():
            return gate_status
    return "missing"


def _gate_numeric_metrics(gate_payload: dict[str, object]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    raw_metrics = gate_payload.get("metrics")
    if isinstance(raw_metrics, dict):
        metrics.update(_numeric_mapping(raw_metrics))
    gate = gate_payload.get("gate")
    if isinstance(gate, dict):
        observed = gate.get("observed")
        if isinstance(observed, dict):
            metrics.update(_numeric_mapping(observed))
    return metrics


def _numeric_mapping(payload: dict[object, object]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        result[key] = float(value)
    return result


def _below(metrics: dict[str, float], key: str, threshold: float) -> bool:
    value = metrics.get(key)
    return value is not None and value < threshold


def _above(metrics: dict[str, float], key: str, threshold: float) -> bool:
    value = metrics.get(key)
    return value is not None and value > threshold


def _evidence(
    *,
    stage: str,
    component: str,
    reason: str,
    metrics: dict[str, float],
    keys: tuple[str, ...],
) -> list[str]:
    evidence = [
        "quality_intervention=group1_component_gate",
        f"stage={stage}",
        f"component={component}",
        f"reason={reason}",
    ]
    for key in keys:
        value = metrics.get(key)
        if value is not None:
            evidence.append(f"{key}={value:.6f}")
    return evidence


def _first_reason(reasons: list[str]) -> str:
    return reasons[0] if reasons else "group1_component_gate_failed"


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
