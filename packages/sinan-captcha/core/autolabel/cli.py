"""CLI for offline autolabel flows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.autolabel.service import AutolabelRequest, run_autolabel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline autolabel flows.")
    parser.add_argument("--task", choices=["group1", "group2"], required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--jitter-pixels", type=int, default=4)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result = run_autolabel(
        AutolabelRequest(
            task=args.task,
            mode=args.mode,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            limit=args.limit,
            jitter_pixels=args.jitter_pixels,
        )
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
