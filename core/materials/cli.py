"""CLI for building local offline materials packs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.materials.service import build_offline_pack, load_materials_pack_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a local offline materials pack.")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/materials"))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    spec = load_materials_pack_spec(args.spec)
    result = build_offline_pack(spec, output_root=args.output_root, cache_dir=args.cache_dir)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
