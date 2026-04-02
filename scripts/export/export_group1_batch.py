"""Thin entry script for future group1 export flows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.generator.runner import GeneratorCommand, run_generator


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke the Go generator to export a group1 batch.")
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--materials-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    result = run_generator(
        GeneratorCommand(
            binary=args.binary,
            command="generate",
            config=args.config,
            materials_root=args.materials_root,
            mode="click",
            backend="native",
            output_root=args.output_root,
        )
    )
    if result.stdout:
        print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
