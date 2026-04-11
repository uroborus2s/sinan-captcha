"""CLI for business exam preparation and reviewed-label export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common.paths import workspace_paths
from exam.service import (
    build_group2_prelabel_yolo_dataset,
    export_group1_reviewed_labels,
    export_group2_reviewed_labels,
    prepare_group1_exam_sources,
    prepare_group2_exam_sources,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare business exam workspaces and export reviewed labels.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    defaults = workspace_paths(Path.cwd())

    prepare_parser = subparsers.add_parser("prepare", help="copy raw materials into a stable reviewed-exam layout")
    prepare_parser.add_argument("--task", choices=["group1", "group2"], required=True)
    prepare_parser.add_argument("--materials-root", type=Path, default=defaults.materials_dir)
    prepare_parser.add_argument("--output-dir", type=Path, required=True)

    export_parser = subparsers.add_parser("export-reviewed", help="convert reviewed X-AnyLabeling annotations into labels.jsonl")
    export_parser.add_argument("--task", choices=["group1", "group2"], required=True)
    export_parser.add_argument("--exam-root", type=Path, required=True)

    group2_parser = subparsers.add_parser(
        "build-group2-prelabel-yolo",
        help="build a single-image YOLO dataset for group2 X-AnyLabeling prelabeling",
    )
    group2_parser.add_argument("--source-dir", type=Path, required=True)
    group2_parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare":
        if args.task == "group1":
            result = prepare_group1_exam_sources(materials_root=args.materials_root, output_dir=args.output_dir)
        else:
            result = prepare_group2_exam_sources(materials_root=args.materials_root, output_dir=args.output_dir)
    elif args.command == "export-reviewed":
        if args.task == "group1":
            result = export_group1_reviewed_labels(exam_root=args.exam_root)
        else:
            result = export_group2_reviewed_labels(exam_root=args.exam_root)
    else:
        result = build_group2_prelabel_yolo_dataset(source_dir=args.source_dir, output_dir=args.output_dir)

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
