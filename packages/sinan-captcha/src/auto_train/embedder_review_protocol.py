"""Local judge protocol for group1 icon-embedder stage reviews."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from auto_train import contracts, judge_protocol, opencode_runtime, storage

EMBEDDER_REVIEW_DECISION_CONTINUE = "CONTINUE"
EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE = "STOP_AND_ADVANCE"
EMBEDDER_REVIEW_DECISION_REBUILD_HARDSET = "REBUILD_HARDSET"
EMBEDDER_REVIEW_DECISION_ESCALATE_DETECTOR = "ESCALATE_DETECTOR"

ALLOWED_EMBEDDER_REVIEW_DECISIONS = {
    EMBEDDER_REVIEW_DECISION_CONTINUE,
    EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
    EMBEDDER_REVIEW_DECISION_REBUILD_HARDSET,
    EMBEDDER_REVIEW_DECISION_ESCALATE_DETECTOR,
}
BASE_EMBEDDER_REVIEW_DECISIONS = {
    EMBEDDER_REVIEW_DECISION_CONTINUE,
    EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
}
HARD_EMBEDDER_REVIEW_DECISIONS = ALLOWED_EMBEDDER_REVIEW_DECISIONS
EMBEDDER_REVIEW_DECISION_MODE_LLM_FIRST = "llm_first"
EMBEDDER_REVIEW_DECISION_MODE_GUARDRAIL_OVERRIDE = "guardrail_override"
ALLOWED_EMBEDDER_REVIEW_DECISION_MODES = {
    EMBEDDER_REVIEW_DECISION_MODE_LLM_FIRST,
    EMBEDDER_REVIEW_DECISION_MODE_GUARDRAIL_OVERRIDE,
}
DEFAULT_EMBEDDER_REVIEW_DECISION_MODE = EMBEDDER_REVIEW_DECISION_MODE_LLM_FIRST

DEFAULT_EMBEDDER_REVIEW_MIN_EPOCHS = 8
DEFAULT_EMBEDDER_REVIEW_WINDOW = 3
DEFAULT_EMBEDDER_REVIEW_MIN_DELTA = 0.001
MAX_EMBEDDER_HARDSET_REBUILDS_PER_TRIAL = 1
BASE_FORCE_HARDSET_MIN_EPOCH = 20
BASE_FORCE_HARDSET_MAX_EXACT_RECALL_AT_1 = 0.10
BASE_FORCE_HARDSET_MIN_POSITIVE_RANK_MEAN = 20.0
BASE_FORCE_HARDSET_MIN_IDENTITY_GAP = 0.25
BASE_STALE_BEST_EPOCH_GAP = 4
BASE_STALE_MAX_EXACT_RECALL_AT_1 = 0.08
BASE_STALE_MIN_SCENE_RECALL_AT_1 = 0.85
BASE_STALE_MIN_SAME_TEMPLATE_ERROR = 0.35
BASE_STALE_MIN_POSITIVE_RANK_MEAN = 100.0
HARD_FORCE_REBUILD_MAX_EXACT_RECALL_AT_1 = 0.05
HARD_FORCE_REBUILD_MIN_IDENTITY_RECALL_AT_1 = 0.80
HARD_FORCE_REBUILD_CONSECUTIVE_REVIEWS = 2


@dataclass(frozen=True)
class EmbedderReviewContext:
    study_name: str
    task: str
    trial_id: str
    train_name: str
    stage: str
    epoch: int
    review_window: int
    rebuild_count: int
    dataset_config: str
    image_size: int
    batch_size: int
    best_epoch: int | None
    best_embedding_recall_at_1: float | None
    current_metrics: dict[str, contracts.JsonValue]
    recent_history: list[dict[str, contracts.JsonValue]]
    review_history: list[dict[str, contracts.JsonValue]]
    decision_mode: str = DEFAULT_EMBEDDER_REVIEW_DECISION_MODE
    guardrail_alerts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.decision_mode not in ALLOWED_EMBEDDER_REVIEW_DECISION_MODES:
            allowed = ", ".join(sorted(ALLOWED_EMBEDDER_REVIEW_DECISION_MODES))
            raise ValueError(f"decision_mode must be one of: {allowed}")

    def to_dict(self) -> dict[str, contracts.JsonValue]:
        return asdict(self)


@dataclass(frozen=True)
class EmbedderReviewRecord:
    stage: str
    epoch: int
    decision: str
    confidence: float
    reason: str
    next_action: dict[str, contracts.JsonValue]
    evidence: list[str]
    agent: contracts.AgentRef
    metrics_snapshot: dict[str, float] | None = None
    used_fallback: bool = False
    fallback_reason: str | None = None

    def __post_init__(self) -> None:
        if self.decision not in ALLOWED_EMBEDDER_REVIEW_DECISIONS:
            allowed = ", ".join(sorted(ALLOWED_EMBEDDER_REVIEW_DECISIONS))
            raise ValueError(f"decision must be one of: {allowed}")

    def to_dict(self) -> dict[str, contracts.JsonValue]:
        payload = asdict(self)
        payload["agent"] = self.agent.to_dict()
        return payload


@dataclass(frozen=True)
class EmbedderReviewOutcome:
    record: EmbedderReviewRecord
    used_fallback: bool
    fallback_reason: str | None = None


def should_run_embedder_review(
    *,
    epoch: int,
    min_epochs: int = DEFAULT_EMBEDDER_REVIEW_MIN_EPOCHS,
    window: int = DEFAULT_EMBEDDER_REVIEW_WINDOW,
) -> bool:
    if epoch < max(1, min_epochs):
        return False
    return (epoch - min_epochs) % max(1, window) == 0


def parse_or_fallback_review(
    *,
    raw_output: str,
    context: EmbedderReviewContext,
    agent: contracts.AgentRef,
) -> EmbedderReviewOutcome:
    try:
        parsed = judge_protocol.parse_structured_payload(
            raw_output=raw_output,
            allowed_decisions=_allowed_decisions_for_stage(context.stage),
        )
    except judge_protocol.StructuredJudgePayloadError as exc:
        return fallback_review(
            context=context,
            agent=agent,
            reason_code=exc.reason_code,
        )

    record = EmbedderReviewRecord(
        stage=context.stage,
        epoch=context.epoch,
        decision=parsed.decision,
        confidence=parsed.confidence,
        reason=parsed.reason,
        next_action=parsed.next_action,
        evidence=parsed.evidence,
        agent=agent,
        metrics_snapshot=_metrics_snapshot(context.current_metrics),
        used_fallback=False,
        fallback_reason=None,
    )
    record = apply_review_guardrails(context=context, record=record)
    return EmbedderReviewOutcome(
        record=record,
        used_fallback=False,
        fallback_reason=None,
    )


def fallback_review(
    *,
    context: EmbedderReviewContext,
    agent: contracts.AgentRef,
    reason_code: str,
    extra_evidence: list[str] | None = None,
) -> EmbedderReviewOutcome:
    decision, reason, next_action, evidence = _fallback_review_components(context)
    evidence = [
        f"fallback_reason={reason_code}",
        *evidence,
        *(item for item in (extra_evidence or []) if item.strip()),
    ]
    record = EmbedderReviewRecord(
        stage=context.stage,
        epoch=context.epoch,
        decision=decision,
        confidence=0.45 if reason_code != "runtime_error" else 0.35,
        reason=reason,
        next_action=next_action,
        evidence=evidence,
        agent=agent,
        metrics_snapshot=_metrics_snapshot(context.current_metrics),
        used_fallback=True,
        fallback_reason=reason_code,
    )
    return EmbedderReviewOutcome(record=record, used_fallback=True, fallback_reason=reason_code)


def build_opencode_embedder_reviewer(
    *,
    runtime: opencode_runtime.OpenCodeRuntimeAdapter,
    run_dir: Path,
) -> object:
    reviews_dir = run_dir / "icon-embedder" / "reviews"
    history_path = reviews_dir / "review_history.jsonl"

    def reviewer(context: EmbedderReviewContext) -> EmbedderReviewRecord:
        reviews_dir.mkdir(parents=True, exist_ok=True)
        context_path = reviews_dir / f"context_epoch_{context.epoch:03d}.json"
        storage.write_json_payload(context_path, context.to_dict())
        files = [context_path]
        if history_path.exists():
            files.append(history_path)
        agent = contracts.AgentRef(
            provider="opencode",
            name="review-embedder",
            model=runtime.config.model,
        )
        try:
            result = runtime.run_command(
                "review-embedder",
                arguments=[
                    context.study_name,
                    context.task,
                    context.trial_id,
                    context.stage,
                    str(context.epoch),
                ],
                files=files,
            )
            outcome = parse_or_fallback_review(
                raw_output=result.stdout,
                context=context,
                agent=agent,
            )
        except opencode_runtime.OpenCodeRuntimeError as exc:
            outcome = fallback_review(
                context=context,
                agent=agent,
                reason_code="runtime_error",
                extra_evidence=[str(exc)],
            )
        record_path = reviews_dir / f"review_epoch_{context.epoch:03d}.json"
        storage.write_json_payload(record_path, outcome.record.to_dict())
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(_json_line(outcome.record.to_dict()))
            handle.write("\n")
        return outcome.record

    return reviewer


def _fallback_review_components(
    context: EmbedderReviewContext,
) -> tuple[str, str, dict[str, contracts.JsonValue], list[str]]:
    current_recall_at_1 = _metric_value(context.current_metrics, "embedding_recall_at_1")
    current_recall_at_3 = _metric_value(context.current_metrics, "embedding_recall_at_3")
    current_scene_recall_at_1 = _metric_value(context.current_metrics, "embedding_scene_recall_at_1")
    current_scene_recall_at_3 = _metric_value(context.current_metrics, "embedding_scene_recall_at_3")
    identity_recall_at_1 = _metric_value(context.current_metrics, "embedding_identity_recall_at_1")
    positive_rank_mean = _metric_value(context.current_metrics, "embedding_positive_rank_mean")
    same_template_error = _metric_value(context.current_metrics, "embedding_same_template_top1_error_rate")
    detector_error_rate = _metric_value(context.current_metrics, "embedding_top1_error_scene_target_rate") + _metric_value(
        context.current_metrics,
        "embedding_top1_error_false_positive_rate",
    )
    primary_recall_at_1 = _primary_recall_at_1(context.current_metrics)
    primary_recall_at_3 = _primary_recall_at_3(context.current_metrics)
    plateau = _is_plateau(
        context.recent_history,
        metric_key="embedding_scene_recall_at_1" if _has_scene_recall_metrics(context.current_metrics) else "embedding_recall_at_1",
    )

    evidence = [
        f"plateau={plateau}",
        f"embedding_recall_at_1={current_recall_at_1:.6f}",
        f"embedding_recall_at_3={current_recall_at_3:.6f}",
        f"embedding_scene_recall_at_1={current_scene_recall_at_1:.6f}",
        f"embedding_scene_recall_at_3={current_scene_recall_at_3:.6f}",
        f"embedding_identity_recall_at_1={identity_recall_at_1:.6f}",
        f"embedding_positive_rank_mean={positive_rank_mean:.6f}",
    ]
    if context.best_epoch is not None:
        evidence.append(f"best_epoch={context.best_epoch}")
    if context.best_embedding_recall_at_1 is not None:
        evidence.append(f"best_embedding_recall_at_1={context.best_embedding_recall_at_1:.6f}")

    if primary_recall_at_1 >= 0.97 and primary_recall_at_3 >= 0.995:
        return (
            EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
            "embedder_gate_met",
            _review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE),
            evidence,
        )

    force_hardset, force_evidence = _base_force_hardset_guardrail(context)
    if force_hardset:
        return (
            EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
            "base_low_exact_recall_force_hardset",
            _review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE),
            [*evidence, *force_evidence],
        )

    stale_force_hardset, stale_force_evidence = _base_stale_best_epoch_guardrail(context)
    if stale_force_hardset:
        return (
            EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
            "base_stale_best_epoch_force_hardset",
            _review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE),
            [*evidence, *stale_force_evidence],
        )

    hard_force_decision, hard_force_reason, hard_force_evidence = _hard_force_action_guardrail(
        context=context,
        detector_error_rate=detector_error_rate,
    )
    if hard_force_decision is not None:
        return (
            hard_force_decision,
            hard_force_reason,
            _review_next_action(context.stage, hard_force_decision),
            [*evidence, *hard_force_evidence],
        )

    if not plateau:
        return (
            EMBEDDER_REVIEW_DECISION_CONTINUE,
            "recent_progress_observed",
            _review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_CONTINUE),
            evidence,
        )

    if context.stage == "TRAIN_EMBEDDER_BASE":
        evidence.append("plateau_trigger=base_exact_recall_stalled")
        if identity_recall_at_1 >= current_recall_at_1 + 0.20:
            evidence.append("identity_exact_gap=high")
        if positive_rank_mean >= 10.0:
            evidence.append("positive_rank_mean=high")
        return (
            EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
            "base_plateau_switch_to_hardset",
            _review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE),
            evidence,
        )

    if same_template_error >= 0.25 and context.rebuild_count < MAX_EMBEDDER_HARDSET_REBUILDS_PER_TRIAL:
        evidence.append(f"same_template_top1_error_rate={same_template_error:.6f}")
        evidence.append(f"rebuild_count={context.rebuild_count}")
        return (
            EMBEDDER_REVIEW_DECISION_REBUILD_HARDSET,
            "hard_plateau_same_template_confusion",
            _review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_REBUILD_HARDSET),
            evidence,
        )

    if detector_error_rate >= 0.45:
        evidence.append(f"detector_error_rate={detector_error_rate:.6f}")
        return (
            EMBEDDER_REVIEW_DECISION_ESCALATE_DETECTOR,
            "hard_plateau_detector_noise_dominates",
            _review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_ESCALATE_DETECTOR),
            evidence,
        )

    return (
        EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
        "hard_plateau_no_meaningful_gain",
        _review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE),
        evidence,
    )


def _review_next_action(stage: str, decision: str) -> dict[str, contracts.JsonValue]:
    if decision == EMBEDDER_REVIEW_DECISION_CONTINUE:
        return {"train_action": "continue", "target_stage": stage}
    if decision == EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE:
        return {
            "train_action": "stop_and_advance",
            "target_stage": "EMBEDDER_GATE" if stage == "TRAIN_EMBEDDER_BASE" else "CALIBRATE_MATCHER",
        }
    if decision == EMBEDDER_REVIEW_DECISION_REBUILD_HARDSET:
        return {"train_action": "rebuild_hardset", "target_stage": "BUILD_EMBEDDER_HARDSET"}
    return {"train_action": "escalate_detector", "target_stage": "JUDGE"}


def _allowed_decisions_for_stage(stage: str) -> set[str]:
    if stage == "TRAIN_EMBEDDER_BASE":
        return BASE_EMBEDDER_REVIEW_DECISIONS
    return HARD_EMBEDDER_REVIEW_DECISIONS


def _metric_value(metrics: dict[str, contracts.JsonValue], key: str) -> float:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _is_plateau(
    recent_history: list[dict[str, contracts.JsonValue]],
    *,
    metric_key: str = "embedding_recall_at_1",
) -> bool:
    if len(recent_history) < DEFAULT_EMBEDDER_REVIEW_WINDOW:
        return False
    scores = [_metric_value(item, metric_key) for item in recent_history]
    return (max(scores) - min(scores)) <= DEFAULT_EMBEDDER_REVIEW_MIN_DELTA


def _has_numeric_metric(metrics: dict[str, contracts.JsonValue], key: str) -> bool:
    value = metrics.get(key)
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _has_scene_recall_metrics(metrics: dict[str, contracts.JsonValue]) -> bool:
    return _has_numeric_metric(metrics, "embedding_scene_recall_at_1") or _has_numeric_metric(
        metrics,
        "embedding_scene_recall_at_3",
    )


def _primary_recall_at_1(metrics: dict[str, contracts.JsonValue]) -> float:
    if _has_numeric_metric(metrics, "embedding_scene_recall_at_1"):
        return _metric_value(metrics, "embedding_scene_recall_at_1")
    return _metric_value(metrics, "embedding_recall_at_1")


def _primary_recall_at_3(metrics: dict[str, contracts.JsonValue]) -> float:
    if _has_numeric_metric(metrics, "embedding_scene_recall_at_3"):
        return _metric_value(metrics, "embedding_scene_recall_at_3")
    return _metric_value(metrics, "embedding_recall_at_3")


def _base_force_hardset_guardrail(
    context: EmbedderReviewContext,
) -> tuple[bool, list[str]]:
    if context.stage != "TRAIN_EMBEDDER_BASE":
        return False, []
    current_recall_at_1 = _metric_value(context.current_metrics, "embedding_recall_at_1")
    identity_recall_at_1 = _metric_value(context.current_metrics, "embedding_identity_recall_at_1")
    positive_rank_mean = _metric_value(context.current_metrics, "embedding_positive_rank_mean")
    if context.epoch < BASE_FORCE_HARDSET_MIN_EPOCH:
        return False, []
    if current_recall_at_1 > BASE_FORCE_HARDSET_MAX_EXACT_RECALL_AT_1:
        return False, []
    if positive_rank_mean < BASE_FORCE_HARDSET_MIN_POSITIVE_RANK_MEAN:
        return False, []
    if identity_recall_at_1 < current_recall_at_1 + BASE_FORCE_HARDSET_MIN_IDENTITY_GAP:
        return False, []
    return (
        True,
        [
            "guardrail=base_force_hardset_low_exact_recall",
            f"epoch={context.epoch}",
            f"embedding_recall_at_1={current_recall_at_1:.6f}",
            f"embedding_identity_recall_at_1={identity_recall_at_1:.6f}",
            f"embedding_positive_rank_mean={positive_rank_mean:.6f}",
        ],
    )


def apply_review_guardrails(
    *,
    context: EmbedderReviewContext,
    record: EmbedderReviewRecord,
) -> EmbedderReviewRecord:
    force_hardset, force_evidence = _base_force_hardset_guardrail(context)
    stale_force_hardset, stale_force_evidence = _base_stale_best_epoch_guardrail(context)
    hard_force_decision, hard_force_reason, hard_force_evidence = _hard_force_action_guardrail(
        context=context,
        detector_error_rate=(
            _metric_value(context.current_metrics, "embedding_top1_error_scene_target_rate")
            + _metric_value(context.current_metrics, "embedding_top1_error_false_positive_rate")
        ),
    )
    advisory_evidence = _merge_review_evidence(
        record.evidence,
        context.guardrail_alerts,
        force_evidence,
        stale_force_evidence,
        hard_force_evidence,
    )
    if context.decision_mode != EMBEDDER_REVIEW_DECISION_MODE_GUARDRAIL_OVERRIDE:
        if advisory_evidence == record.evidence:
            return record
        return EmbedderReviewRecord(
            stage=record.stage,
            epoch=record.epoch,
            decision=record.decision,
            confidence=record.confidence,
            reason=record.reason,
            next_action=record.next_action,
            evidence=advisory_evidence,
            agent=record.agent,
            metrics_snapshot=record.metrics_snapshot,
            used_fallback=record.used_fallback,
            fallback_reason=record.fallback_reason,
        )
    if force_hardset and record.decision == EMBEDDER_REVIEW_DECISION_CONTINUE:
        return EmbedderReviewRecord(
            stage=record.stage,
            epoch=record.epoch,
            decision=EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
            confidence=max(record.confidence, 0.8),
            reason="base_low_exact_recall_force_hardset",
            next_action=_review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE),
            evidence=advisory_evidence,
            agent=record.agent,
            metrics_snapshot=record.metrics_snapshot,
            used_fallback=record.used_fallback,
            fallback_reason=record.fallback_reason,
        )
    if stale_force_hardset and record.decision == EMBEDDER_REVIEW_DECISION_CONTINUE:
        return EmbedderReviewRecord(
            stage=record.stage,
            epoch=record.epoch,
            decision=EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE,
            confidence=max(record.confidence, 0.82),
            reason="base_stale_best_epoch_force_hardset",
            next_action=_review_next_action(context.stage, EMBEDDER_REVIEW_DECISION_STOP_AND_ADVANCE),
            evidence=advisory_evidence,
            agent=record.agent,
            metrics_snapshot=record.metrics_snapshot,
            used_fallback=record.used_fallback,
            fallback_reason=record.fallback_reason,
        )
    if hard_force_decision is None or record.decision != EMBEDDER_REVIEW_DECISION_CONTINUE:
        if advisory_evidence == record.evidence:
            return record
        return EmbedderReviewRecord(
            stage=record.stage,
            epoch=record.epoch,
            decision=record.decision,
            confidence=record.confidence,
            reason=record.reason,
            next_action=record.next_action,
            evidence=advisory_evidence,
            agent=record.agent,
            metrics_snapshot=record.metrics_snapshot,
            used_fallback=record.used_fallback,
            fallback_reason=record.fallback_reason,
        )
    return EmbedderReviewRecord(
        stage=record.stage,
        epoch=record.epoch,
        decision=hard_force_decision,
        confidence=max(record.confidence, 0.8),
        reason=hard_force_reason,
        next_action=_review_next_action(context.stage, hard_force_decision),
        evidence=advisory_evidence,
        agent=record.agent,
        metrics_snapshot=record.metrics_snapshot,
        used_fallback=record.used_fallback,
        fallback_reason=record.fallback_reason,
    )


def _merge_review_evidence(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for item in group:
            if not item.strip() or item in merged:
                continue
            merged.append(item)
    return merged


def _hard_force_action_guardrail(
    *,
    context: EmbedderReviewContext,
    detector_error_rate: float,
) -> tuple[str | None, str | None, list[str]]:
    if context.stage != "TRAIN_EMBEDDER_HARD":
        return None, None, []
    current_recall_at_1 = _primary_recall_at_1(context.current_metrics)
    identity_recall_at_1 = _metric_value(context.current_metrics, "embedding_identity_recall_at_1")
    if current_recall_at_1 >= HARD_FORCE_REBUILD_MAX_EXACT_RECALL_AT_1:
        return None, None, []
    if identity_recall_at_1 < HARD_FORCE_REBUILD_MIN_IDENTITY_RECALL_AT_1:
        return None, None, []

    low_exact_streak = _hard_low_exact_review_streak(context.review_history) + 1
    evidence = [
        "guardrail=hard_force_rebuild_low_exact_recall",
        f"embedding_recall_at_1={current_recall_at_1:.6f}",
        f"embedding_identity_recall_at_1={identity_recall_at_1:.6f}",
        f"low_exact_review_streak={low_exact_streak}",
        f"rebuild_count={context.rebuild_count}",
    ]
    if low_exact_streak >= HARD_FORCE_REBUILD_CONSECUTIVE_REVIEWS and detector_error_rate >= 0.45:
        evidence.append(f"detector_error_rate={detector_error_rate:.6f}")
        return (
            EMBEDDER_REVIEW_DECISION_ESCALATE_DETECTOR,
            "hard_low_exact_persisted_escalate_detector",
            evidence,
        )
    if context.rebuild_count < MAX_EMBEDDER_HARDSET_REBUILDS_PER_TRIAL:
        reason = (
            "hard_low_exact_persisted_rebuild_hardset"
            if low_exact_streak >= HARD_FORCE_REBUILD_CONSECUTIVE_REVIEWS
            else "hard_low_exact_force_rebuild_hardset"
        )
        return EMBEDDER_REVIEW_DECISION_REBUILD_HARDSET, reason, evidence
    evidence.append(f"detector_error_rate={detector_error_rate:.6f}")
    return (
        EMBEDDER_REVIEW_DECISION_ESCALATE_DETECTOR,
        "hard_low_exact_rebuild_exhausted_escalate_detector",
        evidence,
    )


def _base_stale_best_epoch_guardrail(
    context: EmbedderReviewContext,
) -> tuple[bool, list[str]]:
    if context.stage != "TRAIN_EMBEDDER_BASE":
        return False, []
    if context.best_epoch is None:
        return False, []
    best_epoch_gap = context.epoch - context.best_epoch
    if best_epoch_gap < BASE_STALE_BEST_EPOCH_GAP:
        return False, []

    current_recall_at_1 = _metric_value(context.current_metrics, "embedding_recall_at_1")
    scene_recall_at_1 = _metric_value(context.current_metrics, "embedding_scene_recall_at_1")
    same_template_error = _metric_value(context.current_metrics, "embedding_same_template_top1_error_rate")
    positive_rank_mean = _metric_value(context.current_metrics, "embedding_positive_rank_mean")

    if current_recall_at_1 > BASE_STALE_MAX_EXACT_RECALL_AT_1:
        return False, []
    if scene_recall_at_1 < BASE_STALE_MIN_SCENE_RECALL_AT_1:
        return False, []
    if (
        same_template_error < BASE_STALE_MIN_SAME_TEMPLATE_ERROR
        and positive_rank_mean < BASE_STALE_MIN_POSITIVE_RANK_MEAN
    ):
        return False, []

    return (
        True,
        [
            "guardrail=base_stale_best_epoch_force_hardset",
            f"epoch={context.epoch}",
            f"best_epoch={context.best_epoch}",
            f"best_epoch_gap={best_epoch_gap}",
            f"embedding_recall_at_1={current_recall_at_1:.6f}",
            f"embedding_scene_recall_at_1={scene_recall_at_1:.6f}",
            f"embedding_same_template_top1_error_rate={same_template_error:.6f}",
            f"embedding_positive_rank_mean={positive_rank_mean:.6f}",
        ],
    )


def _hard_low_exact_review_streak(review_history: list[dict[str, contracts.JsonValue]]) -> int:
    streak = 0
    for item in reversed(review_history):
        if _review_indicates_hard_low_exact(item):
            streak += 1
            continue
        break
    return streak


def _review_indicates_hard_low_exact(review: dict[str, contracts.JsonValue]) -> bool:
    if str(review.get("stage")) != "TRAIN_EMBEDDER_HARD":
        return False
    metrics_snapshot = review.get("metrics_snapshot")
    if isinstance(metrics_snapshot, dict):
        recall_at_1 = _primary_recall_at_1(metrics_snapshot)
        identity_recall_at_1 = _metric_value(metrics_snapshot, "embedding_identity_recall_at_1")
        return (
            recall_at_1 < HARD_FORCE_REBUILD_MAX_EXACT_RECALL_AT_1
            and identity_recall_at_1 >= HARD_FORCE_REBUILD_MIN_IDENTITY_RECALL_AT_1
        )
    evidence = review.get("evidence")
    if not isinstance(evidence, list):
        return False
    recall_at_1 = _metric_from_evidence(evidence, "embedding_scene_recall_at_1")
    if recall_at_1 is None:
        recall_at_1 = _metric_from_evidence(evidence, "embedding_recall_at_1")
    identity_recall_at_1 = _metric_from_evidence(evidence, "embedding_identity_recall_at_1")
    return (
        recall_at_1 is not None
        and identity_recall_at_1 is not None
        and recall_at_1 < HARD_FORCE_REBUILD_MAX_EXACT_RECALL_AT_1
        and identity_recall_at_1 >= HARD_FORCE_REBUILD_MIN_IDENTITY_RECALL_AT_1
    )


def _metrics_snapshot(metrics: dict[str, contracts.JsonValue]) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for key in (
        "embedding_recall_at_1",
        "embedding_recall_at_3",
        "embedding_scene_recall_at_1",
        "embedding_scene_recall_at_3",
        "embedding_identity_recall_at_1",
        "embedding_identity_recall_at_3",
        "embedding_positive_rank_mean",
        "embedding_scene_positive_rank_mean",
        "embedding_same_template_top1_error_rate",
        "embedding_top1_error_scene_target_rate",
        "embedding_top1_error_false_positive_rate",
    ):
        snapshot[key] = _metric_value(metrics, key)
    return snapshot


def _metric_from_evidence(evidence: list[contracts.JsonValue], key: str) -> float | None:
    prefix = f"{key}="
    for item in evidence:
        if not isinstance(item, str) or not item.startswith(prefix):
            continue
        try:
            return float(item[len(prefix) :])
        except ValueError:
            return None
    return None


def _json_line(payload: dict[str, contracts.JsonValue]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)
