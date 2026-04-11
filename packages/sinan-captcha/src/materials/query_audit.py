"""Build a group1 template icon pack from validation query images."""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from time import strftime
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from auto_train.json_extract import extract_json_object
from common.paths import workspace_paths
from common.jsonl import JsonMapping, read_jsonl, write_jsonl
from materials import service as materials_service
from materials.group1_query_icons import (
    DEFAULT_DARK_THRESHOLD,
    DEFAULT_MAX_HAMMING_DISTANCE,
    DEFAULT_MIN_PIXELS,
    QueryIconCandidate,
    QueryIconCluster,
    build_query_icon_candidates,
    cluster_query_icon_candidates,
    crop_candidate_image,
    load_pillow,
    normalize_icon_png,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
DEFAULT_GROUP1_QUERY_DIR = workspace_paths(Path.cwd()).materials_dir / "validation" / "group1" / "query"
DEFAULT_GROUP1_OUTPUT_ROOT = workspace_paths(Path.cwd()).materials_dir / "incoming"
DEFAULT_GROUP1_AUDIT_REPORT_NAME = "group1-query-audit.jsonl"
DEFAULT_GROUP1_AUDIT_TRACE_NAME = "group1-query-audit-trace.jsonl"
DEFAULT_GROUP1_TEMPLATE_REPORT_NAME = "group1-query-audit-templates.json"
DEFAULT_GROUP1_CACHE_DIR = workspace_paths(Path.cwd()).cache_dir / "materials" / "group1-query-audit"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 600
DEFAULT_MIN_VARIANTS_PER_TEMPLATE = 6
MAX_VARIANT_ID_LENGTH = 30
SVG_RASTERIZE_TIMEOUT_SECONDS = 30

DOWNLOAD_LIBRARY_SPECS: dict[str, dict[str, object]] = {
    "lucide": {
        "style": "outline",
        "kind": "svg",
        "urls": ("https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{slug}.svg",),
    },
    "tabler_outline": {
        "style": "outline",
        "kind": "svg",
        "urls": ("https://raw.githubusercontent.com/tabler/tabler-icons/master/icons/outline/{slug}.svg",),
    },
    "tabler_filled": {
        "style": "filled",
        "kind": "svg",
        "urls": ("https://raw.githubusercontent.com/tabler/tabler-icons/master/icons/filled/{slug}.svg",),
    },
    "heroicons_outline": {
        "style": "outline",
        "kind": "svg",
        "urls": (
            "https://raw.githubusercontent.com/tailwindlabs/heroicons/master/optimized/24/outline/{slug}.svg",
            "https://raw.githubusercontent.com/tailwindlabs/heroicons/master/src/24/outline/{slug}.svg",
        ),
    },
    "heroicons_solid": {
        "style": "filled",
        "kind": "svg",
        "urls": (
            "https://raw.githubusercontent.com/tailwindlabs/heroicons/master/optimized/24/solid/{slug}.svg",
            "https://raw.githubusercontent.com/tailwindlabs/heroicons/master/src/24/solid/{slug}.svg",
        ),
    },
    "bootstrap": {
        "style": "glyph",
        "kind": "svg",
        "urls": ("https://raw.githubusercontent.com/twbs/icons/main/icons/{slug}.svg",),
    },
    "google_material": {
        "style": "material",
        "kind": "google_png",
        "urls": (),
    },
}

DOWNLOAD_LIBRARY_ALIASES = {
    "bootstrap_icons": "bootstrap",
    "bootstrap-icons": "bootstrap",
    "google_materials": "google_material",
    "google-material": "google_material",
    "heroicons-solid": "heroicons_solid",
    "heroicons-outline": "heroicons_outline",
    "tabler-outline": "tabler_outline",
    "tabler-filled": "tabler_filled",
}


@dataclass(frozen=True)
class QueryIconDecision:
    order: int
    template_id: str
    zh_name: str
    family: str
    tags: tuple[str, ...]
    description: str
    reason: str


@dataclass(frozen=True)
class QueryImageClassification:
    icons: tuple[QueryIconDecision, ...]
    request_payload: JsonMapping | None = None
    raw_output: str | None = None
    response_payload: JsonMapping | None = None


@dataclass(frozen=True)
class QueryImageAuditResult:
    image_path: Path
    status: str
    icons: tuple[QueryIconDecision, ...]
    cluster_ids: tuple[str, ...] = ()
    error: str | None = None
    request_payload: JsonMapping | None = None
    raw_output: str | None = None
    response_payload: JsonMapping | None = None


@dataclass(frozen=True)
class ClusterAssignment:
    cluster_id: str
    template_id: str
    member_count: int
    representative: QueryIconCandidate
    zh_name_hints: tuple[str, ...]
    family_hints: tuple[str, ...]
    tag_hints: tuple[str, ...]
    descriptions: tuple[str, ...]


@dataclass(frozen=True)
class TemplateDownloadCandidate:
    library: str
    slug: str
    style: str


@dataclass(frozen=True)
class TemplateDraft:
    template_id: str
    cluster_ids: tuple[str, ...]
    zh_name_hints: tuple[str, ...]
    family_hints: tuple[str, ...]
    tag_hints: tuple[str, ...]
    descriptions: tuple[str, ...]
    member_count: int


@dataclass(frozen=True)
class TemplatePlan:
    template_id: str
    zh_name: str
    family: str
    tags: tuple[str, ...]
    description: str
    cluster_ids: tuple[str, ...]
    target_variant_count: int
    download_candidates: tuple[TemplateDownloadCandidate, ...]


@dataclass(frozen=True)
class VariantManifestEntry:
    variant_id: str
    source: str
    source_ref: str
    style: str


class QueryAuditClassificationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        request_payload: JsonMapping | None = None,
        raw_output: str | None = None,
        response_payload: JsonMapping | None = None,
    ) -> None:
        super().__init__(message)
        self.request_payload = request_payload
        self.raw_output = raw_output
        self.response_payload = response_payload


ImageClassifier = Callable[[Path], QueryImageClassification | tuple[QueryIconDecision, ...]]
TemplateEnricher = Callable[[Sequence[TemplateDraft]], Sequence[TemplatePlan]]
ProgressReporter = Callable[[str], None]


