from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


class NativeProjectLayoutTest(unittest.TestCase):
    def test_workspace_and_crate_metadata_are_aligned(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        workspace = tomllib.loads((project_root / "Cargo.toml").read_text(encoding="utf-8"))
        crate = tomllib.loads(
            (project_root / "native" / "sinanz_ext" / "Cargo.toml").read_text(encoding="utf-8")
        )
        pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(workspace["workspace"]["members"], ["native/sinanz_ext"])
        self.assertEqual(workspace["workspace"]["resolver"], "2")
        self.assertEqual(workspace["workspace"]["metadata"]["sinanz"]["native_module"], "sinanz_ext")
        self.assertEqual(
            workspace["workspace"]["metadata"]["sinanz"]["bridge_module"],
            "sinanz.native_bridge",
        )
        self.assertEqual(crate["lib"]["crate-type"], ["cdylib", "rlib"])
        self.assertEqual(sorted(crate["features"]), ["default", "onnx-runtime", "python-extension"])
        self.assertEqual(crate["package"]["name"], "sinanz_ext")
        self.assertEqual(crate["package"]["publish"], False)
        self.assertEqual(crate["package"]["metadata"]["sinanz"]["stage"], "group2-onnx-bridge")
        self.assertEqual(pyproject["tool"]["sinanz"]["native_extension_module"], "sinanz_ext")
        self.assertEqual(pyproject["tool"]["sinanz"]["native_bridge_module"], "sinanz.native_bridge")


if __name__ == "__main__":
    unittest.main()
