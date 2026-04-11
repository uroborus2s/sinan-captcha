"""CLI for JSONL-based evaluation flows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate.service import EvaluationRequest, evaluate_model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare prediction JSONL files against gold labels.")
    parser.add_argument("--task", choices=["group1", "group2"], required=True)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--prediction-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--point-tolerance-px", type=int, default=12)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result = evaluate_model(
        EvaluationRequest(
            task=args.task,
            gold_dir=args.gold_dir,
            prediction_dir=args.prediction_dir,
            report_dir=args.report_dir,
            point_tolerance_px=args.point_tolerance_px,
            iou_threshold=args.iou_threshold,
        )
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
