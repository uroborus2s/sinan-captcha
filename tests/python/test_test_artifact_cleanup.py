from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


def _load_cleanup_module():
    module_path = Path(__file__).resolve().parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("test_cleanup_conftest", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load cleanup module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CleanupGeneratedTestArtifactsTests(unittest.TestCase):
    def test_cleanup_generated_test_artifacts_removes_common_python_tooling_outputs(self) -> None:
        cleanup_module = _load_cleanup_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            targets = [
                repo_root / ".pytest_cache" / "state",
                repo_root / ".ruff_cache" / "cache",
                repo_root / ".mypy_cache" / "cache",
                repo_root / "htmlcov" / "index.html",
                repo_root / ".coverage",
                repo_root / "packages" / "sinan-captcha" / "build" / "marker.txt",
                repo_root / "packages" / "sinan-captcha" / "src" / "sinan_captcha.egg-info" / "PKG-INFO",
                repo_root / "packages" / "solver" / "solver.egg-info" / "PKG-INFO",
                repo_root / "packages" / "sinan-captcha" / "src" / "auto_train" / "__pycache__" / "x.pyc",
            ]
            for target in targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("artifact", encoding="utf-8")

            original_root = cleanup_module.REPO_ROOT
            cleanup_module.REPO_ROOT = repo_root
            try:
                cleanup_module.cleanup_generated_test_artifacts()
            finally:
                cleanup_module.REPO_ROOT = original_root

            for target in (
                repo_root / ".pytest_cache",
                repo_root / ".ruff_cache",
                repo_root / ".mypy_cache",
                repo_root / "htmlcov",
                repo_root / ".coverage",
                repo_root / "packages" / "sinan-captcha" / "build",
                repo_root / "packages" / "sinan-captcha" / "src" / "sinan_captcha.egg-info",
                repo_root / "packages" / "solver" / "solver.egg-info",
                repo_root / "packages" / "sinan-captcha" / "src" / "auto_train" / "__pycache__",
            ):
                self.assertFalse(target.exists(), f"expected cleanup to remove {target}")


if __name__ == "__main__":
    unittest.main()
