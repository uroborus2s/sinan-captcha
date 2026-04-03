"""CLI for JSONL to YOLO conversion flows."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.convert.service import ConversionRequest, build_yolo_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert JSONL source-of-truth files into YOLO datasets.")
    parser.add_argument("--task", choices=["group1", "group2"], required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    build_yolo_dataset(
        ConversionRequest(
            task=args.task,
            version=args.version,
            source_dir=args.source_dir,
            output_dir=args.output_dir,
        )
    )
    print(f"built YOLO dataset at {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
