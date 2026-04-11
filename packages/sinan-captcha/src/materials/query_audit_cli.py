"""CLI for building group1 template icon packs from query images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import strftime

from common.paths import workspace_paths
from materials.query_audit import (
    DEFAULT_GROUP1_CACHE_DIR,
    DEFAULT_GROUP1_OUTPUT_ROOT,
    DEFAULT_GROUP1_QUERY_DIR,
    DEFAULT_MIN_VARIANTS_PER_TEMPLATE,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_URL,
    run_group1_query_audit,
)


def default_report_root() -> Path:
    return workspace_paths(Path.cwd()).reports_dir / "group1" / "materials" / strftime("%Y%m%d")


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
    parser.add_argument(
        "--retry-from-report",
        type=Path,
        help="Reuse successful rows from a previous group1-query-audit report and only retry failed images.",
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_GROUP1_CACHE_DIR)
    parser.add_argument("--model", required=True, help="Local Ollama multimodal model, such as gemma4:26b")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_OLLAMA_TIMEOUT_SECONDS)
    parser.add_argument("--min-variants-per-template", type=int, default=DEFAULT_MIN_VARIANTS_PER_TEMPLATE)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-image terminal logs.")
    parser.add_argument("--yes", action="store_true", help="Accept default path choices without an interactive prompt.")
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(raw_argv)
    run_root = Path.cwd().resolve()
    if not _confirm_default_paths(args, raw_argv, run_root=run_root):
        parser.exit(2, "已取消执行。\n")
    progress_reporter = None if args.quiet else lambda message: print(message, file=sys.stderr, flush=True)
    result = run_group1_query_audit(
        query_dir=args.query_dir,
        model=args.model,
        output_root=args.output_root,
        report_root=args.report_root,
        output_jsonl=args.output_jsonl,
        trace_jsonl=args.trace_jsonl,
        template_report_json=args.template_report_json,
        retry_from_report=args.retry_from_report,
        cache_dir=args.cache_dir,
        repo_root=run_root,
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


def _confirm_default_paths(args: argparse.Namespace, raw_argv: list[str], *, run_root: Path) -> bool:
    defaulted = _defaulted_path_options(raw_argv)
    if not defaulted or args.yes:
        return True
    resolved_paths = {
        "--query-dir": _resolve_cli_path(args.query_dir, run_root),
        "--output-root": _resolve_cli_path(args.output_root, run_root),
        "--report-root": _resolve_cli_path(args.report_root, run_root),
        "--cache-dir": _resolve_cli_path(args.cache_dir, run_root),
    }
    print("以下路径未显式指定，将按当前仓库的 work_home 默认目录展开：", file=sys.stderr)
    print(f"  current_dir={run_root}", file=sys.stderr)
    for option in defaulted:
        print(f"  {option}={resolved_paths[option]}", file=sys.stderr)
    if not sys.stdin.isatty():
        print("非交互环境请显式传入路径，或添加 --yes 接受默认路径。", file=sys.stderr)
        return False
    answer = input("继续执行？[y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _defaulted_path_options(raw_argv: list[str]) -> list[str]:
    explicit_options = {
        token.split("=", 1)[0]
        for token in raw_argv
        if token.startswith("--")
    }
    path_options = ["--query-dir", "--output-root", "--report-root", "--cache-dir"]
    return [option for option in path_options if option not in explicit_options]


def _resolve_cli_path(path: Path, run_root: Path) -> Path:
    return path if path.is_absolute() else run_root / path


if __name__ == "__main__":
    raise SystemExit(main())
