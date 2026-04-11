"""Minimal dataset CLI for early validation workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

from common.jsonl import read_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate JSONL dataset files.")
    parser.add_argument("--path", type=Path, required=True, help="Path to the JSONL file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.path.exists():
        parser.error(f"JSONL file does not exist: {args.path}")
    rows = read_jsonl(args.path)
    print(f"validated {len(rows)} rows from {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
