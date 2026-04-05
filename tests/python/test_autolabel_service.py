from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from core.autolabel.service import AutolabelRequest, run_autolabel
from core.common.jsonl import read_jsonl


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


class AutolabelServiceTests(unittest.TestCase):
    def test_group1_warmup_auto_copies_assets_and_marks_auto(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "raw"
            (input_dir / "query").mkdir(parents=True)
            (input_dir / "scene").mkdir(parents=True)
            _write_png(input_dir / "query" / "g1_000001.png", 120, 36, (20, 20, 20))
            _write_png(input_dir / "scene" / "g1_000001.png", 300, 150, (220, 220, 220))
            (input_dir / "labels.jsonl").write_text(
                (
                    '{"sample_id":"g1_000001","query_image":"query/g1_000001.png",'
                    '"scene_image":"scene/g1_000001.png","query_targets":[{"order":1,"class":"icon_house",'
                    '"class_id":0,"bbox":[8,8,26,26],"center":[17,17]}],"scene_targets":[{"order":1,"class":"icon_house",'
                    '"class_id":0,"bbox":[10,20,40,50],"center":[25,35]}],"distractors":[{"class":"icon_leaf",'
                    '"class_id":1,"bbox":[70,40,100,70],"center":[85,55]}],"label_source":"gold",'
                    '"source_batch":"batch_0001","seed":100}\n'
                ),
                encoding="utf-8",
            )

            output_dir = root / "interim"
            result = run_autolabel(
                AutolabelRequest(
                    task="group1",
                    mode="warmup-auto",
                    input_dir=input_dir,
                    output_dir=output_dir,
                    jitter_pixels=2,
                )
            )

            self.assertEqual(result.processed_count, 1)
            self.assertTrue((output_dir / "query" / "g1_000001.png").exists())
            self.assertTrue((output_dir / "scene" / "g1_000001.png").exists())

            rows = read_jsonl(output_dir / "labels.jsonl")
            self.assertEqual(rows[0]["label_source"], "auto")
            self.assertEqual(rows[0]["sample_id"], "g1_000001")
            self.assertEqual(rows[0]["scene_targets"][0]["order"], 1)
            self.assertNotEqual(rows[0]["scene_targets"][0]["bbox"], [10, 20, 40, 50])

    def test_group2_rule_auto_marks_auto_and_clamps_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "raw"
            (input_dir / "tile").mkdir(parents=True)
            (input_dir / "master").mkdir(parents=True)
            _write_png(input_dir / "tile" / "g2_000001.png", 60, 60, (20, 20, 20))
            _write_png(input_dir / "master" / "g2_000001.png", 200, 120, (240, 240, 240))
            (input_dir / "labels.jsonl").write_text(
                (
                    '{"sample_id":"g2_000001","master_image":"master/g2_000001.png",'
                    '"tile_image":"tile/g2_000001.png","target_gap":{"class":"slider_gap","class_id":0,'
                    '"bbox":[4,5,36,40],"center":[20,22]},"tile_bbox":[0,5,32,40],"offset_x":4,'
                    '"offset_y":0,"label_source":"gold","source_batch":"batch_0002","seed":101}\n'
                ),
                encoding="utf-8",
            )

            output_dir = root / "interim"
            result = run_autolabel(
                AutolabelRequest(
                    task="group2",
                    mode="rule-auto",
                    input_dir=input_dir,
                    output_dir=output_dir,
                    jitter_pixels=8,
                )
            )

            self.assertEqual(result.processed_count, 1)
            rows = read_jsonl(output_dir / "labels.jsonl")
            row = rows[0]
            self.assertEqual(row["label_source"], "auto")
            bbox = row["target_gap"]["bbox"]
            self.assertGreaterEqual(bbox[0], 0)
            self.assertGreaterEqual(bbox[1], 0)
            self.assertLessEqual(bbox[2], 200)
            self.assertLessEqual(bbox[3], 120)


if __name__ == "__main__":
    unittest.main()
