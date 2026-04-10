"""Audit group1 query images with a local Ollama vision model."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.auto_train.json_extract import extract_json_object
from core.common.jsonl import JsonMapping, write_jsonl

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
DEFAULT_GROUP1_QUERY_DIR = Path("materials/test/group1/query")
DEFAULT_GROUP1_MANIFEST = Path("materials/incoming/group1_icon_pack/manifests/group1.classes.yaml")
DEFAULT_GROUP1_BACKLOG_DOC = Path("docs/02-user-guide/group1-material-category-backlog.md")
DEFAULT_GROUP1_AUDIT_REPORT = Path("reports/materials/group1-query-audit.jsonl")
DEFAULT_GROUP1_AUDIT_TRACE = Path("reports/materials/group1-query-audit-trace.jsonl")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120
AUTO_SECTION_HEADER = "## 3.2 自动审计图片与分类映射（脚本生成）"
AUTO_SECTION_INTRO = (
    "这一区由 `uv run sinan materials audit-group1-query ...` 自动更新。"
    "人工结论仍以第 3 节手工维护内容为准。"
)
AUTO_SECTION_START = "<!-- AUTO-GENERATED:GROUP1-QUERY-AUDIT:START -->"
AUTO_SECTION_END = "<!-- AUTO-GENERATED:GROUP1-QUERY-AUDIT:END -->"


@dataclass(frozen=True)
class QueryIconDecision:
    order: int
    decision: str
    category_name: str
    category_zh_name: str
    description: str
    reason: str


@dataclass(frozen=True)
class QueryImageAuditResult:
    image_path: Path
    status: str
    icons: tuple[QueryIconDecision, ...]
    error: str | None = None
    request_payload: JsonMapping | None = None
    raw_output: str | None = None
    response_payload: JsonMapping | None = None


@dataclass(frozen=True)
class NewCategoryProposal:
    category_name: str
    category_zh_name: str
    description: str
    example_image: Path


@dataclass(frozen=True)
class QueryImageClassification:
    icons: tuple[QueryIconDecision, ...]
    request_payload: JsonMapping | None = None
    raw_output: str | None = None
    response_payload: JsonMapping | None = None


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


Classifier = Callable[
    [Path, Mapping[str, str]],
    QueryImageClassification | tuple[QueryIconDecision, ...],
]
ProgressReporter = Callable[[str], None]


class OllamaQueryImageClassifier:
    """Use a local Ollama multimodal model to classify query icons."""

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
        image_path: Path,
        known_categories: Mapping[str, str],
    ) -> QueryImageClassification:
        prompt = _build_ollama_prompt(known_categories)
        image_bytes = image_path.read_bytes()
        request_payload = {
            "model": self._model,
            "ollama_url": self._ollama_url,
            "timeout_seconds": self._timeout_seconds,
            "image_path": str(image_path),
            "image_size_bytes": len(image_bytes),
            "known_category_count": len(known_categories),
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
        _emit_progress(
            self._progress_reporter,
            "发送到大模型的请求",
            request_payload,
        )
        raw_response = _post_json(
            f"{self._ollama_url}/api/chat",
            payload,
            timeout_seconds=self._timeout_seconds,
        )
        content = _extract_ollama_message_content(raw_response)
        _emit_progress(self._progress_reporter, "大模型原始响应", content)
        try:
            icons = parse_ollama_icon_response(content, known_categories)
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


def run_group1_query_audit(
    *,
    query_dir: Path,
    model: str,
    backlog_doc: Path = DEFAULT_GROUP1_BACKLOG_DOC,
    manifest_path: Path = DEFAULT_GROUP1_MANIFEST,
    output_jsonl: Path = DEFAULT_GROUP1_AUDIT_REPORT,
    trace_jsonl: Path = DEFAULT_GROUP1_AUDIT_TRACE,
    repo_root: Path,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    limit: int | None = None,
    dry_run: bool = False,
    classifier: Classifier | None = None,
    progress_reporter: ProgressReporter | None = None,
) -> dict[str, object]:
    resolved_repo_root = repo_root.resolve()
    resolved_query_dir = _resolve_from_repo(query_dir, resolved_repo_root).resolve()
    resolved_backlog_doc = _resolve_from_repo(backlog_doc, resolved_repo_root)
    resolved_manifest = _resolve_from_repo(manifest_path, resolved_repo_root)
    resolved_output_jsonl = _resolve_from_repo(output_jsonl, resolved_repo_root)
    resolved_trace_jsonl = _resolve_from_repo(trace_jsonl, resolved_repo_root)
    known_categories = load_group1_material_classes(resolved_manifest)
    image_paths = list_query_images(resolved_query_dir)
    if limit is not None:
        image_paths = image_paths[:limit]

    image_classifier = classifier or OllamaQueryImageClassifier(
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
        progress_reporter=progress_reporter,
    )
    _emit_progress(
        progress_reporter,
        "开始执行 group1 query 审计",
        {
            "query_dir": str(resolved_query_dir),
            "model": model,
            "image_count": len(image_paths),
            "dry_run": dry_run,
            "output_jsonl": str(resolved_output_jsonl),
            "trace_jsonl": str(resolved_trace_jsonl),
        },
    )

    results: list[QueryImageAuditResult] = []
    proposals: dict[str, NewCategoryProposal] = {}
    for index, image_path in enumerate(image_paths, start=1):
        display_path = _display_path(image_path, resolved_repo_root)
        _emit_progress(
            progress_reporter,
            f"正在处理图片 {index}/{len(image_paths)}",
            {"image_path": display_path},
        )
        try:
            classification = _normalize_classification_output(image_classifier(image_path, known_categories))
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
            results.append(result)
            _emit_progress(
                progress_reporter,
                f"图片处理失败 {index}/{len(image_paths)}",
                trace_result_to_json_row(result, repo_root=resolved_repo_root),
            )
            continue
        except Exception as exc:
            result = QueryImageAuditResult(
                image_path=image_path,
                status="error",
                icons=(),
                error=str(exc),
            )
            results.append(result)
            _emit_progress(
                progress_reporter,
                f"图片处理失败 {index}/{len(image_paths)}",
                trace_result_to_json_row(result, repo_root=resolved_repo_root),
            )
            continue
        result = QueryImageAuditResult(
            image_path=image_path,
            status="ok",
            icons=classification.icons,
            request_payload=classification.request_payload,
            raw_output=classification.raw_output,
            response_payload=classification.response_payload,
        )
        results.append(result)
        _emit_progress(
            progress_reporter,
            f"图片处理完成 {index}/{len(image_paths)}",
            trace_result_to_json_row(result, repo_root=resolved_repo_root),
        )
        for icon in classification.icons:
            if icon.category_name in known_categories:
                continue
            if icon.category_name in proposals:
                continue
            proposals[icon.category_name] = NewCategoryProposal(
                category_name=icon.category_name,
                category_zh_name=icon.category_zh_name or "待确认",
                description=icon.description or "待人工补充图形描述",
                example_image=image_path,
            )

    output_rows = [result_to_json_row(result, repo_root=resolved_repo_root) for result in results]
    trace_rows = [trace_result_to_json_row(result, repo_root=resolved_repo_root) for result in results]
    if not dry_run:
        write_jsonl(resolved_output_jsonl, output_rows)
        write_jsonl(resolved_trace_jsonl, trace_rows)
        update_group1_backlog_doc(
            resolved_backlog_doc,
            results=results,
            proposals=tuple(proposals.values()),
            repo_root=resolved_repo_root,
        )

    error_count = sum(1 for result in results if result.status == "error")
    summary = {
        "query_dir": str(resolved_query_dir),
        "image_count": len(image_paths),
        "processed_count": len(results),
        "error_count": error_count,
        "new_category_count": len(proposals),
        "new_categories": [proposal.category_name for proposal in proposals.values()],
        "output_jsonl": str(resolved_output_jsonl),
        "trace_jsonl": str(resolved_trace_jsonl),
        "backlog_doc": str(resolved_backlog_doc),
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


def load_group1_material_classes(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"group1 manifest does not exist: {path}")
    categories: dict[str, str] = {}
    current_name: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            current_name = stripped.split(":", 1)[1].strip()
            continue
        if stripped.startswith("zh_name:"):
            if current_name is None:
                raise ValueError(f"invalid group1 manifest row without name before zh_name: {path}")
            zh_name = stripped.split(":", 1)[1].strip()
            categories[current_name] = zh_name
            current_name = None
    if not categories:
        raise ValueError(f"no categories found in group1 manifest: {path}")
    return categories


def parse_ollama_icon_response(
    raw_output: str,
    known_categories: Mapping[str, str],
) -> tuple[QueryIconDecision, ...]:
    payload = extract_json_object(raw_output, required_keys={"icons"})
    raw_icons = payload.get("icons")
    if not isinstance(raw_icons, list):
        raise ValueError("ollama response field 'icons' must be a list")
    normalized_icons: list[QueryIconDecision] = []
    for index, item in enumerate(raw_icons, start=1):
        if not isinstance(item, dict):
            raise ValueError("ollama response contains a non-object icon entry")
        normalized_icons.append(_normalize_icon_decision(item, index=index, known_categories=known_categories))
    normalized_icons.sort(key=lambda icon: icon.order)
    return tuple(normalized_icons)


def result_to_json_row(result: QueryImageAuditResult, *, repo_root: Path) -> JsonMapping:
    sequence = [icon.category_name for icon in result.icons]
    return {
        "image_path": _display_path(result.image_path, repo_root),
        "status": result.status,
        "error": result.error,
        "request_payload": result.request_payload,
        "category_sequence": sequence,
        "new_categories": [icon.category_name for icon in result.icons if icon.decision == "new_candidate"],
        "icons": [
            {
                "order": icon.order,
                "decision": icon.decision,
                "category_name": icon.category_name,
                "category_zh_name": icon.category_zh_name,
                "description": icon.description,
                "reason": icon.reason,
            }
            for icon in result.icons
        ],
    }


def trace_result_to_json_row(result: QueryImageAuditResult, *, repo_root: Path) -> JsonMapping:
    row = result_to_json_row(result, repo_root=repo_root)
    row["raw_output"] = result.raw_output
    row["response_payload"] = result.response_payload
    return row


def update_group1_backlog_doc(
    backlog_doc: Path,
    *,
    results: tuple[QueryImageAuditResult, ...] | list[QueryImageAuditResult],
    proposals: tuple[NewCategoryProposal, ...] | list[NewCategoryProposal],
    repo_root: Path,
) -> None:
    if not backlog_doc.exists():
        raise FileNotFoundError(f"backlog document does not exist: {backlog_doc}")
    original = backlog_doc.read_text(encoding="utf-8")
    updated = _append_new_category_rows(original, proposals=proposals, repo_root=repo_root)
    updated = _upsert_mapping_section(updated, results=results, repo_root=repo_root)
    if updated != original:
        backlog_doc.write_text(updated, encoding="utf-8")


def _append_new_category_rows(
    markdown: str,
    *,
    proposals: tuple[NewCategoryProposal, ...] | list[NewCategoryProposal],
    repo_root: Path,
) -> str:
    if not proposals:
        return markdown
    existing_names = set(re.findall(r"`(icon_[a-z0-9_]+)`", markdown))
    pending_section_marker = "\n## 3.1 已确认可直接归到现有素材类的案例\n"
    insert_at = markdown.find(pending_section_marker)
    if insert_at == -1:
        raise ValueError("could not find section '## 3.1 已确认可直接归到现有素材类的案例'")

    new_lines: list[str] = []
    for proposal in proposals:
        if proposal.category_name in existing_names:
            continue
        example_image = _display_path(proposal.example_image, repo_root)
        new_lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_code(proposal.category_name),
                    _escape_table_cell(proposal.category_zh_name or "待确认"),
                    _escape_table_cell(proposal.description or "待人工补充图形描述"),
                    "待人工确认",
                    "已有截图",
                    _escape_table_cell(f"自动审计发现；示例图片：{example_image}"),
                ]
            )
            + " |"
        )
        existing_names.add(proposal.category_name)
    if not new_lines:
        return markdown

    prefix = markdown[:insert_at].rstrip("\n")
    suffix = markdown[insert_at:]
    return f"{prefix}\n" + "\n".join(new_lines) + f"\n\n{suffix.lstrip('\n')}"


def _upsert_mapping_section(
    markdown: str,
    *,
    results: tuple[QueryImageAuditResult, ...] | list[QueryImageAuditResult],
    repo_root: Path,
) -> str:
    generated_block = _render_mapping_section(results=results, repo_root=repo_root)
    if AUTO_SECTION_START in markdown and AUTO_SECTION_END in markdown:
        pattern = re.compile(
            re.escape(AUTO_SECTION_START) + r".*?" + re.escape(AUTO_SECTION_END),
            flags=re.DOTALL,
        )
        return pattern.sub(generated_block, markdown, count=1)

    anchor = "\n## 4. 类别判定边界\n"
    insert_at = markdown.find(anchor)
    if insert_at == -1:
        raise ValueError("could not find section '## 4. 类别判定边界'")
    prefix = markdown[:insert_at].rstrip("\n")
    suffix = markdown[insert_at:]
    section = "\n\n".join([AUTO_SECTION_HEADER, AUTO_SECTION_INTRO, generated_block])
    return f"{prefix}\n\n{section}\n\n{suffix.lstrip('\n')}"


def _render_mapping_section(
    *,
    results: tuple[QueryImageAuditResult, ...] | list[QueryImageAuditResult],
    repo_root: Path,
) -> str:
    lines = [
        AUTO_SECTION_START,
        f"已扫描 `{len(results)}` 张 query 图片。",
        "",
        "| 图片文件 | 左到右类别序列 | 新类别候选 | 状态 / 备注 |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        image_path = _markdown_code(_display_path(result.image_path, repo_root))
        sequence = "；".join(
            f"{icon.order}:{_markdown_code(icon.category_name)}" for icon in result.icons
        ) or "无"
        new_candidates = "，".join(
            _markdown_code(icon.category_name)
            for icon in result.icons
            if icon.decision == "new_candidate"
        ) or "无"
        note = result.error or result.status
        lines.append(
            "| "
            + " | ".join(
                [
                    image_path,
                    _escape_table_cell(sequence),
                    _escape_table_cell(new_candidates),
                    _escape_table_cell(note),
                ]
            )
            + " |"
        )
    lines.append(AUTO_SECTION_END)
    return "\n".join(lines)


def _normalize_icon_decision(
    payload: Mapping[str, object],
    *,
    index: int,
    known_categories: Mapping[str, str],
) -> QueryIconDecision:
    raw_order = payload.get("order")
    order = raw_order if isinstance(raw_order, int) and raw_order > 0 else index

    raw_name = str(payload.get("category_name", "")).strip()
    category_name = _normalize_category_name(raw_name)
    if not category_name:
        raise ValueError("ollama icon entry is missing category_name")

    decision = _normalize_decision(str(payload.get("decision", "existing")))
    if category_name in known_categories:
        decision = "existing"
        category_zh_name = known_categories[category_name]
    else:
        decision = "new_candidate"
        category_zh_name = str(payload.get("category_zh_name", "")).strip() or "待确认"

    return QueryIconDecision(
        order=order,
        decision=decision,
        category_name=category_name,
        category_zh_name=category_zh_name,
        description=str(payload.get("description", "")).strip(),
        reason=str(payload.get("reason", "")).strip(),
    )


def _normalize_classification_output(
    payload: QueryImageClassification | tuple[QueryIconDecision, ...],
) -> QueryImageClassification:
    if isinstance(payload, QueryImageClassification):
        return payload
    return QueryImageClassification(icons=tuple(payload))


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


def _normalize_category_name(raw_name: str) -> str:
    normalized = raw_name.strip().lower()
    if not normalized:
        return ""
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized.startswith("icon_"):
        normalized = f"icon_{normalized}"
    return normalized


def _normalize_decision(raw_decision: str) -> str:
    normalized = raw_decision.strip().lower()
    if normalized in {"new", "new_category", "new-candidate", "newcandidate", "candidate"}:
        return "new_candidate"
    return "existing"


def _build_ollama_prompt(known_categories: Mapping[str, str]) -> str:
    category_lines = "\n".join(f"- {name}: {zh_name}" for name, zh_name in known_categories.items())
    return (
        "你在审查 group1 captcha 的 query 图片。图片里会出现 1 到多个小图标，"
        "请按从左到右顺序识别它们。\n\n"
        "规则：\n"
        "1. 如果图标能精确归到下方现有素材类，就把 decision 设为 existing，"
        "并且 category_name 必须严格使用现有类名。\n"
        "2. 如果图标无法精确归到现有素材类，就把 decision 设为 new_candidate，"
        "并给出新的 icon_<english_name> 类名、中文名和一句图形描述。\n"
        "3. 只输出 JSON，不要输出 markdown 或解释文字。\n\n"
        "现有素材类：\n"
        f"{category_lines}\n\n"
        "输出格式：\n"
        "{\n"
        '  "icons": [\n'
        "    {\n"
        '      "order": 1,\n'
        '      "decision": "existing",\n'
        '      "category_name": "icon_plane",\n'
        '      "category_zh_name": "飞机",\n'
        '      "description": "飞机轮廓图标",\n'
        '      "reason": "与现有 airplane 类一致"\n'
        "    }\n"
        "  ]\n"
        "}"
    )


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


def _resolve_from_repo(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def require_repo_root(start: Path) -> Path:
    resolved_start = start.resolve()
    if (resolved_start / "pyproject.toml").exists() and (resolved_start / "core").is_dir():
        return resolved_start
    raise FileNotFoundError(
        "请到仓库根目录执行该命令；当前目录缺少 pyproject.toml 和 core/。"
        f" current_dir={resolved_start}"
    )


def _display_path(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve()
    try:
        return str(resolved_path.relative_to(repo_root.resolve()))
    except ValueError:
        return str(resolved_path)


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _markdown_code(value: str) -> str:
    return f"`{value}`"
