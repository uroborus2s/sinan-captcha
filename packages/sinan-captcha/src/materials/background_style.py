"""Analyze reference background style and collect similar web backgrounds."""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import URLError

from auto_train.json_extract import extract_json_object
from common.jsonl import JsonMapping
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
DEFAULT_BACKGROUND_STYLE_SAMPLE_LIMIT = 12
DEFAULT_BACKGROUND_STYLE_MAX_QUERIES = 5
DEFAULT_BACKGROUND_STYLE_PER_QUERY = 8
DEFAULT_PEXELS_API_KEY_ENV = "PEXELS_API_KEY"

SearchClient = Callable[..., dict[str, object]]
Downloader = Callable[[str, Path], None]
ImageAnalyzer = Callable[..., "BackgroundStyleProfile"]


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
    api_key: str | None = None,
    api_key_env: str = DEFAULT_PEXELS_API_KEY_ENV,
    dry_run: bool = False,
    progress_reporter: ProgressReporter | None = None,
    image_analyzer: ImageAnalyzer | None = None,
    search_client: SearchClient | None = None,
    downloader: Downloader | None = None,
) -> dict[str, object]:
    resolved_source_dir = source_dir.resolve()
    resolved_output_root = output_root.resolve()
    analyzer = image_analyzer or analyze_background_style
    profile = analyzer(
        source_dir=resolved_source_dir,
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
        sample_limit=sample_limit,
        max_queries=max_queries,
        progress_reporter=progress_reporter,
    )

    downloaded_rows: list[dict[str, str]] = []
    if not dry_run:
        resolved_api_key = api_key or os.environ.get(api_key_env)
        if not resolved_api_key:
            raise ValueError(f"missing Pexels API key in environment variable: {api_key_env}")
        downloaded_rows = _download_pexels_backgrounds_for_profile(
            profile=profile,
            output_root=resolved_output_root,
            api_key=resolved_api_key,
            orientation=orientation,
            per_query=per_query,
            limit=limit,
            progress_reporter=progress_reporter,
            search_client=search_client or materials_service._search_pexels,
            downloader=downloader or materials_service._download_binary,
        )
        _write_materials_manifest(resolved_output_root / "manifests" / "materials.yaml")
        materials_service._write_csv(
            resolved_output_root / "manifests" / "backgrounds.csv",
            downloaded_rows,
        )

    report_path = resolved_output_root / "reports" / DEFAULT_BACKGROUND_STYLE_REPORT_NAME
    report = {
        "status": "ok",
        "source_dir": str(resolved_source_dir),
        "output_root": str(resolved_output_root),
        "dry_run": dry_run,
        "provider": "pexels",
        "orientation": orientation,
        "per_query": per_query,
        "limit": limit,
        "style_profile": profile.to_dict(),
        "downloaded_count": len(downloaded_rows),
        "downloaded_backgrounds": downloaded_rows,
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


def _download_pexels_backgrounds_for_profile(
    *,
    profile: BackgroundStyleProfile,
    output_root: Path,
    api_key: str,
    orientation: str,
    per_query: int,
    limit: int | None,
    progress_reporter: ProgressReporter | None,
    search_client: SearchClient,
    downloader: Downloader,
) -> list[dict[str, str]]:
    backgrounds_dir = output_root / "backgrounds"
    backgrounds_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    seen_ids: set[int] = set()
    max_total = limit if limit is not None else per_query * len(profile.search_queries)
    for query in profile.search_queries:
        if len(rows) >= max_total:
            break
        collected_for_query = 0
        page = 1
        while collected_for_query < per_query and len(rows) < max_total:
            payload = search_client(
                query=query,
                api_key=api_key,
                orientation=orientation,
                per_page=min(80, per_query - collected_for_query),
                page=page,
            )
            photos = payload.get("photos")
            if not isinstance(photos, list) or not photos:
                break
            for photo in photos:
                if not isinstance(photo, dict):
                    continue
                row = _download_pexels_photo(
                    photo=photo,
                    query=query,
                    backgrounds_dir=backgrounds_dir,
                    seen_ids=seen_ids,
                    progress_reporter=progress_reporter,
                    downloader=downloader,
                )
                if row is None:
                    continue
                rows.append(row)
                collected_for_query += 1
                if collected_for_query >= per_query or len(rows) >= max_total:
                    break
            page += 1
    return rows


def _download_pexels_photo(
    *,
    photo: dict[str, object],
    query: str,
    backgrounds_dir: Path,
    seen_ids: set[int],
    progress_reporter: ProgressReporter | None,
    downloader: Downloader,
) -> dict[str, str] | None:
    photo_id = photo.get("id")
    if not isinstance(photo_id, int) or photo_id in seen_ids:
        return None
    src = photo.get("src")
    if not isinstance(src, dict):
        return None
    image_url = materials_service._choose_pexels_image_url(src)
    if image_url is None:
        return None
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
        return None
    seen_ids.add(photo_id)
    return {
        "background_id": destination.stem,
        "provider": "pexels",
        "query": query,
        "author": str(photo.get("photographer", "")),
        "license": "Pexels License",
        "source_url": image_url,
        "file_name": destination.name,
    }


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