class OllamaQueryImageClassifier:
    """Use a local Ollama multimodal model to analyze group1 query images."""

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

    def __call__(self, image_path: Path) -> QueryImageClassification:
        prompt = _build_ollama_query_prompt()
        image_bytes = image_path.read_bytes()
        request_payload = {
            "model": self._model,
            "ollama_url": self._ollama_url,
            "timeout_seconds": self._timeout_seconds,
            "image_path": str(image_path),
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
        _emit_progress(self._progress_reporter, "发送 query 图到大模型", request_payload)
        raw_response: JsonMapping | None = None
        try:
            raw_response = _post_json(
                f"{self._ollama_url}/api/chat",
                payload,
                timeout_seconds=self._timeout_seconds,
            )
            content = _extract_ollama_message_content(raw_response)
        except Exception as exc:
            raise QueryAuditClassificationError(
                str(exc),
                request_payload=request_payload,
                response_payload=raw_response,
            ) from exc
        _emit_progress(self._progress_reporter, "query 图大模型原始响应", content)
        try:
            icons = parse_ollama_query_response(content)
        except Exception as exc:
            raise QueryAuditClassificationError(
                str(exc),
                request_payload=request_payload,
                raw_output=content,
                response_payload=raw_response,
            ) from exc
        return QueryImageClassification(
            icons=icons,
            request_payload=request_payload,
            raw_output=content,
            response_payload=raw_response,
        )


class OllamaTemplateEnricher:
    """Use local Ollama to enrich template metadata and download candidates."""

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

    def __call__(self, drafts: Sequence[TemplateDraft]) -> tuple[TemplatePlan, ...]:
        prompt = _build_ollama_template_prompt(drafts)
        request_payload = {
            "model": self._model,
            "ollama_url": self._ollama_url,
            "timeout_seconds": self._timeout_seconds,
            "template_count": len(drafts),
            "prompt": prompt,
        }
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
        }
        _emit_progress(self._progress_reporter, "发送 template 汇总到大模型", request_payload)
        raw_response: JsonMapping | None = None
        try:
            raw_response = _post_json(
                f"{self._ollama_url}/api/chat",
                payload,
                timeout_seconds=self._timeout_seconds,
            )
            content = _extract_ollama_message_content(raw_response)
        except Exception as exc:
            raise QueryAuditClassificationError(
                str(exc),
                request_payload=request_payload,
                response_payload=raw_response,
            ) from exc
        _emit_progress(self._progress_reporter, "template 汇总大模型原始响应", content)
        try:
            return parse_ollama_template_response(content, drafts)
        except Exception as exc:
            raise QueryAuditClassificationError(
                str(exc),
                request_payload=request_payload,
                raw_output=content,
                response_payload=raw_response,
            ) from exc


def run_group1_query_audit(
    *,
    query_dir: Path,
    model: str,
    repo_root: Path,
    output_root: Path = DEFAULT_GROUP1_OUTPUT_ROOT,
    report_root: Path | None = None,
    output_jsonl: Path | None = None,
    trace_jsonl: Path | None = None,
    template_report_json: Path | None = None,
    retry_from_report: Path | None = None,
    cache_dir: Path = DEFAULT_GROUP1_CACHE_DIR,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    min_variants_per_template: int = DEFAULT_MIN_VARIANTS_PER_TEMPLATE,
    dark_threshold: int = DEFAULT_DARK_THRESHOLD,
    min_pixels: int = DEFAULT_MIN_PIXELS,
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
    limit: int | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
    image_classifier: ImageClassifier | None = None,
    template_enricher: TemplateEnricher | None = None,
    progress_reporter: ProgressReporter | None = None,
) -> dict[str, object]:
    resolved_repo_root = repo_root.resolve()
    resolved_query_dir = _resolve_from_repo(query_dir, resolved_repo_root).resolve()
    resolved_output_root = _resolve_from_repo(output_root, resolved_repo_root)
    resolved_cache_dir = _resolve_from_repo(cache_dir, resolved_repo_root)
    resolved_report_root = _resolve_report_root(report_root, resolved_repo_root)
    resolved_output_jsonl = _resolve_report_path(output_jsonl, resolved_report_root, DEFAULT_GROUP1_AUDIT_REPORT_NAME)
    resolved_trace_jsonl = _resolve_report_path(trace_jsonl, resolved_report_root, DEFAULT_GROUP1_AUDIT_TRACE_NAME)
    resolved_template_report_json = _resolve_report_path(
        template_report_json,
        resolved_report_root,
        DEFAULT_GROUP1_TEMPLATE_REPORT_NAME,
    )
    resolved_retry_from_report = (
        _resolve_from_repo(retry_from_report, resolved_repo_root).resolve() if retry_from_report is not None else None
    )

    image_paths = list_query_images(resolved_query_dir)
    if limit is not None:
        image_paths = image_paths[:limit]
    if not image_paths:
        raise RuntimeError(f"未找到 group1 query 图片：{resolved_query_dir}")

    candidate_map: dict[Path, tuple[QueryIconCandidate, ...]] = {}
    all_candidates: list[QueryIconCandidate] = []
    for image_path in image_paths:
        candidates = tuple(
            build_query_icon_candidates(
                image_path,
                dark_threshold=dark_threshold,
                min_pixels=min_pixels,
            )
        )
        if not candidates:
            raise RuntimeError(f"未能从 query 图片中切出任何图标：{image_path}")
        candidate_map[image_path.resolve()] = candidates
        all_candidates.extend(candidates)

    clusters = cluster_query_icon_candidates(
        all_candidates,
        max_hamming_distance=max_hamming_distance,
    )
    cluster_by_candidate: dict[tuple[str, int], str] = {}
    cluster_map: dict[str, QueryIconCluster] = {}
    for cluster in clusters:
        cluster_map[cluster.cluster_id] = cluster
        for member in cluster.members:
            cluster_by_candidate[(str(member.source_path.resolve()), member.order)] = cluster.cluster_id

    classifier = image_classifier or OllamaQueryImageClassifier(
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
        progress_reporter=progress_reporter,
    )
    enricher = template_enricher or OllamaTemplateEnricher(
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
        progress_reporter=progress_reporter,
    )
    retry_rows = _load_retry_report_rows(resolved_retry_from_report, repo_root=resolved_repo_root)

    _emit_progress(
        progress_reporter,
        "开始执行 group1 query 审计并生成模板素材",
        {
            "query_dir": str(resolved_query_dir),
            "output_root": str(resolved_output_root),
            "image_count": len(image_paths),
            "icon_count": len(all_candidates),
            "cluster_count": len(clusters),
            "model": model,
            "min_variants_per_template": min_variants_per_template,
            "dry_run": dry_run,
            "retry_from_report": str(resolved_retry_from_report) if resolved_retry_from_report is not None else None,
        },
    )

    results: list[QueryImageAuditResult] = []
    reused_success_count = 0
    retried_image_count = 0

    def checkpoint_results() -> None:
        if dry_run:
            return
        write_jsonl(
            resolved_output_jsonl,
            [result_to_json_row(result, repo_root=resolved_repo_root) for result in results],
        )
        write_jsonl(
            resolved_trace_jsonl,
            [trace_result_to_json_row(result, repo_root=resolved_repo_root) for result in results],
        )

    for index, image_path in enumerate(image_paths, start=1):
        display_path = _display_path(image_path, resolved_repo_root)
        _emit_progress(
            progress_reporter,
            f"正在分析 query 图片 {index}/{len(image_paths)}",
            {"image_path": display_path},
        )
        expected_candidates = candidate_map[image_path.resolve()]
        cluster_ids = tuple(
            cluster_by_candidate[(str(image_path.resolve()), candidate.order)]
            for candidate in expected_candidates
        )
        cached_row = retry_rows.get(image_path.resolve())
        reused_result = _reuse_reported_success(
            cached_row,
            image_path=image_path,
            cluster_ids=cluster_ids,
            expected_icon_count=len(expected_candidates),
        )
        if reused_result is not None:
            reused_success_count += 1
            results.append(reused_result)
            checkpoint_results()
            _emit_progress(
                progress_reporter,
                f"复用历史成功审计 {index}/{len(image_paths)}",
                trace_result_to_json_row(reused_result, repo_root=resolved_repo_root),
            )
            continue
        if cached_row is not None and str(cached_row.get("status", "")).strip().lower() != "ok":
            retried_image_count += 1
            _emit_progress(
                progress_reporter,
                f"重试历史失败审计 {index}/{len(image_paths)}",
                {"image_path": display_path, "retry_from_report": str(resolved_retry_from_report)},
            )
        try:
            classification = _normalize_classification_output(classifier(image_path))
            if len(classification.icons) != len(expected_candidates):
                raise QueryAuditClassificationError(
                    (
                        "大模型返回的图标数量与本地切分结果不一致："
                        f"expected={len(expected_candidates)} actual={len(classification.icons)}"
                    ),
                    request_payload=classification.request_payload,
                    raw_output=classification.raw_output,
                    response_payload=classification.response_payload,
                )
            result = QueryImageAuditResult(
                image_path=image_path,
                status="ok",
                icons=classification.icons,
                cluster_ids=cluster_ids,
                request_payload=classification.request_payload,
                raw_output=classification.raw_output,
                response_payload=classification.response_payload,
            )
        except QueryAuditClassificationError as exc:
            result = QueryImageAuditResult(
                image_path=image_path,
                status="error",
                icons=(),
                error=str(exc),
                request_payload=exc.request_payload,
                raw_output=exc.raw_output,
                response_payload=exc.response_payload,
            )
        except Exception as exc:
            result = QueryImageAuditResult(
                image_path=image_path,
                status="error",
                icons=(),
                error=str(exc),
            )
        results.append(result)
        checkpoint_results()
        _emit_progress(
            progress_reporter,
            f"query 图片处理完成 {index}/{len(image_paths)}",
            trace_result_to_json_row(result, repo_root=resolved_repo_root),
        )

    output_rows = [result_to_json_row(result, repo_root=resolved_repo_root) for result in results]
    trace_rows = [trace_result_to_json_row(result, repo_root=resolved_repo_root) for result in results]

    error_count = sum(1 for result in results if result.status == "error")
    templates_payload: dict[str, object] = {
        "query_dir": str(resolved_query_dir),
        "image_count": len(image_paths),
        "icon_count": len(all_candidates),
        "cluster_count": len(clusters),
        "template_count": 0,
        "templates": [],
    }
    generated_variant_count = 0
    insufficient_templates: list[str] = []

    successful_results = [result for result in results if result.status == "ok"]
    if successful_results:
        assignments = build_cluster_assignments(successful_results, cluster_map=cluster_map)
        drafts = build_template_drafts(assignments.values())
        try:
            enriched_templates = merge_template_plans_with_drafts(enricher(drafts), drafts)
        except QueryAuditClassificationError as exc:
            error_count += 1
            _emit_progress(
                progress_reporter,
                "template 汇总失败",
                {
                    "error": str(exc),
                    "request_payload": exc.request_payload,
                    "raw_output": exc.raw_output,
                },
            )
            enriched_templates = tuple(fallback_template_plan(draft) for draft in drafts)
        templates_payload = render_template_report(
            drafts=drafts,
            templates=enriched_templates,
            repo_root=resolved_repo_root,
        )
        if not dry_run:
            generated_variant_count, insufficient_templates = write_template_pack(
                output_root=resolved_output_root,
                templates=enriched_templates,
                assignments=assignments,
                cache_dir=resolved_cache_dir,
                min_variants_per_template=min_variants_per_template,
                timeout_seconds=timeout_seconds,
                overwrite=overwrite,
                progress_reporter=progress_reporter,
            )

    if not dry_run:
        _write_json(resolved_template_report_json, templates_payload)

    status = "ok"
    if error_count > 0 or insufficient_templates:
        status = "error"
    summary = {
        "status": status,
        "query_dir": str(resolved_query_dir),
        "output_root": str(resolved_output_root),
        "report_root": str(resolved_report_root),
        "image_count": len(image_paths),
        "icon_count": len(all_candidates),
        "cluster_count": len(clusters),
        "template_count": templates_payload.get("template_count", 0),
        "generated_variant_count": generated_variant_count,
        "error_count": error_count,
        "insufficient_templates": insufficient_templates,
        "output_jsonl": str(resolved_output_jsonl),
        "trace_jsonl": str(resolved_trace_jsonl),
        "template_report_json": str(resolved_template_report_json),
        "retry_from_report": str(resolved_retry_from_report) if resolved_retry_from_report is not None else None,
        "reused_success_count": reused_success_count,
        "retried_image_count": retried_image_count,
        "dry_run": dry_run,
        "model": model,
    }
    _emit_progress(progress_reporter, "执行完成", summary)
    return summary


