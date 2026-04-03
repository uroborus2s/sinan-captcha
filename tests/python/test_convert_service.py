from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from core.convert.service import ConversionRequest, build_yolo_dataset


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
    path.write_bytes(png)


class ConvertServiceTests(unittest.TestCase):
    def test_group1_builds_yolo_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "source"
            scene_dir = source_dir / "scene"
            query_dir = source_dir / "query"
            scene_dir.mkdir(parents=True)
            query_dir.mkdir(parents=True)

            _write_png(scene_dir / "g1_000001.png", 100, 50, (240, 240, 240))
            _write_png(query_dir / "g1_000001.png", 40, 20, (20, 20, 20))

            labels_path = source_dir / "labels.jsonl"
            labels_path.write_text(
                (
                    '{"sample_id":"g1_000001","query_image":"query/g1_000001.png",'
                    '"scene_image":"scene/g1_000001.png","targets":[{"order":1,'
                    '"class":"icon_house","class_id":0,"bbox":[10,10,30,30],"center":[20,20]}],'
                    '"distractors":[{"class":"icon_leaf","class_id":1,"bbox":[40,10,60,30],'
                    '"center":[50,20]}],"label_source":"gold","source_batch":"batch_0001","seed":1}\n'
                ),
                encoding="utf-8",
            )

            output_dir = root / "output"
            build_yolo_dataset(
                ConversionRequest(
                    task="group1",
                    version="v1",
                    source_dir=source_dir,
                    output_dir=output_dir,
                )
            )

            dataset_yaml = (output_dir / "dataset.yaml").read_text(encoding="utf-8")
            self.assertIn("path: .", dataset_yaml)
            self.assertIn("icon_house", dataset_yaml)
            self.assertIn("icon_leaf", dataset_yaml)

            train_images = list((output_dir / "images" / "train").glob("*.png"))
            self.assertEqual(len(train_images), 1)
            train_labels = list((output_dir / "labels" / "train").glob("*.txt"))
            self.assertEqual(len(train_labels), 1)
            label_lines = train_labels[0].read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(label_lines), 2)

    def test_group2_builds_yolo_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "source"
            master_dir = source_dir / "master"
            tile_dir = source_dir / "tile"
            master_dir.mkdir(parents=True)
            tile_dir.mkdir(parents=True)

            _write_png(master_dir / "g2_000001.png", 120, 80, (220, 220, 255))
            _write_png(tile_dir / "g2_000001.png", 30, 30, (10, 10, 10))

            labels_path = source_dir / "labels.jsonl"
            labels_path.write_text(
                (
                    '{"sample_id":"g2_000001","master_image":"master/g2_000001.png",'
                    '"tile_image":"tile/g2_000001.png","target_gap":{"class":"slider_gap",'
                    '"class_id":0,"bbox":[20,20,60,50],"center":[40,35]},"tile_bbox":[0,20,40,50],'
                    '"offset_x":20,"offset_y":0,"label_source":"gold","source_batch":"batch_0001","seed":1}\n'
                ),
                encoding="utf-8",
            )

            output_dir = root / "output"
            build_yolo_dataset(
                ConversionRequest(
                    task="group2",
                    version="v1",
                    source_dir=source_dir,
                    output_dir=output_dir,
                )
            )

            dataset_yaml = (output_dir / "dataset.yaml").read_text(encoding="utf-8")
            self.assertIn("path: .", dataset_yaml)
            self.assertIn("slider_gap", dataset_yaml)
            train_labels = list((output_dir / "labels" / "train").glob("*.txt"))
            self.assertEqual(len(train_labels), 1)
            self.assertEqual(len(train_labels[0].read_text(encoding="utf-8").strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
