from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT_DIR = Path(__file__).resolve().parents[1]
WORK_HOME_DIR = ROOT_DIR / "work_home"
SOLVER_SRC_DIR = ROOT_DIR / "packages" / "solver" / "src"
if str(SOLVER_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SOLVER_SRC_DIR))

from common.jsonl import read_jsonl, write_jsonl
from evaluate.service import EvaluationRequest, evaluate_model
from sinanz import CaptchaSolver

DEFAULT_REVIEWED_DIR = WORK_HOME_DIR / "materials" / "solver" / "group2" / "reviewed"
DEFAULT_OUTPUT_DIR = WORK_HOME_DIR / "materials" / "solver" / "group2" / "reports" / "reviewed-regression"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run solver regression against reviewed group2 samples.")
    parser.add_argument("--reviewed-dir", type=Path, default=DEFAULT_REVIEWED_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--asset-root", type=Path, default=None)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--limit", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reviewed_dir = args.reviewed_dir.resolve()
    output_dir = args.output_dir.resolve()
    prediction_dir = output_dir / "predictions"
    report_dir = output_dir / "evaluation"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(reviewed_dir / "labels.jsonl")
    if args.limit > 0:
        rows = rows[: args.limit]

    solver = CaptchaSolver(
        device=args.device,
        asset_root=args.asset_root,
    )
    predictions: list[dict[str, object]] = []

    for row in rows:
        started = time.perf_counter()
        result = solver.sn_match_slider(
            background_image=reviewed_dir / str(row["master_image"]),
            puzzle_piece_image=reviewed_dir / str(row["tile_image"]),
            puzzle_piece_start_bbox=tuple(int(value) for value in row["tile_bbox"]),
            return_debug=False,
        )
        inference_ms = (time.perf_counter() - started) * 1000.0
        predictions.append(
            {
                "sample_id": str(row["sample_id"]),
                "master_image": row["master_image"],
                "tile_image": row["tile_image"],
                "target_gap": {
                    "class": "slider_gap",
                    "class_id": 0,
                    "bbox": [int(value) for value in result.target_bbox],
                    "center": [int(value) for value in result.target_center],
                },
                "tile_bbox": [int(value) for value in row["tile_bbox"]],
                "offset_x": int(result.target_bbox[0]),
                "offset_y": int(result.target_bbox[1]),
                "label_source": "solver_prediction",
                "source_batch": row.get("source_batch", "reviewed"),
                "inference_ms": round(inference_ms, 4),
            }
        )

    write_jsonl(prediction_dir / "labels.jsonl", predictions)
    evaluation = evaluate_model(
        EvaluationRequest(
            task="group2",
            gold_dir=reviewed_dir,
            prediction_dir=prediction_dir,
            report_dir=report_dir,
        )
    )
    summary = {
        "reviewed_dir": str(reviewed_dir),
        "prediction_dir": str(prediction_dir),
        "report_dir": str(report_dir),
        "sample_count": evaluation.sample_count,
        "failure_count": evaluation.failure_count,
        "metrics": evaluation.metrics,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
