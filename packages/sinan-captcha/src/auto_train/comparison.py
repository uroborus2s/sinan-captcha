"""Comparable-trial fingerprints for autonomous training decisions."""

from __future__ import annotations

import hashlib
import json

from auto_train import contracts

COMPARISON_KEY_METRIC = "comparison_key"
COMPARISON_SCOPE_METRIC = "comparison_scope"
COMPARISON_SCOPE = "trial_input_v1"

_IGNORED_PARAM_KEYS = {
    "_optuna_engine",
    "_optuna_trial_number",
    "group1_component_base_runs",
}


def comparison_payload_for_input(
    record: contracts.TrialInputRecord,
) -> dict[str, contracts.JsonValue]:
    """Return the stable fields that make two trial scores directly comparable."""

    return {
        "task": record.task,
        "dataset_version": record.dataset_version,
        "dataset_preset": record.dataset_preset,
        "dataset_override": _normalize_json_value(record.dataset_override),
        "train_mode": record.train_mode,
        "params": _normalize_params(record.params),
    }


def comparison_key_for_input(record: contracts.TrialInputRecord) -> str:
    payload = comparison_payload_for_input(record)
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"cmp_{digest}"


def _normalize_params(params: dict[str, contracts.JsonValue]) -> dict[str, contracts.JsonValue]:
    return {
        key: _normalize_json_value(value)
        for key, value in sorted(params.items())
        if key not in _IGNORED_PARAM_KEYS
    }


def _normalize_json_value(value: contracts.JsonValue) -> contracts.JsonValue:
    if isinstance(value, dict):
        return {
            str(key): _normalize_json_value(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    return value
