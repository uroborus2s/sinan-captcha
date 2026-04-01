"""Small JSONL helpers used across dataset and report flows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonMapping = dict[str, Any]


def read_jsonl(path: Path) -> list[JsonMapping]:
    """Read a JSONL file into a list of dictionaries."""

    rows: list[JsonMapping] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:  # pragma: no cover - direct error path
                message = f"Invalid JSONL at {path}:{line_number}: {exc.msg}"
                raise ValueError(message) from exc
            if not isinstance(payload, dict):
                message = f"Expected object at {path}:{line_number}, got {type(payload).__name__}"
                raise ValueError(message)
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: list[JsonMapping]) -> None:
    """Write dictionaries to a UTF-8 JSONL file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")
