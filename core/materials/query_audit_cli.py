"""CLI for building group1 template icon packs from query images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import strftime

from core.materials.query_audit import (
    DEFAULT_GROUP1_CACHE_DIR,
    DEFAULT_GROUP1_OUTPUT_ROOT,
    DEFAULT_GROUP1_QUERY_DIR,
    DEFAULT_MIN_VARIANTS_PER_TEMPLATE,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_URL,
    require_repo_root,
    run_group1_query_audit,
)


def default_report_root() -> Path:
    return Path.cwd() / "reports" / "group1" / "materials" / strftime("%Y%m%d")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze group1 validation query images with local Ollama and build a tpl_/var_ icon pack."
    )
    parser.add_argument("--query-dir", type=Path, default=DEFAULT_GROUP1_QUERY_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_GROUP1_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=default_report_root())
    parser.add_argument("--output-jsonl", type=Path)
    parser.add_argument("--trace-jsonl", type=Path)
    parser.add_argument("--template-report-json", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_GROUP1_CACHE_DIR)
    parser.add_argument("--model", required=True, help="Local Ollama multimodal model, such as gemma4:26b")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_OLLAMA_TIMEOUT_SECONDS)
    parser.add_argument("--min-variants-per-template", type=int, default=DEFAULT_MIN_VARIANTS_PER_TEMPLATE)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-image terminal logs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        repo_root = require_repo_root(Path.cwd())
    except FileNotFoundError as exc:
        parser.exit(2, f"{exc}\n")
    progress_reporter = None if args.quiet else lambda message: print(message, file=sys.stderr, flush=True)
    result = run_group1_query_audit(
        query_dir=args.query_dir,
        model=args.model,
        output_root=args.output_root,
        report_root=args.report_root,
        output_jsonl=args.output_jsonl,
        trace_jsonl=args.trace_jsonl,
        template_report_json=args.template_report_json,
        cache_dir=args.cache_dir,
        repo_root=repo_root,
        ollama_url=args.ollama_url,
        timeout_seconds=args.timeout_seconds,
        min_variants_per_template=args.min_variants_per_template,
        limit=args.limit,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        progress_reporter=progress_reporter,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