def list_query_images(query_dir: Path) -> list[Path]:
    if not query_dir.exists():
        raise FileNotFoundError(f"query directory does not exist: {query_dir}")
    if not query_dir.is_dir():
        raise NotADirectoryError(f"query path is not a directory: {query_dir}")
    return sorted(
        path
        for path in query_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def parse_ollama_query_response(raw_output: str) -> tuple[QueryIconDecision, ...]:
    payload = extract_json_object(raw_output, required_keys={"icons"})
    raw_icons = payload.get("icons")
    if not isinstance(raw_icons, list):
        raise ValueError("ollama response field 'icons' must be a list")
    normalized_icons: list[QueryIconDecision] = []
    for index, item in enumerate(raw_icons, start=1):
        if not isinstance(item, dict):
            raise ValueError("ollama response contains a non-object icon entry")
        normalized_icons.append(_normalize_query_icon_decision(item, index=index))
    normalized_icons.sort(key=lambda icon: icon.order)
    return tuple(normalized_icons)


def parse_ollama_template_response(
    raw_output: str,
    drafts: Sequence[TemplateDraft],
) -> tuple[TemplatePlan, ...]:
    payload = extract_json_object(raw_output, required_keys={"templates"})
    raw_templates = payload.get("templates")
    if not isinstance(raw_templates, list):
        raise ValueError("ollama response field 'templates' must be a list")
    allowed_template_ids = {draft.template_id for draft in drafts}
    plans: list[TemplatePlan] = []
    for item in raw_templates:
        if not isinstance(item, dict):
            raise ValueError("ollama response contains a non-object template entry")
        plan = _normalize_template_plan(item)
        if plan.template_id not in allowed_template_ids:
            continue
        plans.append(plan)
    return tuple(plans)


def build_cluster_assignments(
    results: Sequence[QueryImageAuditResult],
    *,
    cluster_map: Mapping[str, QueryIconCluster],
) -> dict[str, ClusterAssignment]:
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    zh_name_hints: dict[str, list[str]] = defaultdict(list)
    family_hints: dict[str, list[str]] = defaultdict(list)
    tag_hints: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, list[str]] = defaultdict(list)

    for result in results:
        if result.status != "ok":
            continue
        for icon, cluster_id in zip(result.icons, result.cluster_ids, strict=False):
            votes[cluster_id][icon.template_id] += 1
            if icon.zh_name:
                zh_name_hints[cluster_id].append(icon.zh_name)
            if icon.family:
                family_hints[cluster_id].append(icon.family)
            tag_hints[cluster_id].extend(icon.tags)
            if icon.description:
                descriptions[cluster_id].append(icon.description)

    assignments: dict[str, ClusterAssignment] = {}
    for cluster_id, vote_counter in votes.items():
        template_id = _select_majority_template_id(vote_counter)
        cluster = cluster_map[cluster_id]
        assignments[cluster_id] = ClusterAssignment(
            cluster_id=cluster_id,
            template_id=template_id,
            member_count=len(cluster.members),
            representative=cluster.representative,
            zh_name_hints=tuple(_unique_preserve_order(zh_name_hints[cluster_id])),
            family_hints=tuple(_unique_preserve_order(family_hints[cluster_id])),
            tag_hints=tuple(_unique_preserve_order(tag_hints[cluster_id])),
            descriptions=tuple(_unique_preserve_order(descriptions[cluster_id])),
        )
    return assignments


