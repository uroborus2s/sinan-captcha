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
