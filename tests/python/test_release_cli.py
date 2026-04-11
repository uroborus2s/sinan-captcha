from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from release import cli


class ReleaseCliTests(unittest.TestCase):
    def test_dispatches_build_generator(self) -> None:
        with patch("release.cli.build_generator_distribution") as handler:
            code = cli.main(
                [
                    "build-generator",
                    "--project-dir",
                    ".",
                    "--goos",
                    "windows",
                    "--goarch",
                    "amd64",
                ]
            )

        self.assertEqual(code, 0)
        request = handler.call_args.args[0]
        self.assertEqual(request.project_dir, Path("."))
        self.assertEqual(request.goos, "windows")
        self.assertEqual(request.goarch, "amd64")

    def test_dispatches_build_solver(self) -> None:
        with patch("release.cli.build_solver_distribution") as handler:
            code = cli.main(["build-solver", "--project-dir", "."])

        self.assertEqual(code, 0)
        request = handler.call_args.args[0]
        self.assertEqual(request.project_dir, Path("."))

    def test_dispatches_build_all(self) -> None:
        with patch("release.cli.build_all_distributions") as handler:
            code = cli.main(
                [
                    "build-all",
                    "--project-dir",
                    ".",
                    "--goos",
                    "windows",
                    "--goarch",
                    "amd64",
                ]
            )

        self.assertEqual(code, 0)
        request = handler.call_args.args[0]
        self.assertEqual(request.project_dir, Path("."))
        self.assertEqual(request.goos, "windows")
        self.assertEqual(request.goarch, "amd64")

    def test_dispatches_export_solver_assets(self) -> None:
        with patch("release.cli.export_solver_assets") as handler:
            code = cli.main(
                [
                    "export-solver-assets",
                    "--project-dir",
                    ".",
                    "--group1-proposal-checkpoint",
                    "runs/group1/firstpass/proposal-detector/weights/best.pt",
                    "--group1-query-checkpoint",
                    "runs/group1/firstpass/query-parser/weights/best.pt",
                    "--group1-embedder-checkpoint",
                    "runs/group1/firstpass/icon-embedder/weights/best.pt",
                    "--group1-run",
                    "firstpass",
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
        self.assertEqual(
            request.group1_proposal_checkpoint,
            Path("runs/group1/firstpass/proposal-detector/weights/best.pt"),
        )
        self.assertEqual(
            request.group1_query_checkpoint,
            Path("runs/group1/firstpass/query-parser/weights/best.pt"),
        )
        self.assertEqual(
            request.group1_embedder_checkpoint,
            Path("runs/group1/firstpass/icon-embedder/weights/best.pt"),
        )
        self.assertEqual(request.group1_run, "firstpass")
        self.assertEqual(request.group2_checkpoint, Path("runs/group2/firstpass/weights/best.pt"))
        self.assertEqual(request.group2_run, "firstpass")
        self.assertEqual(request.output_dir, Path("dist/solver-assets/20260405"))
        self.assertEqual(request.asset_version, "20260405")

    def test_dispatches_stage_solver_assets(self) -> None:
        with patch("release.cli.stage_solver_assets") as handler:
            code = cli.main(
                [
                    "stage-solver-assets",
                    "--project-dir",
                    ".",
                    "--asset-dir",
                    "work_home/materials/solver/group2/exported",
                ]
            )

        self.assertEqual(code, 0)
        request = handler.call_args.args[0]
        self.assertEqual(request.project_dir, Path("."))
        self.assertEqual(request.asset_dir, Path("work_home/materials/solver/group2/exported"))


if __name__ == "__main__":
    unittest.main()