def build_template_drafts(assignments: Sequence[ClusterAssignment]) -> tuple[TemplateDraft, ...]:
    grouped: dict[str, list[ClusterAssignment]] = defaultdict(list)
    for assignment in assignments:
        grouped[assignment.template_id].append(assignment)

    drafts: list[TemplateDraft] = []
    for template_id, items in sorted(grouped.items()):
        drafts.append(
            TemplateDraft(
                template_id=template_id,
                cluster_ids=tuple(sorted(item.cluster_id for item in items)),
                zh_name_hints=tuple(_unique_preserve_order(_flatten(item.zh_name_hints for item in items))),
                family_hints=tuple(_unique_preserve_order(_flatten(item.family_hints for item in items))),
                tag_hints=tuple(_unique_preserve_order(_flatten(item.tag_hints for item in items))),
                descriptions=tuple(_unique_preserve_order(_flatten(item.descriptions for item in items))),
                member_count=sum(item.member_count for item in items),
            )
        )
    return tuple(drafts)


def fallback_template_plan(draft: TemplateDraft) -> TemplatePlan:
    return TemplatePlan(
        template_id=draft.template_id,
        zh_name=draft.zh_name_hints[0] if draft.zh_name_hints else draft.template_id.removeprefix("tpl_"),
        family=draft.family_hints[0] if draft.family_hints else "generic",
        tags=draft.tag_hints or (draft.template_id.removeprefix("tpl_"),),
        description=draft.descriptions[0] if draft.descriptions else draft.template_id.removeprefix("tpl_"),
        cluster_ids=draft.cluster_ids,
        target_variant_count=max(DEFAULT_MIN_VARIANTS_PER_TEMPLATE, len(draft.cluster_ids)),
        download_candidates=build_fallback_download_candidates(draft.template_id),
    )


def merge_template_plans_with_drafts(
    plans: Sequence[TemplatePlan],
    drafts: Sequence[TemplateDraft],
) -> tuple[TemplatePlan, ...]:
    by_id = {plan.template_id: plan for plan in plans}
    merged: list[TemplatePlan] = []
    for draft in drafts:
        plan = by_id.get(draft.template_id)
        if plan is None:
            merged.append(fallback_template_plan(draft))
            continue
        family = plan.family or (draft.family_hints[0] if draft.family_hints else "generic")
        tags = plan.tags or draft.tag_hints or (draft.template_id.removeprefix("tpl_"),)
        description = plan.description or (draft.descriptions[0] if draft.descriptions else draft.template_id)
        zh_name = plan.zh_name or (draft.zh_name_hints[0] if draft.zh_name_hints else draft.template_id)
        merged.append(
            TemplatePlan(
                template_id=draft.template_id,
                zh_name=zh_name,
                family=family,
                tags=tuple(_unique_preserve_order(tags)),
                description=description,
                cluster_ids=draft.cluster_ids,
                target_variant_count=max(plan.target_variant_count, len(draft.cluster_ids)),
                download_candidates=merge_download_candidates(
                    plan.download_candidates,
                    build_fallback_download_candidates(draft.template_id),
                ),
            )
        )
    return tuple(merged)


def build_fallback_download_candidates(template_id: str) -> tuple[TemplateDownloadCandidate, ...]:
    stem = template_id.removeprefix("tpl_")
    slug = stem.replace("_", "-")
    google_slug = stem
    candidates = [
        TemplateDownloadCandidate("lucide", slug, "outline"),
        TemplateDownloadCandidate("tabler_outline", slug, "outline"),
        TemplateDownloadCandidate("tabler_filled", slug, "filled"),
        TemplateDownloadCandidate("heroicons_outline", slug, "outline"),
        TemplateDownloadCandidate("heroicons_solid", slug, "filled"),
        TemplateDownloadCandidate("bootstrap", slug, "glyph"),
        TemplateDownloadCandidate("google_material", google_slug, "material"),
    ]
    return tuple(candidates)


def merge_download_candidates(
    primary: Sequence[TemplateDownloadCandidate],
    fallback: Sequence[TemplateDownloadCandidate],
) -> tuple[TemplateDownloadCandidate, ...]:
    merged: list[TemplateDownloadCandidate] = []
    seen: set[tuple[str, str]] = set()
    for candidate in (*primary, *fallback):
        key = (candidate.library, candidate.slug)
        if key in seen:
            continue
        seen.add(key)
        merged.append(candidate)
    return tuple(merged)


def write_template_pack(
    *,
    output_root: Path,
    templates: Sequence[TemplatePlan],
    assignments: Mapping[str, ClusterAssignment],
    cache_dir: Path,
    min_variants_per_template: int,
    timeout_seconds: int,
    overwrite: bool,
    progress_reporter: ProgressReporter | None,
) -> tuple[int, list[str]]:
    manifests_dir = output_root / "manifests"
    icons_root = output_root / "group1" / "icons"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    icons_root.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    template_variants: dict[str, list[VariantManifestEntry]] = {}
    final_variant_ids: dict[str, set[str]] = {}
    generated_variant_count = 0
    insufficient_templates: list[str] = []

    for template in templates:
        target_dir = icons_root / template.template_id
        target_dir.mkdir(parents=True, exist_ok=True)
        variant_entries: list[VariantManifestEntry] = []
        variant_ids: set[str] = set()
        target_variant_count = max(template.target_variant_count, min_variants_per_template)
        for cluster_id in template.cluster_ids:
            assignment = assignments[cluster_id]
            variant_id = _build_real_variant_id(
                template_id=template.template_id,
                assignment=assignment,
                existing_ids=variant_ids,
            )
            output_png = target_dir / f"{variant_id}.png"
            if overwrite or not output_png.exists():
                crop_candidate_image(assignment.representative).save(output_png)
            variant_entries.append(
                VariantManifestEntry(
                    variant_id=variant_id,
                    source="real_query",
                    source_ref=cluster_id,
                    style="captured",
                )
            )
            variant_ids.add(variant_id)
            generated_variant_count += 1

        downloaded_variants = _download_template_variants(
            template=template,
            target_dir=target_dir,
            existing_variant_ids=variant_ids,
            cache_dir=cache_dir,
            min_variants_per_template=target_variant_count,
            timeout_seconds=timeout_seconds,
            overwrite=overwrite,
            progress_reporter=progress_reporter,
        )
        variant_entries.extend(downloaded_variants)
        variant_ids.update(entry.variant_id for entry in downloaded_variants)
        generated_variant_count += len(downloaded_variants)

        template_variants[template.template_id] = variant_entries
        final_variant_ids[template.template_id] = variant_ids
        if len(variant_entries) < target_variant_count:
            insufficient_templates.append(template.template_id)

    _prune_output_root(
        output_root=output_root,
        expected_template_ids={template.template_id for template in templates},
        expected_variant_ids=final_variant_ids,
    )
    _delete_legacy_manifest_files(manifests_dir)
    _write_materials_manifest(manifests_dir / "materials.yaml")
    _write_group1_templates_manifest(
        manifests_dir / "group1.templates.yaml",
        templates=templates,
        template_variants=template_variants,
    )
    return generated_variant_count, insufficient_templates


