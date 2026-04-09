from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from core.common.jsonl import read_jsonl
from core.exam.service import (
    export_group1_reviewed_labels,
    export_group2_reviewed_labels,
    prepare_group1_exam_sources,
    prepare_group2_exam_sources,
    build_group2_prelabel_yolo_dataset,
)


def _write_png(path: Path, width: int, height: int, color: tuple[int, int, int]) -> None:
    rows = [[color for _ in range(width)] for _ in range(height)]
    _write_rgb_png(path, rows)


def _write_rgb_png(path: Path, rows: list[list[tuple[int, int, int]]]) -> None:
    height = len(rows)
    width = len(rows[0]) if rows else 0
    if width <= 0 or height <= 0:
        raise ValueError("rows must not be empty")
    if any(len(row) != width for row in rows):
        raise ValueError("rows must have the same width")

    raw_rows = []
    for row in rows:
        raw_rows.append(b"\x00" + b"".join(bytes(pixel) for pixel in row))
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


def _read_png_ihdr(path: Path) -> tuple[int, int, int]:
    payload = path.read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"{path} is not a PNG file")
    if payload[12:16] != b"IHDR":
        raise AssertionError(f"{path} does not contain a PNG IHDR chunk")
    width, height = struct.unpack("!II", payload[16:24])
    color_type = payload[25]
    return width, height, color_type


