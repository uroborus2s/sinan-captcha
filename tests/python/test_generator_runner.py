from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.generator.runner import GeneratorCommand


class GeneratorRunnerTests(unittest.TestCase):
    def test_builds_generate_args(self) -> None:
        command = GeneratorCommand(
            binary=Path("tools/sinan-click-generator.exe"),
            command="generate",
            config=Path("generator/configs/default.yaml"),
            materials_root=Path("materials"),
            output_root=Path("datasets/group1/raw"),
        )
        args = command.as_args()
        self.assertEqual(args[1], "generate")
        self.assertIn("--output-root", args)

    def test_builds_qa_args(self) -> None:
        command = GeneratorCommand(
            binary=Path("tools/sinan-click-generator.exe"),
            command="qa",
            config=Path("generator/configs/default.yaml"),
            materials_root=Path("materials"),
            batch_dir=Path("generator/output/group1/batch_0001"),
        )
        args = command.as_args()
        self.assertIn("--batch-dir", args)


if __name__ == "__main__":
    unittest.main()