def render_template_report(
    *,
    drafts: Sequence[TemplateDraft],
    templates: Sequence[TemplatePlan],
    repo_root: Path,
) -> dict[str, object]:
    template_by_id = {template.template_id: template for template in templates}
    rows: list[dict[str, object]] = []
    for draft in drafts:
        template = template_by_id.get(draft.template_id, fallback_template_plan(draft))
        rows.append(
            {
                "template_id": draft.template_id,
                "zh_name": template.zh_name,
                "family": template.family,
                "tags": list(template.tags),
                "description": template.description,
                "cluster_ids": list(draft.cluster_ids),
                "member_count": draft.member_count,
                "target_variant_count": template.target_variant_count,
                "download_candidates": [
                    {
                        "library": candidate.library,
                        "slug": candidate.slug,
                        "style": candidate.style,
                    }
                    for candidate in template.download_candidates
                ],
                "repo_root": str(repo_root),
            }
        )
    return {
        "template_count": len(rows),
        "templates": rows,
    }


def result_to_json_row(result: QueryImageAuditResult, *, repo_root: Path) -> JsonMapping:
    return {
        "image_path": _display_path(result.image_path, repo_root),
        "status": result.status,
        "error": result.error,
        "request_payload": result.request_payload,
        "template_sequence": [icon.template_id for icon in result.icons],
        "icons": [
            {
                "order": icon.order,
                "template_id": icon.template_id,
                "zh_name": icon.zh_name,
                "family": icon.family,
                "tags": list(icon.tags),
                "description": icon.description,
                "reason": icon.reason,
                "cluster_id": result.cluster_ids[index] if index < len(result.cluster_ids) else None,
            }
            for index, icon in enumerate(result.icons)
        ],
    }


def trace_result_to_json_row(result: QueryImageAuditResult, *, repo_root: Path) -> JsonMapping:
    row = result_to_json_row(result, repo_root=repo_root)
    row["raw_output"] = result.raw_output
    row["response_payload"] = result.response_payload
    return row


def _load_retry_report_rows(path: Path | None, *, repo_root: Path) -> dict[Path, JsonMapping]:
    if path is None:
        return {}
    rows = read_jsonl(path)
    resolved: dict[Path, JsonMapping] = {}
    for row in rows:
        raw_image_path = row.get("image_path")
        if not isinstance(raw_image_path, str) or not raw_image_path.strip():
            continue
        resolved_path = _resolve_report_image_path(raw_image_path, repo_root=repo_root)
        resolved[resolved_path.resolve()] = row
    return resolved


def _reuse_reported_success(
    row: Mapping[str, object] | None,
    *,
    image_path: Path,
    cluster_ids: Sequence[str],
    expected_icon_count: int,
) -> QueryImageAuditResult | None:
    if row is None:
        return None
    if str(row.get("status", "")).strip().lower() != "ok":
        return None
    raw_icons = row.get("icons")
    if not isinstance(raw_icons, list) or len(raw_icons) != expected_icon_count:
        return None
    icons: list[QueryIconDecision] = []
    for index, item in enumerate(raw_icons, start=1):
        if not isinstance(item, dict):
            return None
        icons.append(_normalize_query_icon_decision(item, index=index))
    request_payload = row.get("request_payload")
    return QueryImageAuditResult(
        image_path=image_path,
        status="ok",
        icons=tuple(icons),
        cluster_ids=tuple(cluster_ids),
        request_payload=request_payload if isinstance(request_payload, dict) else None,
    )


def _normalize_query_icon_decision(payload: Mapping[str, object], *, index: int) -> QueryIconDecision:
    raw_order = payload.get("order")
    order = raw_order if isinstance(raw_order, int) and raw_order > 0 else index
    template_id = _normalize_template_id(str(payload.get("template_id", "")).strip())
    if not template_id:
        raise ValueError("ollama icon entry is missing template_id")
    return QueryIconDecision(
        order=order,
        template_id=template_id,
        zh_name=str(payload.get("zh_name", "")).strip() or template_id.removeprefix("tpl_"),
        family=_normalize_token(str(payload.get("family", "")).strip(), fallback="generic"),
        tags=_normalize_tag_values(payload.get("tags")),
        description=str(payload.get("description", "")).strip() or template_id.removeprefix("tpl_"),
        reason=str(payload.get("reason", "")).strip(),
    )


def _normalize_template_plan(payload: Mapping[str, object]) -> TemplatePlan:
    template_id = _normalize_template_id(str(payload.get("template_id", "")).strip())
    if not template_id:
        raise ValueError("ollama template entry is missing template_id")
    raw_candidates = payload.get("download_candidates")
    download_candidates: list[TemplateDownloadCandidate] = []
    if isinstance(raw_candidates, list):
        for item in raw_candidates:
            if not isinstance(item, dict):
                continue
            library = _normalize_library(str(item.get("library", "")).strip())
            slug = _normalize_slug(str(item.get("slug", "")).strip(), library=library)
            if not library or not slug:
                continue
            download_candidates.append(
                TemplateDownloadCandidate(
                    library=library,
                    slug=slug,
                    style=str(item.get("style", "")).strip() or str(DOWNLOAD_LIBRARY_SPECS[library]["style"]),
                )
            )
    return TemplatePlan(
        template_id=template_id,
        zh_name=str(payload.get("zh_name", "")).strip() or template_id.removeprefix("tpl_"),
        family=_normalize_token(str(payload.get("family", "")).strip(), fallback="generic"),
        tags=_normalize_tag_values(payload.get("tags")),
        description=str(payload.get("description", "")).strip() or template_id.removeprefix("tpl_"),
        cluster_ids=tuple(),
        target_variant_count=_normalize_target_variant_count(payload.get("target_variant_count")),
        download_candidates=tuple(download_candidates),
    )


def _normalize_classification_output(
    payload: QueryImageClassification | tuple[QueryIconDecision, ...],
) -> QueryImageClassification:
    if isinstance(payload, QueryImageClassification):
        return payload
    return QueryImageClassification(icons=tuple(payload))


