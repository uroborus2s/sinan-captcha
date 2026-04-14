from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from auto_train.group1_pipeline import (
    MatcherCalibrationCase,
    build_detector_aware_hardset_from_rows,
    calibrate_matcher_from_cases,
    write_detector_aware_dataset_config,
)
from train.group1.dataset import load_group1_dataset_config


def _write_png(path: Path, width: int, height: int, color: tuple[int, int, int]) -> None:
    raw_rows = []
    pixel = bytes(color)
    for _ in range(height):
        raw_rows.append(b"\x00" + pixel * width)
    payload = zlib.compress(b"".join(raw_rows))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", payload),
            chunk(b"IEND", b""),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


class Group1AutoTrainPipelineTests(unittest.TestCase):
    def test_build_detector_aware_hardset_from_rows_writes_triplets_and_dataset_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_root = root / "dataset"
            query_path = dataset_root / "eval" / "query" / "train" / "g1_000001.png"
            scene_path = dataset_root / "eval" / "scene" / "train" / "g1_000001.png"
            _write_png(query_path, 64, 24, (255, 255, 255))
            _write_png(scene_path, 160, 96, (240, 240, 240))

            row = {
                "sample_id": "g1_000001",
                "query_image": "eval/query/train/g1_000001.png",
                "scene_image": "eval/scene/train/g1_000001.png",
                "query_items": [
                    {
                        "order": 1,
                        "asset_id": "asset_red",
                        "template_id": "tpl_red",
                        "variant_id": "var_red",
                        "bbox": [4, 4, 20, 20],
                        "center": [12, 12],
                    }
                ],
                "scene_targets": [
                    {
                        "order": 1,
                        "asset_id": "asset_red",
                        "template_id": "tpl_red",
                        "variant_id": "var_red",
                        "bbox": [60, 20, 92, 52],
                        "center": [76, 36],
                    }
                ],
                "distractors": [
                    {
                        "bbox": [110, 18, 142, 50],
                        "center": [126, 34],
                        "asset_id": "asset_blue",
                        "template_id": "tpl_blue",
                        "variant_id": "var_blue",
                    }
                ],
            }

            def fake_query_predictor(_path: Path) -> list[dict[str, object]]:
                return [
                    {
                        "order": 1,
                        "bbox": [5, 4, 21, 20],
                        "center": [13, 12],
                        "score": 0.99,
                    }
                ]

            def fake_scene_predictor(_path: Path) -> list[dict[str, object]]:
                return [
                    {
                        "order": 1,
                        "bbox": [61, 20, 93, 52],
                        "center": [77, 36],
                        "score": 0.98,
                    },
                    {
                        "order": 2,
                        "bbox": [109, 18, 141, 50],
                        "center": [125, 34],
                        "score": 0.91,
                    },
                    {
                        "order": 3,
                        "bbox": [12, 60, 36, 84],
                        "center": [24, 72],
                        "score": 0.74,
                    },
                ]

            hardset_root = root / "study" / "trial_0001" / "embedder_hardset"
            progress_messages: list[str] = []
            result = build_detector_aware_hardset_from_rows(
                split_rows={"train": [row], "val": [row]},
                dataset_root=dataset_root,
                output_root=hardset_root,
                query_predictor=fake_query_predictor,
                scene_predictor=fake_scene_predictor,
                progress_callback=progress_messages.append,
            )

            base_dataset_config_path = dataset_root / "dataset.json"
            base_dataset_config_path.write_text(
                json.dumps(
                    {
                        "task": "group1",
                        "format": "sinan.group1.instance_matching.v1",
                        "splits": {
                            "train": str((dataset_root / "splits" / "train.jsonl").resolve()),
                            "val": str((dataset_root / "splits" / "val.jsonl").resolve()),
                            "test": str((dataset_root / "splits" / "test.jsonl").resolve()),
                        },
                        "query_detector": {
                            "format": "yolo.detect.v1",
                            "dataset_yaml": str((dataset_root / "query-yolo" / "dataset.yaml").resolve()),
                        },
                        "proposal_detector": {
                            "format": "yolo.detect.v1",
                            "dataset_yaml": str((dataset_root / "proposal-yolo" / "dataset.yaml").resolve()),
                        },
                        "embedding": {
                            "format": "sinan.group1.embedding.v1",
                            "queries_dir": "embedding/queries",
                            "candidates_dir": "embedding/candidates",
                            "pairs_jsonl": "embedding/pairs.jsonl",
                            "triplets_jsonl": "embedding/triplets.jsonl",
                        },
                        "eval": {
                            "format": "sinan.group1.eval.v1",
                            "labels_jsonl": str((dataset_root / "eval" / "labels.jsonl").resolve()),
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            derived_config = write_detector_aware_dataset_config(
                base_dataset_config_path=base_dataset_config_path,
                output_root=hardset_root,
                output_path=hardset_root / "dataset.json",
            )

            triplets = [
                json.loads(line)
                for line in (hardset_root / "triplets.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            derived = load_group1_dataset_config(derived_config)

            self.assertGreater(result.triplet_count, 0)
            self.assertGreaterEqual(result.false_positive_negative_count, 1)
            self.assertEqual(result.anchor_fallback_count, 0)
            self.assertEqual(result.positive_fallback_count, 0)
            self.assertTrue((hardset_root / "queries" / "train").exists())
            self.assertTrue((hardset_root / "candidates" / "val").exists())
            self.assertEqual(len(triplets), result.triplet_count)
            self.assertIn("negative_bucket", triplets[0])
            self.assertTrue(any(str(item["negative_role"]).startswith("false_positive") for item in triplets))
            self.assertEqual(derived.embedding.triplets_jsonl, hardset_root / "triplets.jsonl")
            self.assertTrue(any("hardset_build_start" in line for line in progress_messages))
            self.assertTrue(any("hardset_build_progress split=train processed=1/1" in line for line in progress_messages))
            self.assertTrue(any("hardset_build_done" in line for line in progress_messages))

    def test_build_detector_aware_hardset_prioritizes_hard_negatives_by_identity_similarity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_root = root / "dataset"
            query_path = dataset_root / "eval" / "query" / "train" / "g1_000001.png"
            scene_path = dataset_root / "eval" / "scene" / "train" / "g1_000001.png"
            _write_png(query_path, 64, 24, (255, 255, 255))
            _write_png(scene_path, 160, 96, (240, 240, 240))

            row = {
                "sample_id": "g1_000001",
                "query_image": "eval/query/train/g1_000001.png",
                "scene_image": "eval/scene/train/g1_000001.png",
                "query_items": [
                    {
                        "order": 1,
                        "asset_id": "asset_red",
                        "template_id": "tpl_red",
                        "variant_id": "var_red",
                        "bbox": [4, 4, 20, 20],
                        "center": [12, 12],
                    }
                ],
                "scene_targets": [
                    {
                        "order": 1,
                        "asset_id": "asset_red",
                        "template_id": "tpl_red",
                        "variant_id": "var_red",
                        "bbox": [60, 20, 92, 52],
                        "center": [76, 36],
                    },
                    {
                        "order": 2,
                        "asset_id": "asset_alt",
                        "template_id": "tpl_red",
                        "variant_id": "var_outline",
                        "bbox": [100, 18, 132, 50],
                        "center": [116, 34],
                    },
                ],
                "distractors": [
                    {
                        "bbox": [12, 60, 36, 84],
                        "center": [24, 72],
                        "asset_id": "asset_blue",
                        "template_id": "tpl_blue",
                        "variant_id": "var_blue",
                    }
                ],
            }

            def fake_query_predictor(_path: Path) -> list[dict[str, object]]:
                return [
                    {
                        "order": 1,
                        "bbox": [5, 4, 21, 20],
                        "center": [13, 12],
                        "score": 0.99,
                        "asset_id": "asset_red",
                        "template_id": "tpl_red",
                        "variant_id": "var_red",
                    }
                ]

            def fake_scene_predictor(_path: Path) -> list[dict[str, object]]:
                return [
                    {
                        "order": 1,
                        "bbox": [61, 20, 93, 52],
                        "center": [77, 36],
                        "score": 0.98,
                        "asset_id": "asset_red",
                        "template_id": "tpl_red",
                        "variant_id": "var_red",
                    },
                    {
                        "order": 2,
                        "bbox": [100, 18, 132, 50],
                        "center": [116, 34],
                        "score": 0.82,
                        "asset_id": "asset_alt",
                        "template_id": "tpl_red",
                        "variant_id": "var_outline",
                    },
                    {
                        "order": 3,
                        "bbox": [12, 60, 36, 84],
                        "center": [24, 72],
                        "score": 0.93,
                    },
                ]

            def fake_embedding_encoder(_image_path: Path, target: dict[str, object]) -> list[float]:
                variant_id = str(target.get("variant_id", ""))
                bbox = target.get("bbox", [0, 0, 0, 0])
                if variant_id == "var_red":
                    return [1.0, 0.0, 0.0]
                if variant_id == "var_outline":
                    return [0.95, 0.05, 0.0]
                if bbox == [12, 60, 36, 84]:
                    return [0.10, 0.90, 0.0]
                return [0.0, 0.0, 1.0]

            hardset_root = root / "study" / "trial_0001" / "embedder_hardset"
            result = build_detector_aware_hardset_from_rows(
                split_rows={"train": [row]},
                dataset_root=dataset_root,
                output_root=hardset_root,
                query_predictor=fake_query_predictor,
                scene_predictor=fake_scene_predictor,
                embedding_encoder=fake_embedding_encoder,
                max_negatives_per_query=2,
            )

            triplets = [
                json.loads(line)
                for line in (hardset_root / "triplets.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(result.triplet_count, 2)
            self.assertEqual(triplets[0]["negative_bucket"], "same_template_variant")
            self.assertGreater(triplets[0]["negative_similarity"], triplets[1]["negative_similarity"])
            self.assertEqual(triplets[1]["negative_bucket"], "distractor")

    def test_calibrate_matcher_from_cases_prefers_threshold_with_best_sequence_score(self) -> None:
        cases = [
            MatcherCalibrationCase(
                sample_id="g1_000001",
                gold_targets=[
                    {"order": 1, "bbox": [0, 0, 20, 20], "center": [10, 10]},
                    {"order": 2, "bbox": [40, 0, 60, 20], "center": [50, 10]},
                ],
                query_items=[
                    {"order": 1, "bbox": [0, 0, 20, 20], "center": [10, 10]},
                    {"order": 2, "bbox": [0, 0, 20, 20], "center": [10, 10]},
                ],
                scene_candidates=[
                    {"order": 1, "bbox": [0, 0, 20, 20], "center": [10, 10]},
                    {"order": 2, "bbox": [40, 0, 60, 20], "center": [50, 10]},
                ],
                similarity_matrix=[
                    [0.87, 0.20],
                    [0.25, 0.89],
                ],
            )
        ]

        result = calibrate_matcher_from_cases(
            cases,
            point_tolerance_px=5,
            similarity_thresholds=(0.85, 0.9),
            ambiguity_margins=(0.0, 0.015),
        )

        self.assertEqual(result.sample_count, 1)
        self.assertEqual(result.selected_similarity_threshold, 0.85)
        self.assertEqual(result.best_metrics["full_sequence_hit_rate"], 1.0)
        self.assertGreaterEqual(len(result.candidate_metrics), 2)


if __name__ == "__main__":
    unittest.main()
