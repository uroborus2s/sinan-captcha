from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.common.jsonl import write_jsonl
from core.evaluate.service import EvaluationRequest, evaluate_model


class EvaluateServiceTests(unittest.TestCase):
    def test_group1_evaluation_reports_perfect_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gold_dir = root / "gold"
            prediction_dir = root / "pred"
            report_dir = root / "reports"
            gold_dir.mkdir()
            prediction_dir.mkdir()

            gold_rows = [
                {
                    "sample_id": "g1_000001",
                    "query_image": "query/g1_000001.png",
                    "scene_image": "scene/g1_000001.png",
                    "query_targets": [
                        {
                            "order": 1,
                            "class": "icon_house",
                            "class_id": 0,
                            "bbox": [5, 6, 23, 24],
                            "center": [14, 15],
                        },
                        {
                            "order": 2,
                            "class": "icon_leaf",
                            "class_id": 1,
                            "bbox": [29, 6, 47, 24],
                            "center": [38, 15],
                        },
                    ],
                    "scene_targets": [
                        {
                            "order": 1,
                            "class": "icon_house",
                            "class_id": 0,
                            "bbox": [10, 20, 30, 40],
                            "center": [20, 30],
                        },
                        {
                            "order": 2,
                            "class": "icon_leaf",
                            "class_id": 1,
                            "bbox": [50, 60, 74, 86],
                            "center": [62, 73],
                        },
                    ],
                    "distractors": [],
                    "label_source": "gold",
                    "source_batch": "batch_0001",
                    "seed": 1,
                }
            ]
            write_jsonl(gold_dir / "labels.jsonl", gold_rows)
            write_jsonl(prediction_dir / "labels.jsonl", gold_rows)

            result = evaluate_model(
                EvaluationRequest(
                    task="group1",
                    gold_dir=gold_dir,
                    prediction_dir=prediction_dir,
                    report_dir=report_dir,
                )
            )

            self.assertEqual(result.sample_count, 1)
            self.assertAlmostEqual(result.metrics["single_target_hit_rate"], 1.0)
            self.assertAlmostEqual(result.metrics["full_sequence_hit_rate"], 1.0)
            self.assertAlmostEqual(result.metrics["mean_center_error_px"], 0.0)
            summary = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["task"], "group1")

    def test_group2_evaluation_exports_failure_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gold_dir = root / "gold"
            prediction_dir = root / "pred"
            report_dir = root / "reports"
            gold_dir.mkdir()
            prediction_dir.mkdir()

            write_jsonl(
                gold_dir / "labels.jsonl",
                [
                    {
                        "sample_id": "g2_000001",
                        "master_image": "master/g2_000001.png",
                        "tile_image": "tile/g2_000001.png",
                        "target_gap": {
                            "class": "slider_gap",
                            "class_id": 0,
                            "bbox": [20, 20, 60, 50],
                            "center": [40, 35],
                        },
                        "tile_bbox": [0, 20, 40, 50],
                        "offset_x": 20,
                        "offset_y": 0,
                        "label_source": "gold",
                        "source_batch": "batch_0001",
                        "seed": 1,
                    }
                ],
            )
            write_jsonl(
                prediction_dir / "labels.jsonl",
                [
                    {
                        "sample_id": "g2_000001",
                        "master_image": "master/g2_000001.png",
                        "tile_image": "tile/g2_000001.png",
                        "target_gap": {
                            "class": "slider_gap",
                            "class_id": 0,
                            "bbox": [100, 90, 130, 118],
                            "center": [115, 104],
                        },
                        "tile_bbox": [0, 20, 40, 50],
                        "offset_x": 100,
                        "offset_y": 70,
                        "label_source": "auto",
                        "source_batch": "batch_0001",
                        "seed": 1,
                        "inference_ms": 7.5,
                    }
                ],
            )

            result = evaluate_model(
                EvaluationRequest(
                    task="group2",
                    gold_dir=gold_dir,
                    prediction_dir=prediction_dir,
                    report_dir=report_dir,
                    point_tolerance_px=10,
                )
            )

            self.assertEqual(result.sample_count, 1)
            self.assertAlmostEqual(result.metrics["point_hit_rate"], 0.0)
            self.assertGreater(result.failure_count, 0)
            failures = (report_dir / "failures.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(failures), 1)

    def test_group1_evaluation_accepts_reviewed_rows_without_identity_or_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gold_dir = root / "gold"
            prediction_dir = root / "pred"
            report_dir = root / "reports"
            gold_dir.mkdir()
            prediction_dir.mkdir()

            write_jsonl(
                gold_dir / "labels.jsonl",
                [
                    {
                        "sample_id": "exam_0001",
                        "query_image": "query/exam_0001.png",
                        "scene_image": "scene/exam_0001.png",
                        "query_items": [
                            {"order": 1, "bbox": [5, 6, 23, 24], "center": [14, 15]},
                            {"order": 2, "bbox": [29, 6, 47, 24], "center": [38, 15]},
                        ],
                        "scene_targets": [
                            {"order": 1, "bbox": [10, 20, 30, 40], "center": [20, 30]},
                            {"order": 2, "bbox": [50, 60, 74, 86], "center": [62, 73]},
                        ],
                        "distractors": [],
                        "label_source": "reviewed",
                        "source_batch": "reviewed-v2",
                    }
                ],
            )
            write_jsonl(
                prediction_dir / "labels.jsonl",
                [
                    {
                        "sample_id": "exam_0001",
                        "query_image": "query/exam_0001.png",
                        "scene_image": "scene/exam_0001.png",
                        "query_items": [],
                        "scene_targets": [
                            {"order": 1, "class": "wrong_a", "class_id": 7, "bbox": [10, 20, 30, 40], "center": [20, 30]},
                            {"order": 2, "class": "wrong_b", "class_id": 9, "bbox": [50, 60, 74, 86], "center": [62, 73]},
                        ],
                        "distractors": [],
                        "label_source": "pred",
                        "source_batch": "predict",
                    }
                ],
            )

            result = evaluate_model(
                EvaluationRequest(
                    task="group1",
                    gold_dir=gold_dir,
                    prediction_dir=prediction_dir,
                    report_dir=report_dir,
                    point_tolerance_px=5,
                )
            )

            self.assertEqual(result.sample_count, 1)
            self.assertAlmostEqual(result.metrics["single_target_hit_rate"], 1.0)
            self.assertAlmostEqual(result.metrics["full_sequence_hit_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