def _normalize_template_id(raw_value: str) -> str:
    normalized = _normalize_token(raw_value, fallback="")
    if not normalized:
        return ""
    if not normalized.startswith("tpl_"):
        normalized = f"tpl_{normalized}"
    return normalized


def _normalize_tag_values(raw_value: object) -> tuple[str, ...]:
    if isinstance(raw_value, str):
        parts = [item for item in re.split(r"[,/]", raw_value) if item.strip()]
        return tuple(_unique_preserve_order(_normalize_token(item.strip(), fallback="") for item in parts if item.strip()))
    if isinstance(raw_value, list):
        tags = [_normalize_token(str(item).strip(), fallback="") for item in raw_value if str(item).strip()]
        return tuple(_unique_preserve_order(tag for tag in tags if tag))
    return tuple()


def _normalize_token(raw_value: str, *, fallback: str) -> str:
    normalized = raw_value.strip().lower()
    if not normalized:
        return fallback
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or fallback


def _normalize_library(raw_value: str) -> str:
    normalized = _normalize_token(raw_value, fallback="")
    if normalized in DOWNLOAD_LIBRARY_ALIASES:
        normalized = DOWNLOAD_LIBRARY_ALIASES[normalized]
    if normalized not in DOWNLOAD_LIBRARY_SPECS:
        return ""
    return normalized


def _normalize_slug(raw_value: str, *, library: str) -> str:
    if not raw_value:
        return ""
    if library == "google_material":
        return _normalize_token(raw_value, fallback="")
    normalized = raw_value.strip().lower().replace("_", "-").replace(" ", "-")
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized


def _normalize_target_variant_count(raw_value: object) -> int:
    if isinstance(raw_value, int):
        return max(3, raw_value)
    if isinstance(raw_value, str) and raw_value.strip().isdigit():
        return max(3, int(raw_value.strip()))
    return DEFAULT_MIN_VARIANTS_PER_TEMPLATE


def _select_majority_template_id(counter: Counter[str]) -> str:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return ordered[0][0]


def _download_template_variants(
    *,
    template: TemplatePlan,
    target_dir: Path,
    existing_variant_ids: set[str],
    cache_dir: Path,
    min_variants_per_template: int,
    timeout_seconds: int,
    overwrite: bool,
    progress_reporter: ProgressReporter | None,
) -> list[VariantManifestEntry]:
    variant_entries: list[VariantManifestEntry] = []
    candidates = merge_download_candidates(
        template.download_candidates,
        build_fallback_download_candidates(template.template_id),
    )
    target_variant_count = min_variants_per_template
    _emit_progress(
        progress_reporter,
        "开始处理模板下载候选",
        {
            "template_id": template.template_id,
            "existing_variant_count": len(existing_variant_ids),
            "target_variant_count": target_variant_count,
            "candidate_count": len(candidates),
        },
    )
    for candidate_index, candidate in enumerate(candidates, start=1):
        if len(existing_variant_ids) + len(variant_entries) >= min_variants_per_template:
            break
        variant_id = _unique_variant_id(
            existing_variant_ids | {entry.variant_id for entry in variant_entries},
            _build_download_variant_id(template_id=template.template_id, candidate=candidate),
        )
        output_png = target_dir / f"{variant_id}.png"
        progress_payload = {
            "template_id": template.template_id,
            "candidate_index": candidate_index,
            "candidate_count": len(candidates),
            "library": candidate.library,
            "slug": candidate.slug,
            "variant_id": variant_id,
            "output_png": str(output_png),
        }
        try:
            if overwrite or not output_png.exists():
                _emit_progress(progress_reporter, "下载候选图标", progress_payload)
                image = _download_icon_image(
                    candidate,
                    cache_dir=cache_dir,
                    timeout_seconds=timeout_seconds,
                    progress_reporter=progress_reporter,
                )
                normalize_icon_png(image).save(output_png)
            else:
                _emit_progress(progress_reporter, "复用已存在候选图标", progress_payload)
            variant_entries.append(
                VariantManifestEntry(
                    variant_id=variant_id,
                    source=candidate.library,
                    source_ref=candidate.slug,
                    style=candidate.style or str(DOWNLOAD_LIBRARY_SPECS[candidate.library]["style"]),
                )
            )
            _emit_progress(progress_reporter, "下载候选图标成功", progress_payload)
        except Exception as exc:
            _emit_progress(
                progress_reporter,
                "下载候选图标失败",
                {**progress_payload, "error": str(exc)},
            )
    _emit_progress(
        progress_reporter,
        "模板下载候选处理完成",
        {
            "template_id": template.template_id,
            "downloaded_variant_count": len(variant_entries),
            "final_variant_count": len(existing_variant_ids) + len(variant_entries),
            "target_variant_count": target_variant_count,
        },
    )
    return variant_entries


def _download_icon_image(
    candidate: TemplateDownloadCandidate,
    *,
    cache_dir: Path,
    timeout_seconds: int,
    progress_reporter: ProgressReporter | None = None,
) -> Any:
    Image, _ = load_pillow()
    spec = DOWNLOAD_LIBRARY_SPECS[candidate.library]
    if spec["kind"] == "google_png":
        slug = candidate.slug.replace("-", "_")
        entry = materials_service._resolve_google_icon_entry(slug, cache_dir)
        url = materials_service.DEFAULT_GOOGLE_ICONS_RAW_URL_PREFIX + entry
        _emit_progress(
            progress_reporter,
            "请求候选图标源",
            {"library": candidate.library, "slug": candidate.slug, "url": url},
        )
        payload = _fetch_binary(url, timeout_seconds=timeout_seconds)
        _emit_progress(
            progress_reporter,
            "候选图标源下载成功",
            {
                "library": candidate.library,
                "slug": candidate.slug,
                "url": url,
                "bytes": len(payload),
            },
        )
        return Image.open(io.BytesIO(payload)).convert("RGBA")

    last_error: Exception | None = None
    for url_template in spec["urls"]:
        url = str(url_template).format(slug=candidate.slug)
        try:
            _emit_progress(
                progress_reporter,
                "请求候选图标源",
                {"library": candidate.library, "slug": candidate.slug, "url": url},
            )
            svg_text = _fetch_text(url, timeout_seconds=timeout_seconds)
            _emit_progress(
                progress_reporter,
                "候选图标源下载成功",
                {
                    "library": candidate.library,
                    "slug": candidate.slug,
                    "url": url,
                    "bytes": len(svg_text.encode("utf-8")),
                },
            )
            return _rasterize_svg(
                svg_text,
                progress_reporter=progress_reporter,
                rasterize_timeout_seconds=min(timeout_seconds, SVG_RASTERIZE_TIMEOUT_SECONDS),
            )
        except Exception as exc:
            last_error = exc
            _emit_progress(
                progress_reporter,
                "候选图标源处理失败",
                {
                    "library": candidate.library,
                    "slug": candidate.slug,
                    "url": url,
                    "error": str(exc),
                },
            )
            continue
    if last_error is None:
        raise RuntimeError(f"unsupported download candidate: {candidate.library}")
    raise last_error


