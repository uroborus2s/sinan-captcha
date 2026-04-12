from __future__ import annotations

import csv
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from common.jsonl import read_jsonl
from materials.background_style import (
    BackgroundStyleImageProfile,
    BackgroundStyleProfile,
    OllamaBackgroundProfileSummarizer,
    OllamaBackgroundReferenceAnalyzer,
    parse_background_style_response,
    run_background_style_collection,
)
from PIL import Image


def _write_background(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (96, 48), color)
    image.save(path)


def _make_downloaded_background_bytes(
    color: tuple[int, int, int],
    *,
    size: tuple[int, int] = (640, 360),
    format_name: str = "JPEG",
) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format=format_name)
    return buffer.getvalue()


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

    def test_parse_background_style_response_falls_back_to_style_features(self) -> None:
        profile = parse_background_style_response(
            """
            {
              "style_features": [
                "night cityscape blue and gold",
                "epic aerial nature photography"
              ],
              "negative_terms": ["text", "overlay"]
            }
            """,
            source_image_count=1,
            request_payload={"model": "gemma4:26b"},
            max_queries=3,
        )

        self.assertIn("night cityscape blue and gold", profile.style_summary_en)
        self.assertEqual(
            profile.search_queries,
            ("night cityscape blue and gold", "epic aerial nature photography"),
        )
        self.assertIn("overlay", profile.negative_terms)

    def test_parse_background_style_response_supports_nested_style_summary_object(self) -> None:
        profile = parse_background_style_response(
            """
            {
              "style_summary": {
                "zh": "宏伟自然景观与城市夜景背景",
                "en": "majestic landscapes and night cityscapes"
              }
            }
            """,
            source_image_count=1,
            request_payload={"model": "gemma4:26b"},
            max_queries=3,
        )

        self.assertEqual(profile.style_summary_zh, "宏伟自然景观与城市夜景背景")
        self.assertEqual(profile.style_summary_en, "majestic landscapes and night cityscapes")
        self.assertEqual(profile.search_queries, ("majestic landscapes and night cityscapes",))

    def test_ollama_reference_analyzer_returns_image_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "reference.png"
            _write_background(image_path, (120, 180, 220))
            analyzer = OllamaBackgroundReferenceAnalyzer(model="gemma4:26b")

            with patch(
                "materials.background_style._post_json",
                return_value={
                    "message": {
                        "content": json.dumps(
                            {
                                "style_summary_zh": "自然湖景背景",
                                "style_summary_en": "natural lake landscape",
                                "search_hints": ["lake landscape", "green mountains"],
                                "negative_terms": ["captcha"],
                            },
                            ensure_ascii=False,
                        )
                    }
                },
            ):
                profile = analyzer(
                    image_path=image_path,
                    image_sha256="sha256",
                )

            self.assertEqual(profile.image_path, str(image_path))
            self.assertEqual(profile.image_sha256, "sha256")
            self.assertEqual(profile.search_hints, ("lake landscape", "green mountains"))

    def test_ollama_profile_summarizer_returns_style_profile(self) -> None:
        summarizer = OllamaBackgroundProfileSummarizer(model="gemma4:26b")
        image_profiles = (
            BackgroundStyleImageProfile(
                image_path="/tmp/a.png",
                image_sha256="sha-a",
                style_summary_zh="自然湖景背景",
                style_summary_en="natural lake landscape",
                search_hints=("lake landscape", "green mountains"),
                negative_terms=("captcha",),
                request_payload={},
                raw_output="{}",
            ),
        )

        with patch(
            "materials.background_style._post_json",
            return_value={
                "message": {
                    "content": json.dumps(
                        {
                            "style_summary_zh": "自然湖景与山脉背景",
                            "style_summary_en": "natural lake and mountain landscape",
                            "search_queries": ["lake mountain landscape"],
                            "negative_terms": ["captcha"],
                        },
                        ensure_ascii=False,
                    )
                }
            },
        ):
            profile = summarizer(
                image_profiles=image_profiles,
                max_queries=3,
            )

        self.assertEqual(profile.source_image_count, 1)
        self.assertEqual(profile.search_queries, ("lake mountain landscape",))

    def test_ollama_profile_summarizer_repairs_schema_drift_and_logs_events(self) -> None:
        summarizer = OllamaBackgroundProfileSummarizer(model="gemma4:26b")
        image_profiles = (
            BackgroundStyleImageProfile(
                image_path="/tmp/a.png",
                image_sha256="sha-a",
                style_summary_zh="自然湖景背景",
                style_summary_en="natural lake landscape",
                search_hints=("lake landscape", "green mountains"),
                negative_terms=("captcha",),
                request_payload={},
                raw_output="{}",
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            drift_log = Path(tmpdir) / "background-style-drift-events.jsonl"
            prompts: list[str] = []

            def fake_post_json(
                _url: str,
                payload: dict[str, object],
                *,
                timeout_seconds: int,
            ) -> dict[str, object]:
                del timeout_seconds
                messages = payload["messages"]
                self.assertIsInstance(messages, list)
                prompts.append(str(messages[0]["content"]))
                if len(prompts) == 1:
                    return {
                        "message": {
                            "content": json.dumps(
                                {
                                    "style_summary": {
                                        "zh": "自然湖景与山脉背景",
                                        "en": "natural lake and mountain landscape",
                                    }
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                return {
                    "message": {
                        "content": json.dumps(
                            {
                                "style_summary_zh": "自然湖景与山脉背景",
                                "style_summary_en": "natural lake and mountain landscape",
                                "search_queries": ["lake mountain landscape"],
                                "negative_terms": ["captcha"],
                            },
                            ensure_ascii=False,
                        )
                    }
                }

            with patch("materials.background_style._post_json", side_effect=fake_post_json):
                profile = summarizer(
                    image_profiles=image_profiles,
                    max_queries=3,
                    drift_log_path=drift_log,
                )

            self.assertEqual(profile.search_queries, ("lake mountain landscape",))
            self.assertEqual(profile.request_payload["mode"], "ollama_summary_repair")
            self.assertEqual(len(prompts), 2)
            self.assertIn("请不要重新分析", prompts[1])
            drift_rows = read_jsonl(drift_log)
            self.assertEqual(
                [row["event_type"] for row in drift_rows],
                [
                    "summary_schema_drift_detected",
                    "summary_schema_repair_succeeded",
                ],
            )
            self.assertIn("missing_top_level_search_queries", drift_rows[0]["contract_issues"])

    def test_run_background_style_collection_falls_back_after_unusable_summary_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "reference-backgrounds"
            _write_background(source_dir / "a.png", (120, 180, 220))
            _write_background(source_dir / "b.png", (80, 120, 160))
            output_root = root / "background-pack"

            def fake_reference_analyzer(**kwargs: object) -> BackgroundStyleImageProfile:
                image_path = Path(str(kwargs["image_path"]))
                hints = (
                    ("lake", "landscape", "background")
                    if image_path.name == "a.png"
                    else ("city", "skyline", "night")
                )
                return BackgroundStyleImageProfile(
                    image_path=str(image_path),
                    image_sha256=str(kwargs["image_sha256"]),
                    style_summary_zh="背景",
                    style_summary_en="background",
                    search_hints=hints,
                    negative_terms=("captcha",),
                    request_payload={"image_path": str(image_path)},
                    raw_output="{}",
                )

            responses = [
                {
                    "message": {
                        "content": json.dumps(
                            {"style_summary_zh": "只有中文摘要"},
                            ensure_ascii=False,
                        )
                    }
                },
                {
                    "message": {
                        "content": json.dumps(
                            {"style_summary": {"zh": "还是只有中文摘要"}},
                            ensure_ascii=False,
                        )
                    }
                },
            ]

            with patch("materials.background_style._post_json", side_effect=responses):
                result = run_background_style_collection(
                    source_dir=source_dir,
                    output_root=output_root,
                    model="gemma4:26b",
                    api_key="token",
                    reference_image_analyzer=fake_reference_analyzer,
                    search_client=lambda **_kwargs: {"photos": []},
                    downloader=lambda _url, _destination: None,
                )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(
                result["style_profile"]["request_payload"]["mode"],
                "ollama_summary_local_fallback",
            )
            self.assertEqual(
                result["style_profile"]["search_queries"],
                ["lake landscape background", "city skyline night"],
            )
            self.assertTrue(Path(result["drift_log_jsonl"]).exists())
            self.assertGreaterEqual(result["drift_event_count"], 2)
            drift_rows = read_jsonl(Path(result["drift_log_jsonl"]))
            self.assertEqual(
                drift_rows[-1]["event_type"],
                "summary_schema_repair_failed_local_fallback",
            )

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
                destination.write_bytes(_make_downloaded_background_bytes((120, 180, 220)))

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
            self.assertEqual(result["rejected_count"], 0)
            self.assertEqual(result["merged_count"], 0)
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

    def test_run_background_style_collection_without_sample_limit_analyzes_all_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "reference-backgrounds"
            _write_background(source_dir / "a.png", (120, 180, 220))
            _write_background(source_dir / "b.png", (80, 120, 160))
            output_root = root / "background-pack"

            analyzed: list[str] = []

            def fake_reference_analyzer(**kwargs: object) -> BackgroundStyleImageProfile:
                image_path = Path(str(kwargs["image_path"]))
                analyzed.append(image_path.name)
                return BackgroundStyleImageProfile(
                    image_path=str(image_path),
                    image_sha256=str(kwargs["image_sha256"]),
                    style_summary_zh="背景",
                    style_summary_en="background",
                    search_hints=("background",),
                    negative_terms=(),
                    request_payload={"image_path": str(image_path)},
                    raw_output="{}",
                )

            result = run_background_style_collection(
                source_dir=source_dir,
                output_root=output_root,
                model="qwen2.5vl:7b",
                api_key=None,
                dry_run=True,
                sample_limit=None,
                reference_image_analyzer=fake_reference_analyzer,
            )

            self.assertEqual(sorted(analyzed), ["a.png", "b.png"])
            self.assertEqual(result["analysis_completed_count"], 2)

    def test_run_background_style_collection_prioritizes_one_download_per_reference_image(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "reference-backgrounds"
            _write_background(source_dir / "a.png", (120, 180, 220))
            _write_background(source_dir / "b.png", (80, 120, 160))
            output_root = root / "background-pack"

            def fake_reference_analyzer(**kwargs: object) -> BackgroundStyleImageProfile:
                image_path = Path(str(kwargs["image_path"]))
                if image_path.name == "a.png":
                    hints = ("forest", "lake", "background")
                else:
                    hints = ("snow", "mountain", "background")
                return BackgroundStyleImageProfile(
                    image_path=str(image_path),
                    image_sha256=str(kwargs["image_sha256"]),
                    style_summary_zh="背景",
                    style_summary_en="background",
                    search_hints=hints,
                    negative_terms=(),
                    request_payload={"image_path": str(image_path)},
                    raw_output="{}",
                )

            def fake_profile_summarizer(**_kwargs: object) -> BackgroundStyleProfile:
                return BackgroundStyleProfile(
                    source_image_count=2,
                    style_summary_zh="汇总背景",
                    style_summary_en="summary background",
                    search_queries=("shared summary query",),
                    negative_terms=(),
                    request_payload={},
                    raw_output="{}",
                )

            search_calls: list[str] = []

            def fake_search(**kwargs: object) -> dict[str, object]:
                query = str(kwargs["query"])
                search_calls.append(query)
                photo_map = {
                    "forest lake background": 1001,
                    "snow mountain background": 1002,
                    "shared summary query": 1003,
                }
                photo_id = photo_map[query]
                return {
                    "photos": [
                        {
                            "id": photo_id,
                            "photographer": f"Author-{photo_id}",
                            "src": {"large": f"https://images.example/bg-{photo_id}.jpg"},
                        }
                    ]
                }

            def fake_download(url: str, destination: Path) -> None:
                color_map = {
                    "https://images.example/bg-1001.jpg": (120, 180, 220),
                    "https://images.example/bg-1002.jpg": (80, 120, 160),
                    "https://images.example/bg-1003.jpg": (50, 60, 70),
                }
                destination.write_bytes(_make_downloaded_background_bytes(color_map[url]))

            result = run_background_style_collection(
                source_dir=source_dir,
                output_root=output_root,
                model="qwen2.5vl:7b",
                api_key="token",
                per_query=1,
                limit=2,
                reference_image_analyzer=fake_reference_analyzer,
                profile_summarizer=fake_profile_summarizer,
                search_client=fake_search,
                downloader=fake_download,
            )

            self.assertEqual(result["downloaded_count"], 2)
            self.assertEqual(
                search_calls,
                ["forest lake background", "snow mountain background"],
            )
            manifest_path = output_root / "manifests" / "backgrounds.csv"
            with manifest_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                {row["query"] for row in rows},
                {"forest lake background", "snow mountain background"},
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
            self.assertEqual(result["rejected_count"], 0)
            self.assertEqual(result["merged_count"], 0)
            self.assertFalse((output_root / "backgrounds").exists())

    def test_run_background_style_collection_rejects_small_or_invalid_downloads(self) -> None:
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
                negative_terms=(),
                request_payload={"model": "qwen2.5vl:7b"},
                raw_output='{"ok": true}',
            )

            def fake_search(**_kwargs: object) -> dict[str, object]:
                return {
                    "photos": [
                        {
                            "id": 1001,
                            "photographer": "Tiny",
                            "src": {"large": "https://images.example/bg-1001.jpg"},
                        },
                        {
                            "id": 1002,
                            "photographer": "Broken",
                            "src": {"large": "https://images.example/bg-1002.jpg"},
                        },
                    ]
                }

            def fake_download(url: str, destination: Path) -> None:
                if url.endswith("1001.jpg"):
                    destination.write_bytes(
                        _make_downloaded_background_bytes((120, 180, 220), size=(120, 60))
                    )
                    return
                destination.write_bytes(b"not-an-image")

            result = run_background_style_collection(
                source_dir=source_dir,
                output_root=output_root,
                model="qwen2.5vl:7b",
                api_key="token",
                per_query=2,
                min_width=256,
                min_height=128,
                image_analyzer=lambda **_kwargs: profile,
                search_client=fake_search,
                downloader=fake_download,
            )

            self.assertEqual(result["downloaded_count"], 0)
            self.assertEqual(result["rejected_count"], 2)
            self.assertFalse((output_root / "backgrounds" / "bg_pexels_1001.jpg").exists())
            reasons = {row["reason"] for row in result["rejected_backgrounds"]}
            self.assertIn("image_too_small", reasons)
            self.assertIn("invalid_image", reasons)

    def test_run_background_style_collection_can_merge_into_materials_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "reference-backgrounds"
            _write_background(source_dir / "a.png", (120, 180, 220))
            output_root = root / "background-pack"
            merge_root = root / "materials-root"

            (merge_root / "backgrounds").mkdir(parents=True, exist_ok=True)
            (merge_root / "manifests").mkdir(parents=True, exist_ok=True)
            (merge_root / "manifests" / "materials.yaml").write_text(
                "schema_version: 3\n",
                encoding="utf-8",
            )
            existing_path = merge_root / "backgrounds" / "existing.jpg"
            existing_path.write_bytes(_make_downloaded_background_bytes((120, 180, 220)))
            with (merge_root / "manifests" / "backgrounds.csv").open(
                "w",
                encoding="utf-8",
                newline="",
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "background_id",
                        "provider",
                        "query",
                        "author",
                        "license",
                        "source_url",
                        "file_name",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "background_id": "existing",
                        "provider": "local",
                        "query": "",
                        "author": "",
                        "license": "local",
                        "source_url": str(existing_path),
                        "file_name": "existing.jpg",
                    }
                )

            profile = BackgroundStyleProfile(
                source_image_count=1,
                style_summary_zh="浅色海滩背景",
                style_summary_en="soft beach background",
                search_queries=("soft beach background",),
                negative_terms=(),
                request_payload={"model": "qwen2.5vl:7b"},
                raw_output='{"ok": true}',
            )

            def fake_search(**_kwargs: object) -> dict[str, object]:
                return {
                    "photos": [
                        {
                            "id": 1001,
                            "photographer": "New",
                            "src": {"large": "https://images.example/bg-1001.jpg"},
                        },
                        {
                            "id": 1002,
                            "photographer": "Dup",
                            "src": {"large": "https://images.example/bg-1002.jpg"},
                        },
                    ]
                }

            def fake_download(url: str, destination: Path) -> None:
                if url.endswith("1001.jpg"):
                    destination.write_bytes(_make_downloaded_background_bytes((50, 60, 70)))
                    return
                destination.write_bytes(_make_downloaded_background_bytes((120, 180, 220)))

            result = run_background_style_collection(
                source_dir=source_dir,
                output_root=output_root,
                model="qwen2.5vl:7b",
                api_key="token",
                per_query=2,
                merge_into=merge_root,
                image_analyzer=lambda **_kwargs: profile,
                search_client=fake_search,
                downloader=fake_download,
            )

            self.assertEqual(result["downloaded_count"], 1)
            self.assertEqual(result["rejected_count"], 1)
            self.assertEqual(result["merged_count"], 1)
            self.assertEqual(result["merge_root"], str(merge_root.resolve()))
            self.assertTrue((merge_root / "backgrounds" / "bg_pexels_1001.jpg").exists())
            self.assertFalse((merge_root / "backgrounds" / "bg_pexels_1002.jpg").exists())

            with (merge_root / "manifests" / "backgrounds.csv").open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1]["file_name"], "bg_pexels_1001.jpg")
            self.assertEqual(result["rejected_backgrounds"][0]["reason"], "duplicate_image")

    def test_run_background_style_collection_checkpoints_each_reference_image_and_reuses_done_rows(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "reference-backgrounds"
            _write_background(source_dir / "a.png", (120, 180, 220))
            _write_background(source_dir / "b.png", (80, 120, 160))
            output_root = root / "background-pack"

            analyzed: list[str] = []

            def fake_reference_analyzer(**kwargs: object) -> BackgroundStyleImageProfile:
                image_path = Path(str(kwargs["image_path"]))
                analyzed.append(image_path.name)
                if image_path.name == "b.png":
                    raise RuntimeError("boom on second image")
                return BackgroundStyleImageProfile(
                    image_path=str(image_path),
                    image_sha256=str(kwargs["image_sha256"]),
                    style_summary_zh="浅色海滩背景",
                    style_summary_en="soft beach background",
                    search_hints=("soft", "beach", "background"),
                    negative_terms=("captcha",),
                    request_payload={"image_path": str(image_path)},
                    raw_output="{}",
                )

            with self.assertRaisesRegex(RuntimeError, "boom on second image"):
                run_background_style_collection(
                    source_dir=source_dir,
                    output_root=output_root,
                    model="qwen2.5vl:7b",
                    api_key=None,
                    dry_run=True,
                    reference_image_analyzer=fake_reference_analyzer,
                )

            self.assertEqual(analyzed, ["a.png", "b.png"])
            analysis_rows = read_jsonl(
                output_root / "reports" / "background-style-image-analysis.jsonl"
            )
            self.assertEqual(len(analysis_rows), 1)
            self.assertEqual(Path(analysis_rows[0]["image_path"]).name, "a.png")

            analyzed.clear()

            result = run_background_style_collection(
                source_dir=source_dir,
                output_root=output_root,
                model="qwen2.5vl:7b",
                api_key=None,
                dry_run=True,
                reference_image_analyzer=lambda **kwargs: BackgroundStyleImageProfile(
                    image_path=str(kwargs["image_path"]),
                    image_sha256=str(kwargs["image_sha256"]),
                    style_summary_zh="冷色城市背景",
                    style_summary_en="cool city background",
                    search_hints=("city", "cool", "background"),
                    negative_terms=("captcha",),
                    request_payload={"image_path": str(kwargs["image_path"])},
                    raw_output="{}",
                ),
            )

            self.assertEqual(result["analysis_reused_count"], 1)
            self.assertEqual(result["analysis_completed_count"], 2)
            analysis_rows = read_jsonl(
                output_root / "reports" / "background-style-image-analysis.jsonl"
            )
            self.assertEqual(len(analysis_rows), 2)

    def test_run_background_style_collection_resumes_download_tasks_from_saved_state(self) -> None:
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
                negative_terms=(),
                request_payload={"model": "qwen2.5vl:7b"},
                raw_output='{"ok": true}',
            )

            search_calls: list[int] = []

            def crashing_search(**kwargs: object) -> dict[str, object]:
                page = int(kwargs["page"])
                search_calls.append(page)
                if page == 1:
                    return {
                        "photos": [
                            {
                                "id": 1001,
                                "photographer": "First",
                                "src": {"large": "https://images.example/bg-1001.jpg"},
                            }
                        ]
                    }
                raise RuntimeError("boom on page 2")

            with self.assertRaisesRegex(RuntimeError, "boom on page 2"):
                run_background_style_collection(
                    source_dir=source_dir,
                    output_root=output_root,
                    model="qwen2.5vl:7b",
                    api_key="token",
                    per_query=2,
                    image_analyzer=lambda **_kwargs: profile,
                    search_client=crashing_search,
                    downloader=lambda _url, destination: destination.write_bytes(
                        _make_downloaded_background_bytes((120, 180, 220))
                    ),
                )

            self.assertEqual(search_calls, [1, 2])
            state_path = output_root / "reports" / "background-style-download-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["tasks"][0]["downloaded_count"], 1)
            self.assertEqual(state["tasks"][0]["next_page"], 2)

            search_calls.clear()

            def resume_search(**kwargs: object) -> dict[str, object]:
                page = int(kwargs["page"])
                search_calls.append(page)
                if page != 2:
                    raise AssertionError(f"unexpected resumed page: {page}")
                return {
                    "photos": [
                        {
                            "id": 1002,
                            "photographer": "Second",
                            "src": {"large": "https://images.example/bg-1002.jpg"},
                        }
                    ]
                }

            result = run_background_style_collection(
                source_dir=source_dir,
                output_root=output_root,
                model="qwen2.5vl:7b",
                api_key="token",
                per_query=2,
                image_analyzer=lambda **_kwargs: profile,
                search_client=resume_search,
                downloader=lambda url, destination: destination.write_bytes(
                    _make_downloaded_background_bytes(
                        (80, 100, 120) if url.endswith("1002.jpg") else (120, 180, 220)
                    )
                ),
            )

            self.assertEqual(search_calls, [2])
            self.assertEqual(result["downloaded_count"], 2)
            self.assertEqual(result["download_task_count"], 1)
            self.assertEqual(result["download_completed_task_count"], 1)


if __name__ == "__main__":
    unittest.main()
