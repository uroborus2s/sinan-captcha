"""CLI for collecting style-similar background images."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from materials.background_style import (
    DEFAULT_BACKGROUND_OUTPUT_ROOT,
    DEFAULT_BACKGROUND_STYLE_MAX_QUERIES,
    DEFAULT_BACKGROUND_STYLE_PER_QUERY,
    DEFAULT_BACKGROUND_STYLE_SAMPLE_LIMIT,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_URL,
    DEFAULT_PEXELS_API_KEY_ENV,
    run_background_style_collection,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze reference background style with local Ollama and download similar backgrounds."
        )
    )
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_BACKGROUND_OUTPUT_ROOT)
    parser.add_argument(
        "--model",
        required=True,
        help="Local Ollama multimodal model, such as qwen2.5vl:7b",
    )
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_OLLAMA_TIMEOUT_SECONDS)
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=DEFAULT_BACKGROUND_STYLE_SAMPLE_LIMIT,
        help="Maximum number of reference images to analyze. Default: analyze all images.",
    )
    parser.add_argument("--max-queries", type=int, default=DEFAULT_BACKGROUND_STYLE_MAX_QUERIES)
    parser.add_argument("--per-query", type=int, default=DEFAULT_BACKGROUND_STYLE_PER_QUERY)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--orientation", default="landscape")
    parser.add_argument("--min-width", type=int, default=256)
    parser.add_argument("--min-height", type=int, default=128)
    parser.add_argument("--max-hamming-distance", type=int, default=0)
    parser.add_argument("--merge-into", type=Path)
    parser.add_argument("--api-key-env", default=DEFAULT_PEXELS_API_KEY_ENV)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    progress_reporter = (
        None if args.quiet else lambda message: print(message, file=sys.stderr, flush=True)
    )
    result = run_background_style_collection(
        source_dir=args.source_dir,
        output_root=args.output_root,
        model=args.model,
        ollama_url=args.ollama_url,
        timeout_seconds=args.timeout_seconds,
        sample_limit=args.sample_limit,
        max_queries=args.max_queries,
        per_query=args.per_query,
        limit=args.limit,
        orientation=args.orientation,
        min_width=args.min_width,
        min_height=args.min_height,
        max_hamming_distance=args.max_hamming_distance,
        merge_into=args.merge_into,
        api_key_env=args.api_key_env,
        dry_run=args.dry_run,
        progress_reporter=progress_reporter,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