def _rasterize_svg(
    svg_text: str,
    *,
    progress_reporter: ProgressReporter | None = None,
    rasterize_timeout_seconds: int = SVG_RASTERIZE_TIMEOUT_SECONDS,
) -> Any:
    Image, _ = load_pillow()
    prepared_svg = _prepare_svg_markup(svg_text)
    with tempfile.TemporaryDirectory(prefix="sinan-g1-icon-") as temp_dir:
        temp_root = Path(temp_dir)
        svg_path = temp_root / "icon.svg"
        png_path = temp_root / "icon.png"
        svg_path.write_text(prepared_svg, encoding="utf-8")
        commands = [
            ["sips", "-s", "format", "png", str(svg_path), "--out", str(png_path)],
            ["qlmanage", "-t", "-s", "256", "-o", str(temp_root), str(svg_path)],
            ["magick", str(svg_path), str(png_path)],
            ["rsvg-convert", "-w", "256", "-h", "256", "-o", str(png_path), str(svg_path)],
            [
                "inkscape",
                str(svg_path),
                "--export-type=png",
                f"--export-filename={png_path}",
                "--export-width=256",
                "--export-height=256",
            ],
        ]
        for command in commands:
            _emit_progress(
                progress_reporter,
                "尝试光栅化 SVG",
                {"command": command[0], "timeout_seconds": rasterize_timeout_seconds},
            )
            try:
                subprocess.run(
                    command,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=rasterize_timeout_seconds,
                )
            except Exception as exc:
                _emit_progress(
                    progress_reporter,
                    "SVG 光栅化命令失败",
                    {"command": command[0], "error": str(exc)},
                )
                continue
            generated_candidates = [png_path, temp_root / f"{svg_path.name}.png"]
            for generated in generated_candidates:
                if generated.exists():
                    _emit_progress(progress_reporter, "SVG 光栅化成功", {"command": command[0]})
                    return Image.open(generated).convert("RGBA")
    raise RuntimeError("could not rasterize svg with sips, qlmanage, magick, rsvg-convert or inkscape")


def _prepare_svg_markup(svg_text: str) -> str:
    prepared = svg_text.replace("currentColor", "#000000")
    if "xmlns=" not in prepared:
        prepared = prepared.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return prepared


def _build_download_variant_id(*, template_id: str, candidate: TemplateDownloadCandidate) -> str:
    source_token = {
        "google_material": "gmat",
        "heroicons_outline": "hero",
        "heroicons_solid": "heros",
        "tabler_outline": "tabo",
        "tabler_filled": "tabf",
        "bootstrap": "boot",
        "lucide": "luci",
    }.get(candidate.library, _normalize_token(candidate.library, fallback="src")[:4])
    slug_token = _normalize_token(candidate.slug.replace("-", "_"), fallback=template_id.removeprefix("tpl_"))
    style_token = _normalize_token(candidate.style, fallback="style")[:4]
    return _compact_variant_id(f"var_{source_token}_{slug_token}_{style_token}")


def _build_real_variant_id(
    *,
    template_id: str,
    assignment: ClusterAssignment,
    existing_ids: set[str],
) -> str:
    features = assignment.representative.features
    aspect_token = "wide" if features.aspect_ratio >= 1.1 else "tall" if features.aspect_ratio <= 0.9 else "square"
    fill_token = "dense" if features.fill_ratio >= 0.5 else "light"
    symmetry_token = "sym" if features.vertical_symmetry >= 0.75 else "asym"
    preferred = _compact_variant_id(
        f"var_real_{template_id.removeprefix('tpl_')}_{aspect_token}_{fill_token}_{symmetry_token}"
    )
    return _unique_variant_id(existing_ids, preferred, salt=assignment.representative.fingerprint)


def _unique_variant_id(existing_ids: set[str], preferred: str, *, salt: str | None = None) -> str:
    preferred = _compact_variant_id(preferred)
    if preferred not in existing_ids:
        return preferred
    suffix_source = salt or preferred
    for width in (3, 4, 5, 6, 8, 10):
        suffix = _alpha_suffix(suffix_source, width)
        candidate = _append_variant_suffix(preferred, suffix)
        if candidate not in existing_ids:
            return candidate
    for attempt in range(1, 1000):
        digest = hashlib.sha1(f"{suffix_source}:{attempt}".encode("utf-8")).hexdigest()
        candidate = _append_variant_suffix(preferred, _alpha_suffix(digest, 10))
        if candidate not in existing_ids:
            return candidate
    raise RuntimeError(f"could not build unique variant id for {preferred}")


def _append_variant_suffix(preferred: str, suffix: str) -> str:
    normalized_suffix = _normalize_token(suffix, fallback="x")
    if len(normalized_suffix) > MAX_VARIANT_ID_LENGTH - 4:
        normalized_suffix = normalized_suffix[: MAX_VARIANT_ID_LENGTH - 4]
    base_limit = max(1, MAX_VARIANT_ID_LENGTH - len(normalized_suffix) - 1)
    base = preferred[:base_limit].rstrip("_") or "var"
    return f"{base}_{normalized_suffix}"[:MAX_VARIANT_ID_LENGTH].rstrip("_")


def _prune_output_root(
    *,
    output_root: Path,
    expected_template_ids: set[str],
    expected_variant_ids: Mapping[str, set[str]],
) -> None:
    icons_root = output_root / "group1" / "icons"
    if not icons_root.exists():
        return
    for template_dir in icons_root.iterdir():
        if not template_dir.is_dir():
            continue
        if template_dir.name not in expected_template_ids:
            shutil.rmtree(template_dir)
            continue
        keep_ids = expected_variant_ids.get(template_dir.name, set())
        for png_path in template_dir.glob("*.png"):
            if png_path.stem not in keep_ids:
                png_path.unlink()


def _delete_legacy_manifest_files(manifests_dir: Path) -> None:
    for path in (
        manifests_dir / "group1.classes.yaml",
        manifests_dir / "group1.icons.csv",
        manifests_dir / "backgrounds.csv",
    ):
        if path.exists():
            path.unlink()


def _write_materials_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("schema_version: 3\n", encoding="utf-8")


