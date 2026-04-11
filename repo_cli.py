"""Console-script entrypoint for root-level repository commands."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_repo_script():
    script_path = Path(__file__).resolve().parent / "scripts" / "repo.py"
    spec = importlib.util.spec_from_file_location("repo_script_entry", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load repo script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    module = _load_repo_script()
    return int(module.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
