"""Thin entry script for future JSONL to YOLO conversion flows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.convert.service import ConversionRequest, build_yolo_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert JSONL source-of-truth files into YOLO datasets.")
    parser.add_argument("--task", choices=["group1", "group2"], required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

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