def _write_labelme_rectangle(
    path: Path,
    *,
    image_path: str,
    image_width: int,
    image_height: int,
    label: str,
    bbox: tuple[int, int, int, int],
) -> None:
    x1, y1, x2, y2 = bbox
    payload = {
        "version": "5.5.0",
        "imagePath": image_path,
        "imageWidth": image_width,
        "imageHeight": image_height,
        "shapes": [
            {
                "label": label,
                "shape_type": "rectangle",
                "points": [[x1, y1], [x2, y2]],
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ExamServicePrepareTests(unittest.TestCase):
    def test_prepare_group1_exam_sources_copies_icon_and_bg_into_stable_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            materials_root = root / "materials"
            case_dir = materials_root / "group1" / "20260409001414_1"
            _write_png(case_dir / "icon.jpg", 120, 36, (10, 10, 10))
            _write_png(case_dir / "bg.jpg", 320, 160, (220, 220, 220))

            output_dir = root / "business-exams" / "group1" / "reviewed-v1"
            result = prepare_group1_exam_sources(materials_root=materials_root, output_dir=output_dir)

            self.assertEqual(result.sample_count, 1)
            self.assertTrue((output_dir / "import" / "query" / "20260409001414_1.jpg").exists())
            self.assertTrue((output_dir / "import" / "scene" / "20260409001414_1.jpg").exists())
            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["task"], "group1")
            self.assertEqual(manifest["sample_count"], 1)
            self.assertEqual(manifest["samples"][0]["sample_id"], "20260409001414_1")

    def test_prepare_group2_exam_sources_converts_gap_to_tight_cropped_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            materials_root = root / "materials"
            case_dir = materials_root / "result" / "20260409001414_2"
            _write_png(case_dir / "bg.jpg", 320, 160, (220, 220, 220))
            _write_rgb_png(
                case_dir / "gap.jpg",
                [
                    [(255, 255, 255)] * 7,
                    [(255, 255, 255), (255, 255, 255), (10, 10, 10), (10, 10, 10), (10, 10, 10), (255, 255, 255), (255, 255, 255)],
                    [(255, 255, 255), (255, 255, 255), (10, 10, 10), (10, 10, 10), (10, 10, 10), (255, 255, 255), (255, 255, 255)],
                    [(255, 255, 255)] * 7,
                    [(255, 255, 255)] * 7,
                ],
            )

            output_dir = root / "business-exams" / "group2" / "reviewed-v1"
            result = prepare_group2_exam_sources(materials_root=materials_root, output_dir=output_dir)

            self.assertEqual(result.sample_count, 1)
            self.assertTrue((output_dir / "import" / "master" / "20260409001414_2.jpg").exists())
            tile_path = output_dir / "import" / "tile" / "20260409001414_2.png"
            self.assertTrue(tile_path.exists())
            self.assertFalse((output_dir / "import" / "tile" / "20260409001414_2.jpg").exists())
            self.assertEqual(_read_png_ihdr(tile_path), (3, 2, 6))
            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["task"], "group2")
            self.assertEqual(manifest["sample_count"], 1)
            self.assertEqual(manifest["samples"][0]["sample_id"], "20260409001414_2")
            self.assertEqual(manifest["samples"][0]["tile_image"], "import/tile/20260409001414_2.png")


class ExamServiceExportTests(unittest.TestCase):
    def test_export_group1_reviewed_labels_merges_query_and_scene_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            exam_root = root / "business-exams" / "group1" / "reviewed-v1"
            query_dir = exam_root / "reviewed" / "query"
            scene_dir = exam_root / "reviewed" / "scene"
            _write_png(query_dir / "sample_0001.png", 120, 36, (10, 10, 10))
            _write_png(scene_dir / "sample_0001.png", 320, 160, (220, 220, 220))

            query_payload = {
                "version": "5.5.0",
                "imagePath": "sample_0001.png",
                "imageWidth": 120,
                "imageHeight": 36,
                "shapes": [
                    {"label": "icon_lock", "shape_type": "rectangle", "points": [[5, 8], [29, 30]]},
                    {"label": "icon_star", "shape_type": "rectangle", "points": [[40, 8], [64, 30]]},
                ],
            }
            (query_dir / "sample_0001.json").write_text(
                json.dumps(query_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            scene_payload = {
                "version": "5.5.0",
                "imagePath": "sample_0001.png",
                "imageWidth": 320,
                "imageHeight": 160,
                "shapes": [
                    {"label": "01|icon_lock", "shape_type": "rectangle", "points": [[100, 40], [132, 72]]},
                    {"label": "02|icon_star", "shape_type": "rectangle", "points": [[180, 56], [212, 88]]},
                ],
            }
            (scene_dir / "sample_0001.json").write_text(
                json.dumps(scene_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = export_group1_reviewed_labels(exam_root=exam_root)

            self.assertEqual(result.sample_count, 1)
            rows = read_jsonl(exam_root / "reviewed" / "labels.jsonl")
            self.assertEqual(rows[0]["label_source"], "reviewed")
            self.assertEqual(rows[0]["sample_id"], "sample_0001")
            self.assertEqual([item["class"] for item in rows[0]["query_targets"]], ["icon_lock", "icon_star"])
            self.assertEqual([item["order"] for item in rows[0]["scene_targets"]], [1, 2])
            self.assertEqual(rows[0]["scene_targets"][0]["center"], [116, 56])

    def test_export_group2_reviewed_labels_reads_master_annotation_and_tile_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            exam_root = root / "business-exams" / "group2" / "reviewed-v1"
            master_dir = exam_root / "reviewed" / "master"
            tile_dir = exam_root / "reviewed" / "tile"
            _write_png(master_dir / "sample_0001.png", 320, 160, (220, 220, 220))
            _write_png(tile_dir / "sample_0001.png", 52, 52, (10, 10, 10))
            _write_labelme_rectangle(
                master_dir / "sample_0001.json",
                image_path="sample_0001.png",
                image_width=320,
                image_height=160,
                label="slider_gap",
                bbox=(118, 46, 170, 98),
            )

            result = export_group2_reviewed_labels(exam_root=exam_root)

            self.assertEqual(result.sample_count, 1)
            rows = read_jsonl(exam_root / "reviewed" / "labels.jsonl")
            row = rows[0]
            self.assertEqual(row["label_source"], "reviewed")
            self.assertEqual(row["sample_id"], "sample_0001")
            self.assertEqual(row["target_gap"]["bbox"], [118, 46, 170, 98])
            self.assertEqual(row["target_gap"]["center"], [144, 72])
            self.assertEqual(row["tile_bbox"], [0, 0, 52, 52])
            self.assertEqual(row["offset_x"], 118)
            self.assertEqual(row["offset_y"], 46)


class Group2PrelabelDatasetTests(unittest.TestCase):
    def test_build_group2_prelabel_yolo_dataset_converts_reviewed_rows_to_single_image_detector_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "group2-reviewed"
            master_dir = source_dir / "master"
            tile_dir = source_dir / "tile"
            _write_png(master_dir / "sample_0001.png", 320, 160, (220, 220, 220))
            _write_png(tile_dir / "sample_0001.png", 52, 52, (10, 10, 10))
            (source_dir / "labels.jsonl").write_text(
                json.dumps(
                    {
                        "sample_id": "sample_0001",
                        "master_image": "master/sample_0001.png",
                        "tile_image": "tile/sample_0001.png",
                        "target_gap": {
                            "class": "slider_gap",
                            "class_id": 0,
                            "bbox": [118, 46, 170, 98],
                            "center": [144, 72],
                        },
                        "tile_bbox": [0, 0, 52, 52],
                        "offset_x": 118,
                        "offset_y": 46,
                        "label_source": "reviewed",
                        "source_batch": "exam_v1",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            output_dir = root / "group2-prelabel-yolo"
            result = build_group2_prelabel_yolo_dataset(source_dir=source_dir, output_dir=output_dir)

            self.assertEqual(result.sample_count, 1)
            self.assertTrue((output_dir / "images" / "all" / "sample_0001.png").exists())
            label_text = (output_dir / "labels" / "all" / "sample_0001.txt").read_text(encoding="utf-8").strip()
            self.assertTrue(label_text.startswith("0 "))
            dataset_yaml = (output_dir / "dataset.yaml").read_text(encoding="utf-8")
            self.assertIn("train: images/all", dataset_yaml)
            self.assertIn("names:", dataset_yaml)


if __name__ == "__main__":
    unittest.main()
