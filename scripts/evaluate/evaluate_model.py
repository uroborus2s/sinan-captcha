"""Thin CLI entry for JSONL-based evaluation flows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.evaluate.service import EvaluationRequest, evaluate_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare prediction JSONL files against gold labels.")
    parser.add_argument("--task", choices=["group1", "group2"], required=True)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--prediction-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--point-tolerance-px", type=int, default=12)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    args = parser.parse_args()

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
