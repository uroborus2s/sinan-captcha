from __future__ import annotations

import io
import json
import os
import struct
import types
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch
import zlib

from common.jsonl import read_jsonl
from train.group1.service import Group1PredictionResult
from train.group2.service import Group2PredictionResult
from train.prelabel import (
    Group1PrelabelRequest,
    Group1QueryDirectoryPrelabelRequest,
    Group1VlmPrelabelRequest,
    Group2PrelabelRequest,
    _resolve_sample_asset,
    run_group1_prelabel,
    run_group1_query_directory_prelabel,
    run_group1_vlm_prelabel,
    run_group2_prelabel,
)


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


class TrainPrelabelServiceTests(unittest.TestCase):
    def test_resolve_sample_asset_normalizes_relative_exam_root_to_absolute_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            exam_root = root / "business-exams" / "group1" / "reviewed-v1"
            image_path = exam_root / "import" / "query" / "sample_0001.png"
            _write_png(image_path, 120, 36, (10, 10, 10))

            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                resolved = _resolve_sample_asset(
                    Path("business-exams/group1/reviewed-v1"),
                    {"query_image": "import/query/sample_0001.png"},
                    "query_image",
                )
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(resolved.is_absolute())
            self.assertEqual(resolved, image_path.resolve())

    def test_group1_prelabel_copies_images_and_writes_xany_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            exam_root = root / "business-exams" / "group1" / "reviewed-v1"
            query_image = exam_root / "import" / "query" / "sample_0001.png"
            scene_image = exam_root / "import" / "scene" / "sample_0001.png"
            _write_png(query_image, 120, 36, (10, 10, 10))
            _write_png(scene_image, 320, 160, (220, 220, 220))
            (exam_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "task": "group1",
                        "sample_count": 1,
                        "samples": [
                            {
                                "sample_id": "sample_0001",
                                "query_image": "import/query/sample_0001.png",
                                "scene_image": "import/scene/sample_0001.png",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            prediction_dir = root / "reports" / "group1" / "prelabel"

            def _fake_predict(job) -> Group1PredictionResult:
                output_dir = job.output_dir()
                output_dir.mkdir(parents=True, exist_ok=True)
                labels_path = output_dir / "labels.jsonl"
                labels_path.write_text(
                    json.dumps(
                        {
                            "sample_id": "sample_0001",
                            "query_image": str(query_image),
                            "scene_image": str(scene_image),
                            "query_items": [
                                {
                                    "order": 1,
                                    "bbox": [5, 8, 29, 30],
                                    "center": [17, 19],
                                    "class_guess": "icon_lock",
                                }
                            ],
                            "scene_targets": [
                                {
                                    "order": 1,
                                    "asset_id": "pred_asset_01",
                                    "template_id": "pred_tpl_01",
                                    "variant_id": "pred_var_01",
                                    "bbox": [100, 40, 132, 72],
                                    "center": [116, 56],
                                    "class_guess": "icon_lock",
                                }
                            ],
                            "distractors": [],
                            "label_source": "pred",
                            "source_batch": "reviewed-v1",
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return Group1PredictionResult(
                    output_dir=output_dir,
                    labels_path=labels_path,
                    sample_count=1,
                    command="uv run python -m train.group1.runner predict ...",
                )

            with patch("train.prelabel.run_group1_prediction_job", side_effect=_fake_predict):
                result = run_group1_prelabel(
                    Group1PrelabelRequest(
                        exam_root=exam_root,
                        dataset_config=root / "datasets" / "group1" / "v1" / "dataset.json",
                        proposal_model_path=root / "runs" / "group1" / "demo" / "proposal-detector" / "weights" / "best.pt",
                        query_model_path=root / "runs" / "group1" / "demo" / "query-parser" / "weights" / "best.pt",
                        project_dir=prediction_dir,
                    )
                )

            self.assertEqual(result.sample_count, 1)
            self.assertEqual(result.annotation_count, 2)
            self.assertTrue((exam_root / "reviewed" / "query" / "sample_0001.png").exists())
            self.assertTrue((exam_root / "reviewed" / "scene" / "sample_0001.png").exists())
            self.assertFalse((exam_root / "reviewed" / "labels.jsonl").exists())

            query_payload = json.loads((exam_root / "reviewed" / "query" / "sample_0001.json").read_text(encoding="utf-8"))
            self.assertEqual(query_payload["imagePath"], "sample_0001.png")
            self.assertEqual(query_payload["shapes"][0]["label"], "query_item")
            self.assertEqual(query_payload["shapes"][0]["flags"]["class_guess"], "icon_lock")

            scene_payload = json.loads((exam_root / "reviewed" / "scene" / "sample_0001.json").read_text(encoding="utf-8"))
            self.assertEqual(scene_payload["shapes"][0]["label"], "01")
            self.assertEqual(scene_payload["shapes"][0]["flags"]["class_guess"], "icon_lock")
            source_rows = read_jsonl(result.source_labels_path)
            self.assertEqual(source_rows[0]["label_source"], "seed")

    def test_group1_prelabel_refuses_to_overwrite_existing_reviewed_json_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            exam_root = root / "business-exams" / "group1" / "reviewed-v1"
            _write_png(exam_root / "import" / "query" / "sample_0001.png", 120, 36, (10, 10, 10))
            _write_png(exam_root / "import" / "scene" / "sample_0001.png", 320, 160, (220, 220, 220))
            (exam_root / "reviewed" / "query").mkdir(parents=True, exist_ok=True)
            (exam_root / "reviewed" / "scene").mkdir(parents=True, exist_ok=True)
            (exam_root / "reviewed" / "query" / "sample_0001.json").write_text("{}", encoding="utf-8")
            (exam_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "task": "group1",
                        "sample_count": 1,
                        "samples": [
                            {
                                "sample_id": "sample_0001",
                                "query_image": "import/query/sample_0001.png",
                                "scene_image": "import/scene/sample_0001.png",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "--overwrite"):
                run_group1_prelabel(
                    Group1PrelabelRequest(
                        exam_root=exam_root,
                        dataset_config=root / "datasets" / "group1" / "v1" / "dataset.json",
                        proposal_model_path=root / "runs" / "group1" / "demo" / "proposal-detector" / "weights" / "best.pt",
                        query_model_path=root / "runs" / "group1" / "demo" / "query-parser" / "weights" / "best.pt",
                        project_dir=root / "reports" / "group1",
                    )
                )

    def test_group1_query_directory_prelabel_writes_sidecar_json_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "materials" / "test" / "group1" / "query"
            image_path = input_dir / "sample_0001.png"
            _write_png(image_path, 120, 36, (10, 10, 10))
            query_model = root / "runs" / "group1" / "demo" / "query-parser" / "weights" / "best.pt"
            query_model.parent.mkdir(parents=True, exist_ok=True)
            query_model.write_text("fake-model", encoding="utf-8")

            class _TensorLike:
                def __init__(self, values: list[list[float]] | list[float]) -> None:
                    self._values = values

                def tolist(self):
                    return self._values

            fake_result = types.SimpleNamespace(
                names={0: "icon_lock"},
                boxes=types.SimpleNamespace(
                    xyxy=_TensorLike([[5.0, 8.0, 29.0, 30.0]]),
                    cls=_TensorLike([0.0]),
                    conf=_TensorLike([0.98]),
                ),
            )

            class _FakeYOLO:
                def __init__(self, model_path: str) -> None:
                    self.model_path = model_path

                def predict(self, *, source: str, imgsz: int, conf: float, device: str, verbose: bool):
                    self.last_call = {
                        "source": source,
                        "imgsz": imgsz,
                        "conf": conf,
                        "device": device,
                        "verbose": verbose,
                    }
                    return [fake_result]

            with patch("train.prelabel._ensure_training_dependencies") as ensure_deps:
                ensure_deps.return_value = None
                with patch.dict("sys.modules", {"ultralytics": types.SimpleNamespace(YOLO=_FakeYOLO)}):
                    result = run_group1_query_directory_prelabel(
                        Group1QueryDirectoryPrelabelRequest(
                            input_dir=input_dir,
                            query_model_path=query_model,
                            project_dir=root / "reports" / "group1" / "query-prelabel",
                        )
                    )

            self.assertEqual(result.sample_count, 1)
            self.assertEqual(result.annotation_count, 1)
            annotation_path = input_dir / "sample_0001.json"
            self.assertTrue(annotation_path.exists())
            annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
            self.assertEqual(annotation["imagePath"], "sample_0001.png")
            self.assertEqual(annotation["shapes"][0]["label"], "query_item")
            self.assertEqual(annotation["shapes"][0]["flags"]["class_guess"], "icon_lock")
            rows = read_jsonl(result.prediction_labels_path)
            self.assertEqual(rows[0]["query_items"][0]["class_guess"], "icon_lock")

    def test_group1_query_directory_prelabel_refuses_to_overwrite_existing_json_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "materials" / "test" / "group1" / "query"
            image_path = input_dir / "sample_0001.png"
            _write_png(image_path, 120, 36, (10, 10, 10))
            (input_dir / "sample_0001.json").write_text("{}", encoding="utf-8")
            query_model = root / "runs" / "group1" / "demo" / "query-parser" / "weights" / "best.pt"
            query_model.parent.mkdir(parents=True, exist_ok=True)
            query_model.write_text("fake-model", encoding="utf-8")

            with patch("train.prelabel._ensure_training_dependencies") as ensure_deps:
                ensure_deps.return_value = None
                with self.assertRaisesRegex(RuntimeError, "--overwrite"):
                    run_group1_query_directory_prelabel(
                        Group1QueryDirectoryPrelabelRequest(
                            input_dir=input_dir,
                            query_model_path=query_model,
                            project_dir=root / "reports" / "group1" / "query-prelabel",
                        )
                    )

    def test_group1_vlm_prelabel_pairs_query_and_scence_and_writes_reviewed_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pair_root = root / "work_home" / "materials" / "validation" / "group1"
            query_image = pair_root / "query" / "sample_0001.png"
            scene_image = pair_root / "scence" / "sample_0001.png"
            _write_png(query_image, 120, 36, (10, 10, 10))
            _write_png(scene_image, 320, 160, (220, 220, 220))

            fake_content = json.dumps(
                {
                    "query_items": [
                        {
                            "order": 9,
                            "bbox": [31, 8, 55, 30],
                            "class_guess": "icon_star",
                            "confidence": 0.87,
                        },
                        {
                            "order": 3,
                            "bbox": [5, 8, 29, 30],
                            "class_guess": "icon_lock",
                            "confidence": 0.91,
                        },
                    ],
                    "scene_targets": [
                        {
                            "order": 2,
                            "bbox": [180, 42, 212, 74],
                            "class_guess": "icon_star",
                            "confidence": 0.74,
                        },
                        {
                            "order": 1,
                            "bbox": [100, 40, 132, 72],
                            "class_guess": "icon_lock",
                            "confidence": 0.93,
                        },
                    ],
                },
                ensure_ascii=False,
            )

            with patch(
                "train.prelabel._post_json",
                return_value={"message": {"content": fake_content}},
            ):
                stderr_buffer = io.StringIO()
                output_root = root / "reports" / "group1" / "vlm-prelabel"
                with redirect_stderr(stderr_buffer):
                    result = run_group1_vlm_prelabel(
                        Group1VlmPrelabelRequest(
                            pair_root=pair_root,
                            model="qwen2.5vl:7b",
                            project_dir=output_root,
                        )
                    )
            logs = stderr_buffer.getvalue()

            self.assertEqual(result.sample_count, 1)
            self.assertEqual(result.annotation_count, 2)
            self.assertTrue((output_root / "reviewed" / "query" / "sample_0001.png").exists())
            self.assertTrue((output_root / "reviewed" / "scene" / "sample_0001.png").exists())
            query_payload = json.loads((output_root / "reviewed" / "query" / "sample_0001.json").read_text(encoding="utf-8"))
            scene_payload = json.loads((output_root / "reviewed" / "scene" / "sample_0001.json").read_text(encoding="utf-8"))
            self.assertEqual([shape["label"] for shape in query_payload["shapes"]], ["query_item", "query_item"])
            self.assertEqual([shape["flags"]["class_guess"] for shape in query_payload["shapes"]], ["icon_lock", "icon_star"])
            self.assertEqual([shape["label"] for shape in scene_payload["shapes"]], ["01", "02"])
            rows = read_jsonl(result.prediction_labels_path)
            self.assertEqual(rows[0]["label_source"], "vlm_pred")
            self.assertEqual([item["order"] for item in rows[0]["query_items"]], [1, 2])
            self.assertEqual(rows[0]["query_items"][0]["class_guess"], "icon_lock")
            self.assertEqual(rows[0]["scene_targets"][0]["center"], [116, 56])
            self.assertIn("qwen2.5vl:7b", result.prediction_command)
            self.assertIn("sample_id=sample_0001", logs)
            self.assertIn("sending request", logs)
            self.assertIn('"query_items"', logs)
            self.assertIn("normalized query_items=2 scene_targets=2", logs)
            self.assertEqual(result.review_dir, output_root / "reviewed")

    def test_group2_prelabel_copies_assets_and_writes_master_annotation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            exam_root = root / "business-exams" / "group2" / "reviewed-v1"
            master_image = exam_root / "import" / "master" / "sample_0001.png"
            tile_image = exam_root / "import" / "tile" / "sample_0001.png"
            _write_png(master_image, 320, 160, (220, 220, 220))
            _write_png(tile_image, 52, 52, (10, 10, 10))
            (exam_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "task": "group2",
                        "sample_count": 1,
                        "samples": [
                            {
                                "sample_id": "sample_0001",
                                "master_image": "import/master/sample_0001.png",
                                "tile_image": "import/tile/sample_0001.png",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            prediction_dir = root / "reports" / "group2" / "prelabel"

            def _fake_predict(job) -> Group2PredictionResult:
                output_dir = job.output_dir()
                output_dir.mkdir(parents=True, exist_ok=True)
                labels_path = output_dir / "labels.jsonl"
                labels_path.write_text(
                    json.dumps(
                        {
                            "sample_id": "sample_0001",
                            "master_image": str(master_image),
                            "tile_image": str(tile_image),
                            "target_gap": {
                                "class": "slider_gap",
                                "class_id": 0,
                                "bbox": [118, 46, 170, 98],
                                "center": [144, 72],
                            },
                            "tile_bbox": [0, 0, 52, 52],
                            "offset_x": 118,
                            "offset_y": 46,
                            "label_source": "predicted",
                            "source_batch": "reviewed-v1",
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return Group2PredictionResult(
                    output_dir=output_dir,
                    labels_path=labels_path,
                    sample_count=1,
                    command="uv run python -m train.group2.runner predict ...",
                )

            with patch("train.prelabel.run_group2_prediction_job", side_effect=_fake_predict):
                result = run_group2_prelabel(
                    Group2PrelabelRequest(
                        exam_root=exam_root,
                        dataset_config=root / "datasets" / "group2" / "v1" / "dataset.json",
                        model_path=root / "runs" / "group2" / "demo" / "weights" / "best.pt",
                        project_dir=prediction_dir,
                    )
                )

            self.assertEqual(result.sample_count, 1)
            self.assertEqual(result.annotation_count, 1)
            self.assertTrue((exam_root / "reviewed" / "master" / "sample_0001.png").exists())
            self.assertTrue((exam_root / "reviewed" / "tile" / "sample_0001.png").exists())
            payload = json.loads((exam_root / "reviewed" / "master" / "sample_0001.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["shapes"][0]["label"], "slider_gap")
            self.assertEqual(payload["shapes"][0]["points"], [[118, 46], [170, 98]])

    def test_group2_prelabel_runs_prediction_per_sample_for_mixed_tile_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            exam_root = root / "business-exams" / "group2" / "reviewed-v1"
            master_a = exam_root / "import" / "master" / "sample_0001.png"
            master_b = exam_root / "import" / "master" / "sample_0002.png"
            tile_a = exam_root / "import" / "tile" / "sample_0001.png"
            tile_b = exam_root / "import" / "tile" / "sample_0002.png"
            _write_png(master_a, 320, 160, (220, 220, 220))
            _write_png(master_b, 320, 160, (220, 220, 220))
            _write_png(tile_a, 25, 55, (10, 10, 10))
            _write_png(tile_b, 26, 54, (10, 10, 10))
            (exam_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "task": "group2",
                        "sample_count": 2,
                        "samples": [
                            {
                                "sample_id": "sample_0001",
                                "master_image": "import/master/sample_0001.png",
                                "tile_image": "import/tile/sample_0001.png",
                            },
                            {
                                "sample_id": "sample_0002",
                                "master_image": "import/master/sample_0002.png",
                                "tile_image": "import/tile/sample_0002.png",
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            prediction_dir = root / "reports" / "group2" / "prelabel"
            observed_sources: list[tuple[str, Path]] = []

            def _fake_predict(job) -> Group2PredictionResult:
                source_rows = read_jsonl(job.source)
                self.assertEqual(len(source_rows), 1)
                sample_id = str(source_rows[0]["sample_id"])
                observed_sources.append((sample_id, job.source))
                output_dir = job.output_dir()
                output_dir.mkdir(parents=True, exist_ok=True)
                labels_path = output_dir / "labels.jsonl"
                if sample_id == "sample_0001":
                    bbox = [118, 46, 143, 101]
                    tile_image = tile_a
                else:
                    bbox = [120, 44, 146, 98]
                    tile_image = tile_b
                labels_path.write_text(
                    json.dumps(
                        {
                            "sample_id": sample_id,
                            "master_image": str(master_a if sample_id == "sample_0001" else master_b),
                            "tile_image": str(tile_image),
                            "target_gap": {
                                "class": "slider_gap",
                                "class_id": 0,
                                "bbox": bbox,
                                "center": [int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2)],
                            },
                            "tile_bbox": [0, 0, bbox[2] - bbox[0], bbox[3] - bbox[1]],
                            "offset_x": bbox[0],
                            "offset_y": bbox[1],
                            "label_source": "predicted",
                            "source_batch": "reviewed-v1",
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return Group2PredictionResult(
                    output_dir=output_dir,
                    labels_path=labels_path,
                    sample_count=1,
                    command=f"uv run python -m train.group2.runner predict --source {job.source}",
                )

            with patch("train.prelabel.run_group2_prediction_job", side_effect=_fake_predict):
                result = run_group2_prelabel(
                    Group2PrelabelRequest(
                        exam_root=exam_root,
                        dataset_config=root / "datasets" / "group2" / "v1" / "dataset.json",
                        model_path=root / "runs" / "group2" / "demo" / "weights" / "best.pt",
                        project_dir=prediction_dir,
                    )
                )

            self.assertEqual(result.sample_count, 2)
            self.assertEqual(sorted(sample_id for sample_id, _ in observed_sources), ["sample_0001", "sample_0002"])
            self.assertTrue(all(path.name.endswith(".jsonl") for _, path in observed_sources))
            aggregated_rows = read_jsonl(result.prediction_labels_path)
            self.assertEqual([str(row["sample_id"]) for row in aggregated_rows], ["sample_0001", "sample_0002"])
            self.assertIn("per-sample", result.prediction_command)


if __name__ == "__main__":
    unittest.main()