def _write_group1_templates_manifest(
    path: Path,
    *,
    templates: Sequence[TemplatePlan],
    template_variants: Mapping[str, Sequence[VariantManifestEntry]],
) -> None:
    lines = [
        "schema_version: 3",
        "task: group1",
        "mode: instance_matching",
        "",
        "templates:",
    ]
    for template in templates:
        lines.append(f"  - template_id: {template.template_id}")
        lines.append(f"    zh_name: {template.zh_name}")
        lines.append(f"    family: {template.family}")
        lines.append(f"    tags: {_format_inline_list(template.tags)}")
        lines.append("    status: active")
        lines.append("    variants:")
        for variant in template_variants.get(template.template_id, ()):
            lines.append(f"      - variant_id: {variant.variant_id}")
            lines.append(f"        source: {variant.source}")
            lines.append(f"        source_ref: {variant.source_ref}")
            lines.append(f"        style: {variant.style}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_inline_list(values: Sequence[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(values) + "]"


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_ollama_query_prompt() -> str:
    return (
        "你在为 group1 captcha 的新素材库建立模板目录。给你 1 张 query 图片，图片中有 1 到多个小图标，"
        "请按从左到右顺序输出每个图标的语义根模板。\n\n"
        "硬规则：\n"
        "1. template_id 格式必须严格为 tpl_<snake_case>。\n"
        "2. template_id 只表达图标语义根，不要把 outline、filled、white、black、small、number 等风格写进 template_id。\n"
        "3. description 只描述图标本体特征，不描述背景、噪点或边框。\n"
        "4. family 用简短英文类别词，例如 travel / nature / commerce / security / symbol。\n"
        "5. tags 提供 2 到 5 个英文 snake_case 关键词。\n"
        "6. 只输出 JSON，不要输出 markdown 或解释。\n\n"
        "输出格式：\n"
        "{\n"
        '  "icons": [\n'
        "    {\n"
        '      "order": 1,\n'
        '      "template_id": "tpl_shopping_cart",\n'
        '      "zh_name": "购物车",\n'
        '      "family": "commerce",\n'
        '      "tags": ["shopping", "cart", "trolley"],\n'
        '      "description": "线框购物车，前方有篮筐，底部两个轮子",\n'
        '      "reason": "图标主体是购物车而不是篮子"\n'
        "    }\n"
        "  ]\n"
        "}"
    )


def _build_ollama_template_prompt(drafts: Sequence[TemplateDraft]) -> str:
    payload = [
        {
            "template_id": draft.template_id,
            "cluster_ids": list(draft.cluster_ids),
            "member_count": draft.member_count,
            "zh_name_hints": list(draft.zh_name_hints),
            "family_hints": list(draft.family_hints),
            "tag_hints": list(draft.tag_hints),
            "descriptions": list(draft.descriptions),
        }
        for draft in drafts
    ]
    supported_sources = ", ".join(sorted(DOWNLOAD_LIBRARY_SPECS))
    return (
        "你在补完 group1 generator 的实例模板目录。下面是已经按 template_id 聚合好的 query 图标特征。"
        "不要改 template_id，只补全中文名、family、tags、简短 description，"
        "并为每个 template_id 生成一组可自动下载的图标候选。\n\n"
        f"download_candidates 只允许使用这些 library: {supported_sources}。\n"
        "slug 必须使用该图标库常见的英文 slug；对 google_material 用 snake_case，其余库用 kebab-case。\n"
        "target_variant_count 表示这个 template 建议保留的最终变体总数，由你按类别复杂度判断；"
        "简单图标可以少一些，常见且风格分化明显的图标可以多一些，但不得小于 3。\n"
        "优先给出最像 query 图标语义根的通用符号，不要输出风格过度复杂的组合图标。\n"
        "只输出 JSON。\n\n"
        "输入数据：\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "输出格式：\n"
        "{\n"
        '  "templates": [\n'
        "    {\n"
        '      "template_id": "tpl_shopping_cart",\n'
        '      "zh_name": "购物车",\n'
        '      "family": "commerce",\n'
        '      "tags": ["shopping", "cart", "trolley"],\n'
        '      "description": "线框购物车图标",\n'
        '      "target_variant_count": 8,\n'
        '      "download_candidates": [\n'
        '        {"library": "lucide", "slug": "shopping-cart"},\n'
        '        {"library": "tabler_outline", "slug": "shopping-cart"}\n'
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}"
    )


def _emit_progress(
    reporter: ProgressReporter | None,
    title: str,
    payload: JsonMapping | str,
) -> None:
    if reporter is None:
        return
    if isinstance(payload, str):
        rendered_payload = payload
    else:
        rendered_payload = json.dumps(payload, ensure_ascii=False, indent=2)
    reporter(f"[group1-query-audit] {title}\n{rendered_payload}\n")


def _extract_ollama_message_content(response: Mapping[str, object]) -> str:
    message = response.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    content = response.get("response")
    if isinstance(content, str) and content.strip():
        return content
    raise ValueError("ollama response did not contain message.content or response text")


def _post_json(url: str, payload: Mapping[str, object], *, timeout_seconds: int) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ollama request failed with HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"could not reach Ollama at {url}: {exc.reason}") from exc
    try:
        payload_obj = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ollama response was not valid JSON") from exc
    if not isinstance(payload_obj, dict):
        raise RuntimeError("ollama response root must be a JSON object")
    return payload_obj


def _fetch_text(url: str, *, timeout_seconds: int) -> str:
    request = Request(url, headers={"User-Agent": "sinan-captcha/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"download failed with HTTP {exc.code}: {url} {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"could not reach {url}: {exc.reason}") from exc


def _fetch_binary(url: str, *, timeout_seconds: int) -> bytes:
    request = Request(url, headers={"User-Agent": "sinan-captcha/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"download failed with HTTP {exc.code}: {url} {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"could not reach {url}: {exc.reason}") from exc


def _resolve_from_repo(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _default_report_root(base_dir: Path) -> Path:
    return base_dir / "reports" / "group1" / "materials" / strftime("%Y%m%d")


def _resolve_report_root(path: Path | None, base_dir: Path) -> Path:
    if path is None:
        return _default_report_root(base_dir)
    return path if path.is_absolute() else base_dir / path


def _resolve_report_path(path: Path | None, report_root: Path, default_name: str) -> Path:
    if path is None:
        return report_root / default_name
    return path if path.is_absolute() else report_root / path


def _resolve_report_image_path(raw_path: str, *, repo_root: Path) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else repo_root / path


def _display_path(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve()
    try:
        return str(resolved_path.relative_to(repo_root.resolve()))
    except ValueError:
        return str(resolved_path)


def _unique_preserve_order(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _flatten(groups: Sequence[Sequence[str]]) -> list[str]:
    result: list[str] = []
    for group in groups:
        result.extend(group)
    return result


def _compact_variant_id(value: str) -> str:
    normalized = _normalize_token(value, fallback="var")
    if len(normalized) <= MAX_VARIANT_ID_LENGTH:
        return normalized
    parts = [part for part in normalized.split("_") if part]
    if not parts:
        return normalized[:MAX_VARIANT_ID_LENGTH]
    compact_parts: list[str] = []
    remaining = MAX_VARIANT_ID_LENGTH
    for index, part in enumerate(parts):
        reserve = max(0, len(parts) - index - 1)
        max_part_length = max(1, remaining - reserve)
        compact = part[:max_part_length]
        compact_parts.append(compact)
        remaining -= len(compact) + 1
        if remaining <= 0:
            break
    return "_".join(compact_parts)[:MAX_VARIANT_ID_LENGTH].rstrip("_")


def _alpha_suffix(seed: str, width: int) -> str:
    digest = re.sub(r"[^a-f]", "", seed.lower()) or "abcdef"
    chars: list[str] = []
    for index in range(width):
        source_char = digest[index % len(digest)]
        chars.append(chr(ord("a") + (ord(source_char) - ord("a")) % 26))
    return "".join(chars)
