"""Shared structured-judge payload parsing for local autonomous-training judges."""

from __future__ import annotations

from dataclasses import dataclass

from auto_train import contracts, json_extract


class StructuredJudgePayloadError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class StructuredJudgePayload:
    decision: str
    reason: str
    confidence: float
    next_action: dict[str, contracts.JsonValue]
    evidence: list[str]

    def __post_init__(self) -> None:
        if not self.decision.strip():
            raise ValueError("decision must not be empty")
        if not self.reason.strip():
            raise ValueError("reason must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not isinstance(self.next_action, dict):
            raise ValueError("next_action must be a mapping")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("evidence entries must be non-empty strings")


def parse_structured_payload(
    *,
    raw_output: str,
    allowed_decisions: set[str],
) -> StructuredJudgePayload:
    try:
        payload = json_extract.extract_json_object_from_opencode_output(
            raw_output,
            required_keys={"decision", "reason", "confidence", "next_action", "evidence"},
        )
    except ValueError as exc:
        raise StructuredJudgePayloadError("invalid_json", str(exc)) from exc
    if not isinstance(payload, dict):
        raise StructuredJudgePayloadError("invalid_payload", "judge payload must be an object")

    decision = _string(payload, "decision")
    if decision not in allowed_decisions:
        allowed_text = ", ".join(sorted(allowed_decisions))
        raise StructuredJudgePayloadError("invalid_payload", f"decision must be one of: {allowed_text}")

    evidence_payload = payload.get("evidence")
    if not isinstance(evidence_payload, list):
        raise StructuredJudgePayloadError("invalid_payload", "evidence must be a list")

    try:
        return StructuredJudgePayload(
            decision=decision,
            reason=_string(payload, "reason"),
            confidence=_float(payload, "confidence"),
            next_action=_mapping(payload, "next_action"),
            evidence=[_string_value(item, "evidence") for item in evidence_payload],
        )
    except ValueError as exc:
        raise StructuredJudgePayloadError("invalid_payload", str(exc)) from exc


def _string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _string_value(value: object, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} entries must be non-empty strings")
    return value


def _float(payload: dict[str, object], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    return float(value)


def _mapping(payload: dict[str, object], key: str) -> dict[str, contracts.JsonValue]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value  # type: ignore[return-value]
