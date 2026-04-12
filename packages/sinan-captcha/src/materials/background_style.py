"""Analyze reference background style and collect similar web backgrounds."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import shutil
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import URLError

from auto_train.json_extract import extract_json_object
from common.jsonl import JsonMapping, read_jsonl, write_jsonl
from common.paths import workspace_paths
from materials import service as materials_service
from materials.query_audit import (
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_URL,
    ProgressReporter,
    _emit_progress,
    _extract_ollama_message_content,
    _post_json,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
DEFAULT_BACKGROUND_OUTPUT_ROOT = workspace_paths(Path.cwd()).materials_dir / "incoming"
DEFAULT_BACKGROUND_STYLE_REPORT_NAME = "background-style-collection.json"
DEFAULT_BACKGROUND_STYLE_IMAGE_ANALYSIS_NAME = "background-style-image-analysis.jsonl"
DEFAULT_BACKGROUND_STYLE_SUMMARY_NAME = "background-style-summary.json"
DEFAULT_BACKGROUND_STYLE_DOWNLOAD_STATE_NAME = "background-style-download-state.json"
DEFAULT_BACKGROUND_STYLE_SAMPLE_LIMIT = 12
DEFAULT_BACKGROUND_STYLE_MAX_QUERIES = 5
DEFAULT_BACKGROUND_STYLE_PER_QUERY = 8
DEFAULT_PEXELS_API_KEY_ENV = "PEXELS_API_KEY"
DEFAULT_BACKGROUND_MIN_WIDTH = 256
DEFAULT_BACKGROUND_MIN_HEIGHT = 128
DEFAULT_BACKGROUND_MAX_HAMMING_DISTANCE = 0
BACKGROUND_REFERENCE_ANALYSIS_VERSION = "background-reference-analysis-v1"
BACKGROUND_PROFILE_SUMMARY_VERSION = "background-profile-summary-v1"
BACKGROUND_DOWNLOAD_STATE_VERSION = 1

SearchClient = Callable[..., dict[str, object]]
Downloader = Callable[[str, Path], None]
ImageAnalyzer = Callable[..., "BackgroundStyleProfile"]
ReferenceImageAnalyzer = Callable[..., "BackgroundStyleImageProfile"]
ProfileSummarizer = Callable[..., "BackgroundStyleProfile"]


@dataclass(frozen=True)
class BackgroundStyleProfile:
    source_image_count: int
    style_summary_zh: str
    style_summary_en: str
    search_queries: tuple[str, ...]
    negative_terms: tuple[str, ...]
    request_payload: JsonMapping
    raw_output: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["search_queries"] = list(self.search_queries)
        payload["negative_terms"] = list(self.negative_terms)
        return payload

    @classmethod
    def from_dict(cls, payload: JsonMapping) -> BackgroundStyleProfile:
        request_payload = payload.get("request_payload")
        return cls(
            source_image_count=int(payload.get("source_image_count", 0)),
            style_summary_zh=str(payload.get("style_summary_zh", "")).strip(),
            style_summary_en=str(payload.get("style_summary_en", "")).strip(),
            search_queries=_normalize_text_tuple(payload.get("search_queries"), limit=32),
            negative_terms=_normalize_text_tuple(payload.get("negative_terms"), limit=32),
            request_payload=request_payload if isinstance(request_payload, dict) else {},
            raw_output=str(payload.get("raw_output", "")),
        )


@dataclass(frozen=True)
class BackgroundStyleImageProfile:
    image_path: str
    image_sha256: str
    style_summary_zh: str
    style_summary_en: str
    search_hints: tuple[str, ...]
    negative_terms: tuple[str, ...]
    request_payload: JsonMapping
    raw_output: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["search_hints"] = list(self.search_hints)
        payload["negative_terms"] = list(self.negative_terms)
        return payload

    @classmethod
    def from_dict(cls, payload: JsonMapping) -> BackgroundStyleImageProfile:
        request_payload = payload.get("request_payload")
        return cls(
            image_path=str(payload.get("image_path", "")).strip(),
            image_sha256=str(payload.get("image_sha256", "")).strip(),
            style_summary_zh=str(payload.get("style_summary_zh", "")).strip(),
            style_summary_en=str(payload.get("style_summary_en", "")).strip(),
            search_hints=_normalize_text_tuple(payload.get("search_hints"), limit=16),
            negative_terms=_normalize_text_tuple(payload.get("negative_terms"), limit=16),
            request_payload=request_payload if isinstance(request_payload, dict) else {},
            raw_output=str(payload.get("raw_output", "")),
        )


@dataclass(frozen=True)
class BackgroundFingerprint:
    sha256: str
    ahash_bits: str
    width: int
    height: int


@dataclass
class BackgroundDownloadTask:
    query: str
    target_count: int
    downloaded_count: int = 0
    rejected_count: int = 0
    next_page: int = 1
    completed: bool = False
    exhausted: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "target_count": self.target_count,
            "downloaded_count": self.downloaded_count,
            "rejected_count": self.rejected_count,
            "next_page": self.next_page,
            "completed": self.completed,
            "exhausted": self.exhausted,
        }

    @classmethod
    def from_dict(cls, payload: JsonMapping) -> BackgroundDownloadTask:
        return cls(
            query=str(payload.get("query", "")).strip(),
            target_count=int(payload.get("target_count", 0)),
            downloaded_count=int(payload.get("downloaded_count", 0)),
            rejected_count=int(payload.get("rejected_count", 0)),
            next_page=max(1, int(payload.get("next_page", 1))),
            completed=bool(payload.get("completed", False)),
            exhausted=bool(payload.get("exhausted", False)),
        )


@dataclass
class BackgroundDownloadState:
    signature: str
    tasks: list[BackgroundDownloadTask]
    downloaded_rows: list[dict[str, str]]
    rejected_rows: list[dict[str, str]]
    seen_photo_ids: set[int]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": BACKGROUND_DOWNLOAD_STATE_VERSION,
            "signature": self.signature,
            "tasks": [task.to_dict() for task in self.tasks],
            "downloaded_backgrounds": self.downloaded_rows,
            "rejected_backgrounds": self.rejected_rows,
            "seen_photo_ids": sorted(self.seen_photo_ids),
        }

    @classmethod
    def from_dict(cls, payload: JsonMapping) -> BackgroundDownloadState:
        task_payload = payload.get("tasks")
        tasks = (
            [
                BackgroundDownloadTask.from_dict(task)
                for task in task_payload
                if isinstance(task, dict)
            ]
            if isinstance(task_payload, list)
            else []
        )
        downloaded_payload = payload.get("downloaded_backgrounds")
        rejected_payload = payload.get("rejected_backgrounds")
        seen_payload = payload.get("seen_photo_ids")
        downloaded_rows = (
            [dict(row) for row in downloaded_payload if isinstance(row, dict)]
            if isinstance(downloaded_payload, list)
            else []
        )
        rejected_rows = (
            [dict(row) for row in rejected_payload if isinstance(row, dict)]
            if isinstance(rejected_payload, list)
            else []
        )
        seen_photo_ids = (
            {int(photo_id) for photo_id in seen_payload}
            if isinstance(seen_payload, list)
            else set()
        )
        return cls(
            signature=str(payload.get("signature", "")),
            tasks=tasks,
            downloaded_rows=downloaded_rows,
            rejected_rows=rejected_rows,
            seen_photo_ids=seen_photo_ids,
        )


class OllamaBackgroundReferenceAnalyzer:
    """Analyze one reference image at a time so the result can be checkpointed."""

    def __init__(
        self,
        *,
        model: str,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        self._model = model
        self._ollama_url = ollama_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._progress_reporter = progress_reporter

    def __call__(
        self,
        *,
        image_path: Path,
        image_sha256: str,
        **_kwargs: object,
    ) -> BackgroundStyleImageProfile:
        prompt = _build_background_reference_prompt()
        image_bytes = image_path.read_bytes()
        request_payload = {
            "version": BACKGROUND_REFERENCE_ANALYSIS_VERSION,
            "model": self._model,
            "ollama_url": self._ollama_url,
            "timeout_seconds": self._timeout_seconds,
            "image_path": str(image_path),
            "image_sha256": image_sha256,
            "image_size_bytes": len(image_bytes),
            "prompt": prompt,
        }
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(image_bytes).decode("ascii")],
                }
            ],
        }
        _emit_progress(self._progress_reporter, "发送参考背景图到大模型", request_payload)
        raw_response = _post_json(
            f"{self._ollama_url}/api/chat",
            payload,
            timeout_seconds=self._timeout_seconds,
        )
        content = _extract_ollama_message_content(raw_response)
        _emit_progress(self._progress_reporter, "单图背景分析大模型原始响应", content)
        return parse_background_reference_response(
            content,
            image_path=image_path,
            image_sha256=image_sha256,
            request_payload=request_payload,
            raw_output=content,
        )


class OllamaBackgroundProfileSummarizer:
    """Aggregate per-image analysis into stable search queries."""

    def __init__(
        self,
        *,
        model: str,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        self._model = model
        self._ollama_url = ollama_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._progress_reporter = progress_reporter

    def __call__(
        self,
        *,
        image_profiles: Sequence[BackgroundStyleImageProfile],
        max_queries: int,
        **_kwargs: object,
    ) -> BackgroundStyleProfile:
        summary_input = [
            {
                "image_path": profile.image_path,
                "style_summary_zh": profile.style_summary_zh,
                "style_summary_en": profile.style_summary_en,
                "search_hints": list(profile.search_hints),
                "negative_terms": list(profile.negative_terms),
            }
            for profile in image_profiles
        ]
        prompt = _build_background_style_summary_prompt(
            summary_input=json.dumps(summary_input, ensure_ascii=False, indent=2),
            max_queries=max_queries,
        )
        request_payload = {
            "version": BACKGROUND_PROFILE_SUMMARY_VERSION,
            "model": self._model,
            "ollama_url": self._ollama_url,
            "timeout_seconds": self._timeout_seconds,
            "source_image_count": len(image_profiles),
            "max_queries": max_queries,
            "image_profiles": summary_input,
            "prompt": prompt,
        }
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
        }
        _emit_progress(self._progress_reporter, "发送背景风格汇总到大模型", request_payload)
        raw_response = _post_json(
            f"{self._ollama_url}/api/chat",
            payload,
            timeout_seconds=self._timeout_seconds,
        )
        content = _extract_ollama_message_content(raw_response)
        _emit_progress(self._progress_reporter, "背景风格汇总大模型原始响应", content)
        return parse_background_style_response(
            content,
            source_image_count=len(image_profiles),
            request_payload=request_payload,
            raw_output=content,
            max_queries=max_queries,
        )


def run_background_style_collection(
    *,
    source_dir: Path,
    output_root: Path,
    model: str,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    sample_limit: int = DEFAULT_BACKGROUND_STYLE_SAMPLE_LIMIT,
    max_queries: int = DEFAULT_BACKGROUND_STYLE_MAX_QUERIES,
    per_query: int = DEFAULT_BACKGROUND_STYLE_PER_QUERY,
    limit: int | None = None,
    orientation: str = "landscape",
    min_width: int = DEFAULT_BACKGROUND_MIN_WIDTH,
    min_height: int = DEFAULT_BACKGROUND_MIN_HEIGHT,
    max_hamming_distance: int = DEFAULT_BACKGROUND_MAX_HAMMING_DISTANCE,
    merge_into: Path | None = None,
    api_key: str | None = None,
    api_key_env: str = DEFAULT_PEXELS_API_KEY_ENV,
    dry_run: bool = False,
    progress_reporter: ProgressReporter | None = None,
    image_analyzer: ImageAnalyzer | None = None,
    reference_image_analyzer: ReferenceImageAnalyzer | None = None,
    profile_summarizer: ProfileSummarizer | None = None,
    search_client: SearchClient | None = None,
    downloader: Downloader | None = None,
) -> dict[str, object]:
    resolved_source_dir = source_dir.resolve()
    resolved_output_root = output_root.resolve()
    resolved_merge_into = merge_into.resolve() if merge_into is not None else None
    reports_dir = resolved_output_root / "reports"
    analysis_jsonl = reports_dir / DEFAULT_BACKGROUND_STYLE_IMAGE_ANALYSIS_NAME
    summary_json = reports_dir / DEFAULT_BACKGROUND_STYLE_SUMMARY_NAME
    download_state_json = reports_dir / DEFAULT_BACKGROUND_STYLE_DOWNLOAD_STATE_NAME

    if image_analyzer is not None:
        profile = image_analyzer(
            source_dir=resolved_source_dir,
            model=model,
            ollama_url=ollama_url,
            timeout_seconds=timeout_seconds,
            sample_limit=sample_limit,
            max_queries=max_queries,
            progress_reporter=progress_reporter,
        )
        analysis_reused_count = 0
        analysis_completed_count = profile.source_image_count
        summary_reused = False
        _write_background_style_summary(
            summary_json,
            source_dir=resolved_source_dir,
            image_profiles=(),
            profile=profile,
            summary_signature=_build_profile_signature(
                profile,
                per_query=per_query,
                limit=limit,
                orientation=orientation,
                min_width=min_width,
                min_height=min_height,
                max_hamming_distance=max_hamming_distance,
            ),
            analysis_reused_count=analysis_reused_count,
            summary_reused=summary_reused,
        )
    else:
        profile, analysis_reused_count, analysis_completed_count, summary_reused = (
            _load_or_create_background_style_profile(
                source_dir=resolved_source_dir,
                analysis_jsonl=analysis_jsonl,
                summary_json=summary_json,
                model=model,
                ollama_url=ollama_url,
                timeout_seconds=timeout_seconds,
                sample_limit=sample_limit,
                max_queries=max_queries,
                progress_reporter=progress_reporter,
                reference_image_analyzer=reference_image_analyzer,
                profile_summarizer=profile_summarizer,
                dry_run=dry_run,
                per_query=per_query,
                limit=limit,
                orientation=orientation,
                min_width=min_width,
                min_height=min_height,
                max_hamming_distance=max_hamming_distance,
            )
        )

    download_state: BackgroundDownloadState | None = None
    merged_rows: list[dict[str, str]] = []
    if not dry_run:
        resolved_api_key = api_key or os.environ.get(api_key_env)
        if not resolved_api_key:
            raise ValueError(f"missing Pexels API key in environment variable: {api_key_env}")
        known_fingerprints = _collect_existing_background_fingerprints(
            [
                resolved_output_root / "backgrounds",
                resolved_merge_into / "backgrounds" if resolved_merge_into is not None else None,
            ],
            progress_reporter=progress_reporter,
        )
        download_state = _download_pexels_backgrounds_for_profile(
            profile=profile,
            output_root=resolved_output_root,
            state_path=download_state_json,
            api_key=resolved_api_key,
            orientation=orientation,
            per_query=per_query,
            limit=limit,
            min_width=min_width,
            min_height=min_height,
            max_hamming_distance=max_hamming_distance,
            known_fingerprints=known_fingerprints,
            progress_reporter=progress_reporter,
            search_client=search_client or materials_service._search_pexels,
            downloader=downloader or materials_service._download_binary,
        )
        _write_materials_manifest(resolved_output_root / "manifests" / "materials.yaml")
        materials_service._write_csv(
            resolved_output_root / "manifests" / "backgrounds.csv",
            download_state.downloaded_rows,
        )
        if resolved_merge_into is not None:
            merged_rows = merge_background_rows_into_materials_root(
                source_root=resolved_output_root,
                target_root=resolved_merge_into,
                rows=download_state.downloaded_rows,
                progress_reporter=progress_reporter,
            )

    downloaded_rows = download_state.downloaded_rows if download_state is not None else []
    rejected_rows = download_state.rejected_rows if download_state is not None else []
    download_tasks = [task.to_dict() for task in download_state.tasks] if download_state else []
    report_path = resolved_output_root / "reports" / DEFAULT_BACKGROUND_STYLE_REPORT_NAME
    report = {
        "status": "ok",
        "source_dir": str(resolved_source_dir),
        "output_root": str(resolved_output_root),
        "merge_root": str(resolved_merge_into) if resolved_merge_into is not None else None,
        "dry_run": dry_run,
        "provider": "pexels",
        "orientation": orientation,
        "per_query": per_query,
        "limit": limit,
        "min_width": min_width,
        "min_height": min_height,
        "max_hamming_distance": max_hamming_distance,
        "style_profile": profile.to_dict(),
        "analysis_jsonl": str(analysis_jsonl),
        "style_summary_json": str(summary_json),
        "download_state_json": str(download_state_json),
        "analysis_reused_count": analysis_reused_count,
        "analysis_completed_count": analysis_completed_count,
        "summary_reused": summary_reused,
        "download_task_count": len(download_tasks),
        "download_completed_task_count": sum(1 for task in download_tasks if task["completed"]),
        "download_tasks": download_tasks,
        "downloaded_count": len(downloaded_rows),
        "downloaded_backgrounds": downloaded_rows,
        "rejected_count": len(rejected_rows),
        "rejected_backgrounds": rejected_rows,
        "merged_count": len(merged_rows),
        "merged_backgrounds": merged_rows,
        "report_json": str(report_path),
    }
    _write_json(report_path, report)
    _emit_progress(progress_reporter, "背景风格素材采集完成", report)
    return report


def analyze_background_style(
    *,
    source_dir: Path,
    model: str,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    sample_limit: int = DEFAULT_BACKGROUND_STYLE_SAMPLE_LIMIT,
    max_queries: int = DEFAULT_BACKGROUND_STYLE_MAX_QUERIES,
    progress_reporter: ProgressReporter | None = None,
) -> BackgroundStyleProfile:
    image_paths = list_background_images(source_dir, limit=sample_limit)
    if not image_paths:
        raise RuntimeError(f"未找到背景参考图片：{source_dir}")
    prompt = _build_background_style_prompt(max_queries=max_queries)
    encoded_images = [base64.b64encode(path.read_bytes()).decode("ascii") for path in image_paths]
    request_payload = {
        "model": model,
        "ollama_url": ollama_url.rstrip("/"),
        "timeout_seconds": timeout_seconds,
        "source_dir": str(source_dir),
        "image_paths": [str(path) for path in image_paths],
        "image_count": len(image_paths),
        "prompt": prompt,
    }
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": encoded_images,
            }
        ],
    }
    _emit_progress(progress_reporter, "发送背景参考图到大模型", request_payload)
    raw_response = _post_json(
        f"{ollama_url.rstrip('/')}/api/chat",
        payload,
        timeout_seconds=timeout_seconds,
    )
    content = _extract_ollama_message_content(raw_response)
    _emit_progress(progress_reporter, "背景风格大模型原始响应", content)
    return parse_background_style_response(
        content,
        source_image_count=len(image_paths),
        request_payload=request_payload,
        raw_output=content,
        max_queries=max_queries,
    )


def parse_background_reference_response(
    raw_output: str,
    *,
    image_path: Path,
    image_sha256: str,
    request_payload: JsonMapping,
) -> BackgroundStyleImageProfile:
    payload = extract_json_object(
        raw_output,
        required_keys={"style_summary_zh", "style_summary_en", "search_hints"},
    )
    style_summary_zh = _required_text(payload, "style_summary_zh")
    style_summary_en = _required_text(payload, "style_summary_en")
    search_hints = _normalize_text_tuple(payload.get("search_hints"), limit=8)
    if not search_hints:
        search_hints = (_compact_search_query(style_summary_en),)
    negative_terms = _normalize_text_tuple(payload.get("negative_terms"), limit=12)
    return BackgroundStyleImageProfile(
        image_path=str(image_path),
        image_sha256=image_sha256,
        style_summary_zh=style_summary_zh,
        style_summary_en=style_summary_en,
        search_hints=search_hints,
        negative_terms=negative_terms,
        request_payload=request_payload,
        raw_output=raw_output,
    )


def parse_background_style_response(
    raw_output: str,
    *,
    source_image_count: int,
    request_payload: JsonMapping,
    max_queries: int = DEFAULT_BACKGROUND_STYLE_MAX_QUERIES,
) -> BackgroundStyleProfile:
    payload = extract_json_object(
        raw_output,
        required_keys={"style_summary_zh", "style_summary_en", "search_queries"},
    )
    style_summary_zh = _required_text(payload, "style_summary_zh")
    style_summary_en = _required_text(payload, "style_summary_en")
    search_queries = _normalize_text_tuple(payload.get("search_queries"), limit=max_queries)
    if not search_queries:
        search_queries = (_compact_search_query(style_summary_en),)
    negative_terms = _normalize_text_tuple(payload.get("negative_terms"), limit=12)
    return BackgroundStyleProfile(
        source_image_count=source_image_count,
        style_summary_zh=style_summary_zh,
        style_summary_en=style_summary_en,
        search_queries=search_queries,
        negative_terms=negative_terms,
        request_payload=request_payload,
        raw_output=raw_output,
    )


def list_background_images(source_dir: Path, *, limit: int | None = None) -> list[Path]:
    image_paths = sorted(
        path
        for path in source_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    return image_paths[:limit] if limit is not None else image_paths


def _load_or_create_background_style_profile(
    *,
    source_dir: Path,
    analysis_jsonl: Path,
    summary_json: Path,
    model: str,
    ollama_url: str,
    timeout_seconds: int,
    sample_limit: int,
    max_queries: int,
    progress_reporter: ProgressReporter | None,
    reference_image_analyzer: ReferenceImageAnalyzer | None,
    profile_summarizer: ProfileSummarizer | None,
    dry_run: bool,
    per_query: int,
    limit: int | None,
    orientation: str,
    min_width: int,
    min_height: int,
    max_hamming_distance: int,
) -> tuple[BackgroundStyleProfile, int, int, bool]:
    image_paths = list_background_images(source_dir, limit=sample_limit)
    if not image_paths:
        raise RuntimeError(f"未找到背景参考图片：{source_dir}")
    analysis_key = _build_analysis_key(
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
    )
    cached_rows = _load_image_analysis_rows(analysis_jsonl)
    analyzer = reference_image_analyzer or OllamaBackgroundReferenceAnalyzer(
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
        progress_reporter=progress_reporter,
    )
    results: list[BackgroundStyleImageProfile] = []
    reused_count = 0
    for index, image_path in enumerate(image_paths, start=1):
        image_sha256 = _sha256_file(image_path)
        cached_row = cached_rows.get(str(image_path.resolve()))
        if _is_reusable_image_analysis_row(
            cached_row,
            image_path=image_path,
            image_sha256=image_sha256,
            analysis_key=analysis_key,
        ):
            result = BackgroundStyleImageProfile.from_dict(cached_row)
            reused_count += 1
            _emit_progress(
                progress_reporter,
                f"复用参考背景分析 {index}/{len(image_paths)}",
                {"image_path": str(image_path), "image_sha256": image_sha256},
            )
        else:
            _emit_progress(
                progress_reporter,
                f"分析参考背景图 {index}/{len(image_paths)}",
                {"image_path": str(image_path), "image_sha256": image_sha256},
            )
            result = analyzer(
                image_path=image_path,
                image_sha256=image_sha256,
                model=model,
                ollama_url=ollama_url,
                timeout_seconds=timeout_seconds,
                progress_reporter=progress_reporter,
            )
        results.append(
            _normalize_image_profile_output(
                result,
                image_path=image_path,
                image_sha256=image_sha256,
            )
        )
        _write_image_analysis_rows(
            analysis_jsonl,
            results,
            analysis_key=analysis_key,
        )
    summarizer = profile_summarizer or (
        _summarize_background_style_profiles_locally
        if dry_run
        else OllamaBackgroundProfileSummarizer(
            model=model,
            ollama_url=ollama_url,
            timeout_seconds=timeout_seconds,
            progress_reporter=progress_reporter,
        )
    )
    summary_signature = _build_summary_signature(
        image_profiles=results,
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
        max_queries=max_queries,
    )
    cached_profile = _load_cached_summary_profile(
        summary_json,
        summary_signature=summary_signature,
    )
    summary_reused = cached_profile is not None
    profile = cached_profile or summarizer(
        image_profiles=tuple(results),
        max_queries=max_queries,
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
        progress_reporter=progress_reporter,
    )
    _write_background_style_summary(
        summary_json,
        source_dir=source_dir,
        image_profiles=results,
        profile=profile,
        summary_signature=summary_signature,
        analysis_reused_count=reused_count,
        summary_reused=summary_reused,
    )
    return profile, reused_count, len(results), summary_reused


def _download_pexels_backgrounds_for_profile(
    *,
    profile: BackgroundStyleProfile,
    output_root: Path,
    state_path: Path,
    api_key: str,
    orientation: str,
    per_query: int,
    limit: int | None,
    min_width: int,
    min_height: int,
    max_hamming_distance: int,
    known_fingerprints: list[BackgroundFingerprint],
    progress_reporter: ProgressReporter | None,
    search_client: SearchClient,
    downloader: Downloader,
) -> BackgroundDownloadState:
    backgrounds_dir = output_root / "backgrounds"
    backgrounds_dir.mkdir(parents=True, exist_ok=True)
    state = _load_or_initialize_download_state(
        profile=profile,
        state_path=state_path,
        backgrounds_dir=backgrounds_dir,
        per_query=per_query,
        limit=limit,
        orientation=orientation,
        min_width=min_width,
        min_height=min_height,
        max_hamming_distance=max_hamming_distance,
    )
    _write_download_state(state_path, state)
    for task in state.tasks:
        if task.completed:
            continue
        while not task.completed:
            per_page = min(80, max(1, task.target_count - task.downloaded_count))
            page = task.next_page
            payload = search_client(
                query=task.query,
                api_key=api_key,
                orientation=orientation,
                per_page=per_page,
                page=page,
            )
            photos = payload.get("photos")
            if not isinstance(photos, list) or not photos:
                task.exhausted = True
                task.completed = True
                _write_download_state(state_path, state)
                break
            progress_made = False
            for photo in photos:
                before_seen_count = len(state.seen_photo_ids)
                row, rejection = _download_pexels_photo(
                    photo=photo,
                    query=task.query,
                    backgrounds_dir=backgrounds_dir,
                    seen_ids=state.seen_photo_ids,
                    min_width=min_width,
                    min_height=min_height,
                    max_hamming_distance=max_hamming_distance,
                    known_fingerprints=known_fingerprints,
                    progress_reporter=progress_reporter,
                    downloader=downloader,
                )
                if len(state.seen_photo_ids) != before_seen_count:
                    progress_made = True
                if rejection is not None:
                    state.rejected_rows.append(rejection)
                    task.rejected_count += 1
                    progress_made = True
                    _write_download_state(state_path, state)
                if row is None:
                    continue
                state.downloaded_rows.append(row)
                task.downloaded_count += 1
                progress_made = True
                _write_download_state(state_path, state)
                if task.downloaded_count >= task.target_count:
                    task.completed = True
                    break
            if task.completed:
                _write_download_state(state_path, state)
                break
            if not progress_made:
                task.exhausted = True
                task.completed = True
                _write_download_state(state_path, state)
                break
            task.next_page = page + 1
            _write_download_state(state_path, state)
    return state


def _download_pexels_photo(
    *,
    photo: dict[str, object],
    query: str,
    backgrounds_dir: Path,
    seen_ids: set[int],
    min_width: int,
    min_height: int,
    max_hamming_distance: int,
    known_fingerprints: list[BackgroundFingerprint],
    progress_reporter: ProgressReporter | None,
    downloader: Downloader,
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    photo_id = photo.get("id")
    if not isinstance(photo_id, int) or photo_id in seen_ids:
        return None, None
    seen_ids.add(photo_id)
    src = photo.get("src")
    if not isinstance(src, dict):
        return None, None
    image_url = materials_service._choose_pexels_image_url(src)
    if image_url is None:
        return None, None
    extension = materials_service._guess_extension_from_url(image_url)
    destination = backgrounds_dir / f"bg_pexels_{photo_id}{extension}"
    try:
        _emit_progress(
            progress_reporter,
            "下载背景候选图",
            {"query": query, "photo_id": photo_id, "url": image_url, "output": str(destination)},
        )
        downloader(image_url, destination)
    except (OSError, URLError) as exc:
        _emit_progress(
            progress_reporter,
            "下载背景候选图失败",
            {"query": query, "photo_id": photo_id, "url": image_url, "error": str(exc)},
        )
        return None, {
            "background_id": destination.stem,
            "photo_id": str(photo_id),
            "query": query,
            "source_url": image_url,
            "reason": "download_failed",
            "error": str(exc),
        }
    try:
        fingerprint = _inspect_background_image(destination)
    except RuntimeError as exc:
        _safe_unlink(destination)
        return None, {
            "background_id": destination.stem,
            "photo_id": str(photo_id),
            "query": query,
            "source_url": image_url,
            "reason": "invalid_image",
            "error": str(exc),
        }
    if fingerprint.width < min_width or fingerprint.height < min_height:
        _safe_unlink(destination)
        return None, {
            "background_id": destination.stem,
            "photo_id": str(photo_id),
            "query": query,
            "source_url": image_url,
            "reason": "image_too_small",
            "width": str(fingerprint.width),
            "height": str(fingerprint.height),
            "min_width": str(min_width),
            "min_height": str(min_height),
        }
    if _is_duplicate_fingerprint(
        fingerprint,
        known_fingerprints,
        max_hamming_distance=max_hamming_distance,
    ):
        _safe_unlink(destination)
        return None, {
            "background_id": destination.stem,
            "photo_id": str(photo_id),
            "query": query,
            "source_url": image_url,
            "reason": "duplicate_image",
        }
    known_fingerprints.append(fingerprint)
    return {
        "background_id": destination.stem,
        "photo_id": str(photo_id),
        "provider": "pexels",
        "query": query,
        "author": str(photo.get("photographer", "")),
        "license": "Pexels License",
        "source_url": image_url,
        "file_name": destination.name,
        "width": str(fingerprint.width),
        "height": str(fingerprint.height),
    }, None


def _build_background_reference_prompt() -> str:
    return (
        "你在为验证码生成器补充 backgrounds 背景素材。请只分析当前图片的背景本身，"
        "忽略并不要输出图片上的验证码图标、文字、滑块缺口、遮挡块、前景符号、点击目标、按钮、局部破损等干扰。\n\n"
        "请关注：场景类别、色彩、光照、纹理、真实摄影/插画/渐变/卡通等风格、画面复杂度。"
        "输出面向后续汇总阶段的中间特征，不要直接给太长描述。\n\n"
        "只输出 JSON，格式如下：\n"
        "{\n"
        '  "style_summary_zh": "中文背景风格总结",\n'
        '  "style_summary_en": "short English style summary",\n'
        '  "search_hints": ["english hint 1", "english hint 2"],\n'
        '  "negative_terms": ["captcha", "icons", "puzzle gap"]\n'
        "}"
    )


def _build_background_style_prompt(*, max_queries: int) -> str:
    return (
        "你在为验证码生成器补充背景素材。请综合分析提供的多张参考图片，只判断背景本身的视觉风格，"
        "忽略并不要输出图片上的验证码图标、文字、滑块缺口、遮挡块、前景符号、点击目标等信息。\n\n"
        "请关注：场景类别、色彩、光照、纹理、真实摄影/插画/渐变/卡通等风格、画面复杂度、适合作为验证码背景的搜索词。"
        "搜索词必须是英文，适合提交给 Pexels 这类图片搜索 API，"
        "不要包含 captcha、icon、puzzle、slider、gap、symbol 等词。\n\n"
        "只输出 JSON，格式如下：\n"
        "{\n"
        '  "style_summary_zh": "中文背景风格总结",\n'
        '  "style_summary_en": "short English style summary",\n'
        f'  "search_queries": ["english query 1", "...最多 {max_queries} 条"],\n'
        '  "negative_terms": ["captcha", "icons", "puzzle gap"]\n'
        "}"
    )


def _build_background_style_summary_prompt(*, summary_input: str, max_queries: int) -> str:
    return (
        "你在为验证码生成器补充 backgrounds 背景素材。下面是多张参考图逐张分析后的中间结果，"
        "请汇总成最终的背景风格结论和英文搜索词。请忽略 captcha、icon、puzzle gap 等干扰信息，"
        "只保留背景本身的风格描述和搜索方向。\n\n"
        "输入 JSON：\n"
        f"{summary_input}\n\n"
        "只输出 JSON，格式如下：\n"
        "{\n"
        '  "style_summary_zh": "中文背景风格总结",\n'
        '  "style_summary_en": "short English style summary",\n'
        f'  "search_queries": ["english query 1", "...最多 {max_queries} 条"],\n'
        '  "negative_terms": ["captcha", "icons", "puzzle gap"]\n'
        "}"
    )


def _summarize_background_style_profiles_locally(
    *,
    image_profiles: Sequence[BackgroundStyleImageProfile],
    max_queries: int,
    **_kwargs: object,
) -> BackgroundStyleProfile:
    style_summary_zh = "；".join(
        dict.fromkeys(
            profile.style_summary_zh
            for profile in image_profiles
            if profile.style_summary_zh
        )
    )
    style_summary_en = ", ".join(
        dict.fromkeys(
            profile.style_summary_en
            for profile in image_profiles
            if profile.style_summary_en
        )
    )
    search_queries = _build_fallback_search_queries(image_profiles, max_queries=max_queries)
    negative_terms = _normalize_text_tuple(
        [term for profile in image_profiles for term in profile.negative_terms],
        limit=12,
    )
    request_payload = {
        "mode": "local_fallback_summary",
        "source_image_count": len(image_profiles),
        "max_queries": max_queries,
    }
    raw_output = json.dumps(
        {
            "style_summary_zh": style_summary_zh,
            "style_summary_en": style_summary_en,
            "search_queries": list(search_queries),
            "negative_terms": list(negative_terms),
        },
        ensure_ascii=False,
    )
    return BackgroundStyleProfile(
        source_image_count=len(image_profiles),
        style_summary_zh=style_summary_zh or "背景风格汇总",
        style_summary_en=style_summary_en or "background style summary",
        search_queries=search_queries,
        negative_terms=negative_terms,
        request_payload=request_payload,
        raw_output=raw_output,
    )


def _build_fallback_search_queries(
    image_profiles: Sequence[BackgroundStyleImageProfile],
    *,
    max_queries: int,
) -> tuple[str, ...]:
    combined_queries: list[str] = []
    seen: set[str] = set()
    for profile in image_profiles:
        if profile.search_hints:
            query = " ".join(profile.search_hints[:3])
        else:
            query = _compact_search_query(profile.style_summary_en)
        normalized = " ".join(query.split()).strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        combined_queries.append(normalized)
        if len(combined_queries) >= max_queries:
            break
    if not combined_queries:
        combined_queries.append("natural landscape background")
    return tuple(combined_queries)


def _normalize_text_tuple(raw_value: object, *, limit: int) -> tuple[str, ...]:
    if isinstance(raw_value, str):
        values = [raw_value]
    elif isinstance(raw_value, list):
        values = [str(item) for item in raw_value if str(item).strip()]
    else:
        values = []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
        if len(normalized) >= limit:
            break
    return tuple(normalized)


def _required_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"background style response missing non-empty {key}")
    return " ".join(value.strip().split())


def _compact_search_query(value: str) -> str:
    words = [word for word in value.lower().replace(",", " ").split() if word]
    return " ".join(words[:8]) or "natural landscape background"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_materials_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("schema_version: 3\n", encoding="utf-8")


def _write_image_analysis_rows(
    path: Path,
    rows: Sequence[BackgroundStyleImageProfile],
    *,
    analysis_key: str,
) -> None:
    write_jsonl(
        path,
        [
            {
                **row.to_dict(),
                "analysis_key": analysis_key,
            }
            for row in rows
        ],
    )


def _load_image_analysis_rows(path: Path) -> dict[str, JsonMapping]:
    if not path.exists():
        return {}
    rows = read_jsonl(path)
    result: dict[str, JsonMapping] = {}
    for row in rows:
        image_path = str(row.get("image_path", "")).strip()
        if not image_path:
            continue
        result[str(Path(image_path).resolve())] = row
    return result


def _is_reusable_image_analysis_row(
    row: JsonMapping | None,
    *,
    image_path: Path,
    image_sha256: str,
    analysis_key: str,
) -> bool:
    if row is None:
        return False
    if str(Path(str(row.get("image_path", ""))).resolve()) != str(image_path.resolve()):
        return False
    if str(row.get("image_sha256", "")) != image_sha256:
        return False
    row_analysis_key = str(row.get("analysis_key", "")).strip()
    if row_analysis_key and row_analysis_key != analysis_key:
        return False
    try:
        profile = BackgroundStyleImageProfile.from_dict(row)
    except Exception:
        return False
    return bool(profile.style_summary_zh and profile.style_summary_en)


def _normalize_image_profile_output(
    profile: BackgroundStyleImageProfile,
    *,
    image_path: Path,
    image_sha256: str,
) -> BackgroundStyleImageProfile:
    return BackgroundStyleImageProfile(
        image_path=str(image_path),
        image_sha256=image_sha256,
        style_summary_zh=profile.style_summary_zh,
        style_summary_en=profile.style_summary_en,
        search_hints=profile.search_hints,
        negative_terms=profile.negative_terms,
        request_payload=profile.request_payload,
        raw_output=profile.raw_output,
    )


def _build_analysis_key(
    *,
    model: str,
    ollama_url: str,
    timeout_seconds: int,
) -> str:
    return _sha256_text(
        json.dumps(
            {
                "version": BACKGROUND_REFERENCE_ANALYSIS_VERSION,
                "model": model,
                "ollama_url": ollama_url.rstrip("/"),
                "timeout_seconds": timeout_seconds,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _build_summary_signature(
    *,
    image_profiles: Sequence[BackgroundStyleImageProfile],
    model: str,
    ollama_url: str,
    timeout_seconds: int,
    max_queries: int,
) -> str:
    return _sha256_text(
        json.dumps(
            {
                "version": BACKGROUND_PROFILE_SUMMARY_VERSION,
                "model": model,
                "ollama_url": ollama_url.rstrip("/"),
                "timeout_seconds": timeout_seconds,
                "max_queries": max_queries,
                "image_profiles": [
                    {
                        "image_path": profile.image_path,
                        "image_sha256": profile.image_sha256,
                        "style_summary_zh": profile.style_summary_zh,
                        "style_summary_en": profile.style_summary_en,
                        "search_hints": list(profile.search_hints),
                        "negative_terms": list(profile.negative_terms),
                    }
                    for profile in image_profiles
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _build_profile_signature(
    profile: BackgroundStyleProfile,
    *,
    per_query: int,
    limit: int | None,
    orientation: str,
    min_width: int,
    min_height: int,
    max_hamming_distance: int,
) -> str:
    return _sha256_text(
        json.dumps(
            {
                "style_profile": profile.to_dict(),
                "per_query": per_query,
                "limit": limit,
                "orientation": orientation,
                "min_width": min_width,
                "min_height": min_height,
                "max_hamming_distance": max_hamming_distance,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _load_cached_summary_profile(
    path: Path,
    *,
    summary_signature: str,
) -> BackgroundStyleProfile | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("summary_signature", "")) != summary_signature:
        return None
    style_profile = payload.get("style_profile")
    if not isinstance(style_profile, dict):
        return None
    return BackgroundStyleProfile.from_dict(style_profile)


def _write_background_style_summary(
    path: Path,
    *,
    source_dir: Path,
    image_profiles: Sequence[BackgroundStyleImageProfile],
    profile: BackgroundStyleProfile,
    summary_signature: str,
    analysis_reused_count: int,
    summary_reused: bool,
) -> None:
    _write_json(
        path,
        {
            "status": "ok",
            "source_dir": str(source_dir),
            "source_image_count": profile.source_image_count,
            "analysis_reused_count": analysis_reused_count,
            "summary_reused": summary_reused,
            "summary_signature": summary_signature,
            "image_profiles": [item.to_dict() for item in image_profiles],
            "style_profile": profile.to_dict(),
        },
    )


def _load_or_initialize_download_state(
    *,
    profile: BackgroundStyleProfile,
    state_path: Path,
    backgrounds_dir: Path,
    per_query: int,
    limit: int | None,
    orientation: str,
    min_width: int,
    min_height: int,
    max_hamming_distance: int,
) -> BackgroundDownloadState:
    signature = _build_profile_signature(
        profile,
        per_query=per_query,
        limit=limit,
        orientation=orientation,
        min_width=min_width,
        min_height=min_height,
        max_hamming_distance=max_hamming_distance,
    )
    fresh_state = BackgroundDownloadState(
        signature=signature,
        tasks=_build_download_tasks(
            search_queries=profile.search_queries,
            per_query=per_query,
            limit=limit,
        ),
        downloaded_rows=[],
        rejected_rows=[],
        seen_photo_ids=set(),
    )
    if not state_path.exists():
        return fresh_state
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    cached_state = BackgroundDownloadState.from_dict(payload)
    if cached_state.signature != signature:
        return fresh_state
    _reconcile_download_state(
        cached_state,
        backgrounds_dir=backgrounds_dir,
    )
    return cached_state


def _build_download_tasks(
    *,
    search_queries: Sequence[str],
    per_query: int,
    limit: int | None,
) -> list[BackgroundDownloadTask]:
    tasks: list[BackgroundDownloadTask] = []
    remaining = limit
    for query in search_queries:
        if remaining is None:
            target_count = per_query
        else:
            if remaining <= 0:
                break
            target_count = min(per_query, remaining)
            remaining -= target_count
        if target_count <= 0:
            continue
        tasks.append(BackgroundDownloadTask(query=query, target_count=target_count))
    return tasks


def _reconcile_download_state(
    state: BackgroundDownloadState,
    *,
    backgrounds_dir: Path,
) -> None:
    kept_rows: list[dict[str, str]] = []
    for row in state.downloaded_rows:
        file_name = row.get("file_name", "")
        if file_name and (backgrounds_dir / file_name).exists():
            kept_rows.append(row)
    state.downloaded_rows = kept_rows
    download_counts = Counter(row.get("query", "") for row in state.downloaded_rows)
    reject_counts = Counter(row.get("query", "") for row in state.rejected_rows)
    seen_photo_ids = set(state.seen_photo_ids)
    for row in [*state.downloaded_rows, *state.rejected_rows]:
        photo_id = _extract_photo_id_from_row(row)
        if photo_id is not None:
            seen_photo_ids.add(photo_id)
    state.seen_photo_ids = seen_photo_ids
    for task in state.tasks:
        task.downloaded_count = download_counts.get(task.query, 0)
        task.rejected_count = reject_counts.get(task.query, 0)
        if task.downloaded_count >= task.target_count:
            task.completed = True
        if task.exhausted:
            task.completed = True
        task.next_page = max(1, task.next_page)


def _extract_photo_id_from_row(row: dict[str, str]) -> int | None:
    raw_value = row.get("photo_id", "")
    if raw_value.isdigit():
        return int(raw_value)
    background_id = row.get("background_id", "")
    if background_id.startswith("bg_pexels_"):
        suffix = background_id.removeprefix("bg_pexels_")
        if suffix.isdigit():
            return int(suffix)
    return None


def _write_download_state(path: Path, state: BackgroundDownloadState) -> None:
    _write_json(path, state.to_dict())


def merge_background_rows_into_materials_root(
    *,
    source_root: Path,
    target_root: Path,
    rows: list[dict[str, str]],
    progress_reporter: ProgressReporter | None = None,
) -> list[dict[str, str]]:
    if not rows:
        return []
    source_backgrounds = source_root / "backgrounds"
    target_backgrounds = target_root / "backgrounds"
    target_backgrounds.mkdir(parents=True, exist_ok=True)
    manifests_dir = target_root / "manifests"
    existing_rows = _read_csv_rows(manifests_dir / "backgrounds.csv")
    existing_keys = {
        key
        for key in (_background_row_merge_key(row) for row in existing_rows)
        if key is not None
    }
    merged_rows: list[dict[str, str]] = []
    for row in rows:
        merge_key = _background_row_merge_key(row)
        if merge_key is not None and merge_key in existing_keys:
            continue
        source_path = source_backgrounds / row["file_name"]
        destination = _unique_destination_path(target_backgrounds, source_path.name)
        if source_path.resolve() != destination.resolve():
            shutil.copy2(source_path, destination)
        merged_row = dict(row)
        merged_row["background_id"] = destination.stem
        merged_row["file_name"] = destination.name
        merged_rows.append(merged_row)
        if merge_key is not None:
            existing_keys.add(merge_key)
        _emit_progress(
            progress_reporter,
            "合并背景图到正式素材根",
            {
                "source": str(source_path),
                "target": str(destination),
                "background_id": destination.stem,
            },
        )
    _write_materials_manifest(manifests_dir / "materials.yaml")
    materials_service._write_csv(
        manifests_dir / "backgrounds.csv",
        [*existing_rows, *merged_rows],
    )
    return merged_rows


def _background_row_merge_key(row: dict[str, str]) -> str | None:
    source_url = row.get("source_url", "").strip()
    if source_url:
        return f"source_url:{source_url}"
    background_id = row.get("background_id", "").strip()
    return f"background_id:{background_id}" if background_id else None


def _unique_destination_path(directory: Path, file_name: str) -> Path:
    candidate = directory / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        alt = directory / f"{stem}_{index}{suffix}"
        if not alt.exists():
            return alt
        index += 1


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _collect_existing_background_fingerprints(
    directories: list[Path | None],
    *,
    progress_reporter: ProgressReporter | None,
) -> list[BackgroundFingerprint]:
    fingerprints: list[BackgroundFingerprint] = []
    for directory in directories:
        if directory is None or not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                fingerprints.append(_inspect_background_image(path))
            except RuntimeError as exc:
                _emit_progress(
                    progress_reporter,
                    "跳过无法建立指纹的已有背景图",
                    {"path": str(path), "error": str(exc)},
                )
    return fingerprints


def _inspect_background_image(path: Path) -> BackgroundFingerprint:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dependency issue
        raise RuntimeError("当前环境缺少 Pillow，无法校验背景图片。") from exc
    payload = path.read_bytes()
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            grayscale = image.convert("L").resize((8, 8))
            pixels = [grayscale.getpixel((x, y)) for y in range(8) for x in range(8)]
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"无法解码背景图片：{path}") from exc
    average = sum(pixels) / float(len(pixels))
    ahash_bits = "".join("1" if pixel >= average else "0" for pixel in pixels)
    return BackgroundFingerprint(
        sha256=hashlib.sha256(payload).hexdigest(),
        ahash_bits=ahash_bits,
        width=width,
        height=height,
    )


def _is_duplicate_fingerprint(
    fingerprint: BackgroundFingerprint,
    existing: list[BackgroundFingerprint],
    *,
    max_hamming_distance: int,
) -> bool:
    for candidate in existing:
        if fingerprint.sha256 == candidate.sha256:
            return True
        if (
            max_hamming_distance > 0
            and _hamming_distance(fingerprint.ahash_bits, candidate.ahash_bits)
            <= max_hamming_distance
        ):
            return True
    return False


def _hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        raise ValueError("bit strings must have the same length")
    return sum(a != b for a, b in zip(left, right, strict=False))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
