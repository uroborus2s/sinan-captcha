from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from core.release import cli


class ReleaseCliTests(unittest.TestCase):
    def test_dispatches_export_solver_assets(self) -> None:
        with patch("core.release.cli.export_group2_solver_assets") as handler:
            code = cli.main(
                [
                    "export-solver-assets",
                    "--project-dir",
                    ".",
                    "--group2-checkpoint",
                    "runs/group2/firstpass/weights/best.pt",
                    "--group2-run",
                    "firstpass",
                    "--output-dir",
                    "dist/solver-assets/20260405",
                    "--asset-version",
                    "20260405",
                ]
            )

        self.assertEqual(code, 0)
        request = handler.call_args.args[0]
        self.assertEqual(request.project_dir, Path("."))
        self.assertEqual(request.group2_checkpoint, Path("runs/group2/firstpass/weights/best.pt"))
        self.assertEqual(request.group2_run, "firstpass")
        self.assertEqual(request.output_dir, Path("dist/solver-assets/20260405"))
        self.assertEqual(request.asset_version, "20260405")


if __name__ == "__main__":
    unittest.main()
