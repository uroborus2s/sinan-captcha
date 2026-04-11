from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from materials.background_style import (
    BackgroundStyleProfile,
    parse_background_style_response,
    run_background_style_collection,
)
from PIL import Image


def _write_background(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (96, 48), color)
    image.save(path)


class BackgroundStyleCollectTests(unittest.TestCase):
    def test_parse_background_style_response_normalizes_queries_and_terms(self) -> None:
        profile = parse_background_style_response(
            """
            ```json
            {
              "style_summary_zh": "浅色海滩度假背景，柔和低对比度。",
              "style_summary_en": "soft pastel beach vacation background",
              "search_queries": [
                "pastel beach landscape",
                "minimal ocean background",
                "pastel beach landscape"
              ],
              "negative_terms": ["captcha icons", "puzzle gap"]
            }
            ```
            """,
            source_image_count=2,
            request_payload={"model": "qwen2.5vl:7b"},
        )

        self.assertEqual(profile.source_image_count, 2)
        self.assertEqual(
            profile.search_queries,
            ("pastel beach landscape", "minimal ocean background"),
        )
        self.assertIn("puzzle gap", profile.negative_terms)

    def test_run_background_style_collection_downloads_pexels_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "reference-backgrounds"
            _write_background(source_dir / "a.png", (120, 180, 220))
            output_root = root / "background-pack"

            profile = BackgroundStyleProfile(
                source_image_count=1,
                style_summary_zh="浅色海滩背景",
                style_summary_en="soft beach background",
                search_queries=("soft beach background",),
                negative_terms=("icons", "captcha"),
                request_payload={"model": "qwen2.5vl:7b"},
                raw_output='{"ok": true}',
            )

            def fake_analyzer(**kwargs: object) -> BackgroundStyleProfile:
                self.assertEqual(kwargs["source_dir"], source_dir.resolve())
                return profile

            def fake_search(**kwargs: object) -> dict[str, object]:
                self.assertEqual(kwargs["query"], "soft beach background")
                return {
                    "photos": [
                        {
                            "id": 1001,
                            "photographer": "A. Photographer",
                            "src": {"large": "https://images.example/bg-1001.jpg"},
                        }
                    ]
                }

            def fake_download(url: str, destination: Path) -> None:
                self.assertEqual(url, "https://images.example/bg-1001.jpg")
                destination.write_bytes(b"fake-jpeg")

            result = run_background_style_collection(
                source_dir=source_dir,
                output_root=output_root,
                model="qwen2.5vl:7b",
                api_key="token",
                per_query=1,
                image_analyzer=fake_analyzer,
                search_client=fake_search,
                downloader=fake_download,
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["downloaded_count"], 1)
            self.assertTrue((output_root / "backgrounds" / "bg_pexels_1001.jpg").exists())
            self.assertEqual(
                (output_root / "manifests" / "materials.yaml").read_text(encoding="utf-8"),
                "schema_version: 3\n",
            )

            manifest_path = output_root / "manifests" / "backgrounds.csv"
            with manifest_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["background_id"], "bg_pexels_1001")
            self.assertEqual(rows[0]["query"], "soft beach background")

            report_path = output_root / "reports" / "background-style-collection.json"
            report = json.loads(report_path.read_text())
            self.assertEqual(report["style_profile"]["style_summary_en"], "soft beach background")
            self.assertEqual(
                report["downloaded_backgrounds"][0]["source_url"],
                "https://images.example/bg-1001.jpg",
            )

    def test_run_background_style_collection_dry_run_skips_api_key_and_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "reference-backgrounds"
            _write_background(source_dir / "a.png", (120, 180, 220))
            output_root = root / "background-pack"

            result = run_background_style_collection(
                source_dir=source_dir,
                output_root=output_root,
                model="qwen2.5vl:7b",
                api_key=None,
                dry_run=True,
                image_analyzer=lambda **_kwargs: BackgroundStyleProfile(
                    source_image_count=1,
                    style_summary_zh="浅色海滩背景",
                    style_summary_en="soft beach background",
                    search_queries=("soft beach background",),
                    negative_terms=(),
                    request_payload={},
                    raw_output="{}",
                ),
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["downloaded_count"], 0)
            self.assertFalse((output_root / "backgrounds").exists())


if __name__ == "__main__":
    unittest.main()
