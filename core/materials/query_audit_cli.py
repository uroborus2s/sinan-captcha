"""CLI for auditing group1 query images with a local Ollama model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from core.materials.query_audit import (
    DEFAULT_GROUP1_AUDIT_REPORT,
    DEFAULT_GROUP1_AUDIT_TRACE,
    DEFAULT_GROUP1_BACKLOG_DOC,
    DEFAULT_GROUP1_MANIFEST,
    DEFAULT_GROUP1_QUERY_DIR,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_URL,
    require_repo_root,
    run_group1_query_audit,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit group1 query images with a local Ollama multimodal model."
    )
    parser.add_argument("--query-dir", type=Path, default=DEFAULT_GROUP1_QUERY_DIR)
    parser.add_argument("--model", required=True, help="Local Ollama multimodal model, such as qwen2.5vl:7b")
    parser.add_argument("--backlog-doc", type=Path, default=DEFAULT_GROUP1_BACKLOG_DOC)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_GROUP1_MANIFEST)
    parser.add_argument("--output-jsonl", type=Path, default=DEFAULT_GROUP1_AUDIT_REPORT)
    parser.add_argument("--trace-jsonl", type=Path, default=DEFAULT_GROUP1_AUDIT_TRACE)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_OLLAMA_TIMEOUT_SECONDS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
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
        backlog_doc=args.backlog_doc,
        manifest_path=args.manifest,
        output_jsonl=args.output_jsonl,
        trace_jsonl=args.trace_jsonl,
        repo_root=repo_root,
        ollama_url=args.ollama_url,
        timeout_seconds=args.timeout_seconds,
        limit=args.limit,
        dry_run=args.dry_run,
        progress_reporter=progress_reporter,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
