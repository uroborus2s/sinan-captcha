"""Helpers for extracting one structured JSON object from LLM-style output."""

from __future__ import annotations

import json
import re


def extract_json_object(raw_output: str, *, required_keys: set[str]) -> dict[str, object]:
    """Return the first JSON object containing the required keys.

    The OpenCode CLI may return plain JSON, JSON inside markdown fences, or surrounding prose.
    This helper scans the raw output and extracts the first object that matches the expected
    contract shape.
    """

    decoder = json.JSONDecoder()

    def _matches(candidate: object) -> dict[str, object] | None:
        if not isinstance(candidate, dict):
            return None
        if not required_keys.issubset(candidate.keys()):
            return None
        return candidate

    stripped = raw_output.strip()
    if stripped:
        try:
            direct = json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            matched = _matches(direct)
            if matched is not None:
                return matched

    for index, char in enumerate(raw_output):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(raw_output[index:])
        except json.JSONDecodeError:
            continue
        matched = _matches(candidate)
        if matched is not None:
            return matched

    for candidate_text in _repairable_json_candidates(raw_output):
        try:
            repaired = _repair_json_candidate(candidate_text)
            candidate = json.loads(repaired)
        except json.JSONDecodeError:
            continue
        matched = _matches(candidate)
        if matched is not None:
            return matched

    required_text = ", ".join(sorted(required_keys))
    raise ValueError(f"no JSON object found with required keys: {required_text}")


def extract_json_object_from_opencode_output(raw_output: str, *, required_keys: set[str]) -> dict[str, object]:
    """Return one JSON object from either plain output or OpenCode JSON event streams."""

    try:
        return extract_json_object(raw_output, required_keys=required_keys)
    except ValueError:
        pass

    candidates = _extract_opencode_event_text(raw_output)
    for candidate in candidates:
        try:
            return extract_json_object(candidate, required_keys=required_keys)
        except ValueError:
            continue

    required_text = ", ".join(sorted(required_keys))
    raise ValueError(f"no JSON object found with required keys: {required_text}")


def _extract_opencode_event_text(raw_output: str) -> list[str]:
    candidates: list[str] = []
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        _collect_candidate_strings(payload, path=(), sink=candidates)
    unique: list[str] = []
    for candidate in candidates:
        text = candidate.strip()
        if not text:
            continue
        if text not in unique:
            unique.append(text)
    return unique


def _repairable_json_candidates(raw_output: str) -> list[str]:
    candidates: list[str] = []
    stripped = raw_output.strip()
    if stripped:
        candidates.append(stripped)

    for match in re.finditer(r"```(?:json)?\s*(.*?)```", raw_output, flags=re.IGNORECASE | re.DOTALL):
        block = match.group(1).strip()
        if block:
            candidates.append(block)

    first_brace = raw_output.find("{")
    last_brace = raw_output.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(raw_output[first_brace : last_brace + 1].strip())

    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def _repair_json_candidate(candidate_text: str) -> str:
    repaired = candidate_text.strip()
    previous = None
    while repaired != previous:
        previous = repaired
        repaired = re.sub(r"([,{]\s*)\"([A-Za-z_][A-Za-z0-9_-]*)\s*:", r'\1"\2":', repaired)
        repaired = re.sub(r"([,{]\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*:)", r'\1"\2"\3', repaired)
        repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return repaired


def _collect_candidate_strings(node: object, *, path: tuple[str, ...], sink: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _collect_candidate_strings(value, path=path + (key,), sink=sink)
        return
    if isinstance(node, list):
        for value in node:
            _collect_candidate_strings(value, path=path, sink=sink)
        return
    if not isinstance(node, str):
        return
    if "input" in path:
        return
    leaf = path[-1] if path else ""
    if leaf not in {"output", "text", "content"}:
        return
    sink.append(node)
