"""Retune-plan fallbacks built from structured trial analysis."""

from __future__ import annotations

from auto_train import contracts, optimize

_GROUP1_DETECTION_FAILURES = {"detection_precision", "detection_recall", "strict_localization"}


def build_retune_plan(
    *,
    summary: contracts.ResultSummaryRecord,
    analysis: contracts.TrialAnalysisRecord,
    decision: contracts.DecisionRecord,
) -> contracts.RetunePlanRecord:
    if decision.decision != "RETUNE":
        raise ValueError("retune plan only supports RETUNE decisions")
    if summary.task == "group1":
        return _build_group1_retune_plan(summary=summary, analysis=analysis)
    return _build_group2_retune_plan(summary=summary, analysis=analysis)


def _build_group1_retune_plan(
    *,
    summary: contracts.ResultSummaryRecord,
    analysis: contracts.TrialAnalysisRecord,
) -> contracts.RetunePlanRecord:
    global_updates = _filter_global_updates(optimize.deterministic_fallback_parameters(summary))
    component_actions: dict[str, str] = {
        "query-detector": "reuse",
        "proposal-detector": "reuse",
        "icon-embedder": "reuse",
    }
    component_updates: dict[str, dict[str, contracts.JsonValue]] = {}

    query_diag = _component_diag(analysis, "query-detector")
    proposal_diag = _component_diag(analysis, "proposal-detector")
    embedder_diag = _component_diag(analysis, "icon-embedder")

    if _status_requires_retrain(query_diag):
        component_actions["query-detector"] = "train"
        if _status_failed(query_diag):
            component_updates["query-detector"] = _detector_updates(query_diag, upgrade_model=False)
    if _status_requires_retrain(proposal_diag) or set(summary.failure_patterns) & _GROUP1_DETECTION_FAILURES:
        component_actions["proposal-detector"] = "train"
        if _status_failed(proposal_diag) or set(summary.failure_patterns) & _GROUP1_DETECTION_FAILURES:
            component_updates["proposal-detector"] = _detector_updates(proposal_diag, upgrade_model=True)
    if _status_requires_retrain(embedder_diag) or _has_embedder_alerts(embedder_diag):
        component_actions["icon-embedder"] = "train"
        if _status_failed(embedder_diag) or _has_embedder_alerts(embedder_diag):
            component_updates["icon-embedder"] = _embedder_updates(embedder_diag)

    if all(action == "reuse" for action in component_actions.values()):
        component_actions["proposal-detector"] = "train"
        component_updates["proposal-detector"] = _detector_updates(proposal_diag, upgrade_model=True)

    selected = [component for component, action in component_actions.items() if action == "train"]
    return contracts.RetunePlanRecord(
        study_name=summary.study_name,
        task=summary.task,
        trial_id=summary.trial_id,
        parameter_updates=global_updates,
        component_actions=component_actions,
        component_parameter_updates=component_updates or None,
        rationale_cn="、".join(selected) + " 继续定向调参，其余组件复用当前结果。",
        evidence=[
            f"trend={summary.trend}",
            f"failure_patterns={', '.join(summary.failure_patterns)}"
            if summary.failure_patterns
            else "failure_patterns=(none)",
            f"global_updates={', '.join(sorted(global_updates))}" if global_updates else "global_updates=(none)",
            f"selected_components={', '.join(selected)}",
        ],
    )


def _build_group2_retune_plan(
    *,
    summary: contracts.ResultSummaryRecord,
    analysis: contracts.TrialAnalysisRecord,
) -> contracts.RetunePlanRecord:
    current = analysis.current_params
    current_epochs = _int_value(current.get("epochs"), default=100)
    current_batch = _int_value(current.get("batch"), default=16)
    current_imgsz = _int_value(current.get("imgsz"), default=192)
    updates: dict[str, contracts.JsonValue] = {
        "epochs": min(current_epochs + 20, 160),
        "batch": 8 if current_batch > 8 else current_batch,
        "imgsz": 224 if current_imgsz < 224 else current_imgsz,
    }
    return contracts.RetunePlanRecord(
        study_name=summary.study_name,
        task=summary.task,
        trial_id=summary.trial_id,
        parameter_updates=updates,
        component_actions=None,
        component_parameter_updates=None,
        rationale_cn="围绕当前定位误差继续做一轮保守调参。",
        evidence=[
            f"trend={summary.trend}",
            f"failure_patterns={', '.join(summary.failure_patterns)}"
            if summary.failure_patterns
            else "failure_patterns=(none)",
        ],
    )


def _component_diag(
    analysis: contracts.TrialAnalysisRecord,
    component: str,
) -> dict[str, contracts.JsonValue]:
    payload = analysis.component_diagnostics.get(component)
    return payload if isinstance(payload, dict) else {}


def _status_failed(payload: dict[str, contracts.JsonValue]) -> bool:
    status = payload.get("status")
    return isinstance(status, str) and status == "failed"


def _status_requires_retrain(payload: dict[str, contracts.JsonValue]) -> bool:
    status = payload.get("status")
    return not isinstance(status, str) or status != "passed"


def _detector_updates(
    payload: dict[str, contracts.JsonValue],
    *,
    upgrade_model: bool,
) -> dict[str, contracts.JsonValue]:
    current = payload.get("current_params")
    params = current if isinstance(current, dict) else {}
    current_epochs = _int_value(params.get("epochs"), default=120)
    current_batch = _int_value(params.get("batch"), default=16)
    current_imgsz = _int_value(params.get("imgsz"), default=640)
    current_model = params.get("model")
    updates: dict[str, contracts.JsonValue] = {
        "epochs": min(current_epochs + 20, 180),
        "batch": 8 if current_batch > 8 else current_batch,
        "imgsz": 640 if current_imgsz < 640 else current_imgsz,
    }
    if upgrade_model and isinstance(current_model, str) and current_model == "yolo26n.pt":
        updates["model"] = "yolo26s.pt"
    return updates


def _embedder_updates(payload: dict[str, contracts.JsonValue]) -> dict[str, contracts.JsonValue]:
    current = payload.get("current_params")
    params = current if isinstance(current, dict) else {}
    current_epochs = _int_value(params.get("epochs"), default=160)
    current_batch = _int_value(params.get("batch"), default=32)
    return {
        "epochs": min(current_epochs + 20, 220),
        "batch": 48 if current_batch < 48 else current_batch,
        "imgsz": 96,
    }


def _has_embedder_alerts(payload: dict[str, contracts.JsonValue]) -> bool:
    alerts = payload.get("signal_summary")
    return isinstance(alerts, list) and any(isinstance(item, str) and item.strip() for item in alerts)


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return default


def _filter_global_updates(
    payload: dict[str, contracts.JsonValue],
) -> dict[str, contracts.JsonValue]:
    return {
        key: value
        for key, value in payload.items()
        if key in contracts.ALLOWED_RETUNE_PARAM_FIELDS
    }
