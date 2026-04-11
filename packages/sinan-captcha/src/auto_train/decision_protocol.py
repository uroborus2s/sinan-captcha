"""Decision JSON validation and fallback helpers for autonomous training."""

from __future__ import annotations

import json
from dataclasses import dataclass

from auto_train import contracts, json_extract, policies


@dataclass(frozen=True)
class DecisionParseOutcome:
    record: contracts.DecisionRecord
    used_fallback: bool
    fallback_reason: str | None = None


def parse_or_fallback_decision(
    *,
    raw_output: str,
    trial_id: str,
    agent: contracts.AgentRef,
    summary: contracts.ResultSummaryRecord,
) -> DecisionParseOutcome:
    """Parse one judge response into a persisted decision, with deterministic fallback."""

    try:
        payload = json_extract.extract_json_object_from_opencode_output(
            raw_output,
            required_keys={"decision", "reason", "confidence", "next_action", "evidence"},
        )
    except ValueError:
        return fallback_decision(
            trial_id=trial_id,
            agent=agent,
            summary=summary,
            reason_code="invalid_json",
        )

    if not isinstance(payload, dict):
        return fallback_decision(
            trial_id=trial_id,
            agent=agent,
            summary=summary,
            reason_code="invalid_payload",
        )

    try:
        parsed = contracts.JudgeDecisionPayload.from_dict(payload)
    except ValueError:
        return fallback_decision(
            trial_id=trial_id,
            agent=agent,
            summary=summary,
            reason_code="invalid_payload",
        )

    return DecisionParseOutcome(
        record=contracts.DecisionRecord(
            trial_id=trial_id,
            decision=parsed.decision,
            confidence=parsed.confidence,
            reason=parsed.reason,
            next_action=parsed.next_action,
            evidence=parsed.evidence,
            agent=agent,
        ),
        used_fallback=False,
        fallback_reason=None,
    )


def fallback_decision(
    *,
    trial_id: str,
    agent: contracts.AgentRef,
    summary: contracts.ResultSummaryRecord,
    reason_code: str,
    extra_evidence: list[str] | None = None,
) -> DecisionParseOutcome:
    return DecisionParseOutcome(
        record=_fallback_decision(
            trial_id=trial_id,
            agent=agent,
            summary=summary,
            reason_code=reason_code,
            extra_evidence=extra_evidence,
        ),
        used_fallback=True,
        fallback_reason=reason_code,
    )


def _fallback_decision(
    *,
    trial_id: str,
    agent: contracts.AgentRef,
    summary: contracts.ResultSummaryRecord,
    reason_code: str,
    extra_evidence: list[str] | None = None,
) -> contracts.DecisionRecord:
    recommendation = policies.evaluate_summary(summary)
    decision = recommendation.decision
    next_action = _fallback_next_action(summary, decision)
    evidence = [
        f"fallback_reason={reason_code}",
        f"policy_reason={recommendation.reason}",
        f"trend={summary.trend}",
    ]
    evidence.extend(recommendation.evidence)
    if summary.weak_classes:
        evidence.append(f"weak_classes={', '.join(summary.weak_classes)}")
    if summary.failure_patterns:
        evidence.append(f"failure_patterns={', '.join(summary.failure_patterns)}")
    if summary.delta_vs_best is not None:
        evidence.append(f"delta_vs_best={summary.delta_vs_best:+.6f}")
    if extra_evidence:
        evidence.extend(item for item in extra_evidence if item.strip())

    confidence = 0.4 if reason_code == "invalid_json" else 0.45
    return contracts.DecisionRecord(
        trial_id=trial_id,
        decision=decision,
        confidence=confidence,
        reason=f"fallback_{reason_code}",
        next_action=next_action,
        evidence=evidence,
        agent=agent,
    )


def _fallback_next_action(summary: contracts.ResultSummaryRecord, decision: str) -> dict[str, contracts.JsonValue]:
    if decision == "REGENERATE_DATA":
        return {
            "dataset_action": "new_version",
            "train_action": "from_run",
            "base_run": summary.train_name,
        }
    if decision == "ABANDON_BRANCH":
        return {"dataset_action": "freeze", "train_action": "stop"}
    if decision == "PROMOTE_BRANCH":
        return {"dataset_action": "freeze", "train_action": "promote"}
    return {
        "dataset_action": "reuse",
        "train_action": "from_run",
        "base_run": summary.train_name,
    }
