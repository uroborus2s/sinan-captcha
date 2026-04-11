"""CLI for local release and delivery actions."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.release.service import (
    BuildAllReleaseRequest,
    BuildGeneratorRequest,
    BuildReleaseRequest,
    BuildSolverRequest,
    ExportSolverAssetsRequest,
    PackageWindowsRequest,
    PublishReleaseRequest,
    StageSolverAssetsRequest,
    build_all_distributions,
    build_generator_distribution,
    build_distribution,
    build_solver_distribution,
    export_solver_assets,
    package_windows_bundle,
    publish_distribution,
    stage_solver_assets,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build, publish, and package local delivery artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser_cmd = subparsers.add_parser("build", help="Build wheel and sdist into dist/.")
    build_parser_cmd.add_argument("--project-dir", type=Path, default=Path.cwd())

    build_generator_parser_cmd = subparsers.add_parser(
        "build-generator",
        help="Build sinan-generator into packages/generator/dist/<goos>-<goarch>/.",
    )
    build_generator_parser_cmd.add_argument("--project-dir", type=Path, default=Path.cwd())
    build_generator_parser_cmd.add_argument("--goos", default=None)
    build_generator_parser_cmd.add_argument("--goarch", default=None)

    build_solver_parser_cmd = subparsers.add_parser(
        "build-solver",
        help="Build the standalone solver package into packages/solver/dist/.",
    )
    build_solver_parser_cmd.add_argument("--project-dir", type=Path, default=Path.cwd())

    build_all_parser_cmd = subparsers.add_parser(
        "build-all",
        help="Build root CLI, generator CLI, and solver package from the repository root.",
    )
    build_all_parser_cmd.add_argument("--project-dir", type=Path, default=Path.cwd())
    build_all_parser_cmd.add_argument("--goos", default=None)
    build_all_parser_cmd.add_argument("--goarch", default=None)

    publish_parser_cmd = subparsers.add_parser("publish", help="Publish dist/ artifacts to PyPI or TestPyPI.")
    publish_parser_cmd.add_argument("--project-dir", type=Path, default=Path.cwd())
    publish_parser_cmd.add_argument("--repository", choices=("pypi", "testpypi"), default="pypi")
    publish_parser_cmd.add_argument("--token-env", default="PYPI_TOKEN")

    export_parser_cmd = subparsers.add_parser(
        "export-solver-assets",
        help="Export group1/group2 PT checkpoints into sinanz ONNX solver assets.",
    )
    export_parser_cmd.add_argument("--project-dir", type=Path, default=Path.cwd())
    export_parser_cmd.add_argument("--group1-proposal-checkpoint", type=Path, default=None)
    export_parser_cmd.add_argument("--group1-query-checkpoint", type=Path, default=None)
    export_parser_cmd.add_argument("--group1-embedder-checkpoint", type=Path, default=None)
    export_parser_cmd.add_argument("--group1-run", default="")
    export_parser_cmd.add_argument("--group2-checkpoint", type=Path, required=True)
    export_parser_cmd.add_argument("--group2-run", required=True)
    export_parser_cmd.add_argument("--output-dir", type=Path, required=True)
    export_parser_cmd.add_argument("--asset-version", required=True)
    export_parser_cmd.add_argument("--exported-at", default=None)
    export_parser_cmd.add_argument("--source-checkpoint", default=None)
    export_parser_cmd.add_argument("--opset", type=int, default=17)

    stage_assets_parser_cmd = subparsers.add_parser(
        "stage-solver-assets",
        help="Copy exported solver assets into packages/solver/resources/ for packaging.",
    )
    stage_assets_parser_cmd.add_argument("--project-dir", type=Path, default=Path.cwd())
    stage_assets_parser_cmd.add_argument("--asset-dir", type=Path, required=True)

    package_parser_cmd = subparsers.add_parser(
        "package-windows",
        help="Assemble a Windows delivery bundle with the wheel, generator, and optional assets.",
    )
    package_parser_cmd.add_argument("--project-dir", type=Path, default=Path.cwd())
    package_parser_cmd.add_argument("--generator-exe", type=Path, required=True)
    package_parser_cmd.add_argument("--output-dir", type=Path, required=True)
    package_parser_cmd.add_argument("--bundle-dir", type=Path, default=None)
    package_parser_cmd.add_argument("--datasets-dir", type=Path, default=None)
    package_parser_cmd.add_argument("--materials-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            build_distribution(BuildReleaseRequest(project_dir=args.project_dir))
        elif args.command == "build-generator":
            build_generator_distribution(
                BuildGeneratorRequest(
                    project_dir=args.project_dir,
                    goos=args.goos,
                    goarch=args.goarch,
                )
            )
        elif args.command == "build-solver":
            build_solver_distribution(BuildSolverRequest(project_dir=args.project_dir))
        elif args.command == "build-all":
            build_all_distributions(
                BuildAllReleaseRequest(
                    project_dir=args.project_dir,
                    goos=args.goos,
                    goarch=args.goarch,
                )
            )
        elif args.command == "publish":
            publish_distribution(
                PublishReleaseRequest(
                    project_dir=args.project_dir,
                    repository=args.repository,
                    token_env=args.token_env,
                )
            )
        elif args.command == "export-solver-assets":
            export_solver_assets(
                ExportSolverAssetsRequest(
                    project_dir=args.project_dir,
                    group1_proposal_checkpoint=args.group1_proposal_checkpoint,
                    group1_query_checkpoint=args.group1_query_checkpoint,
                    group1_embedder_checkpoint=args.group1_embedder_checkpoint,
                    group1_run=args.group1_run,
                    group2_checkpoint=args.group2_checkpoint,
                    output_dir=args.output_dir,
                    asset_version=args.asset_version,
                    group2_run=args.group2_run,
                    exported_at=args.exported_at,
                    source_checkpoint=args.source_checkpoint,
                    opset=args.opset,
                )
            )
        elif args.command == "stage-solver-assets":
            stage_solver_assets(
                StageSolverAssetsRequest(
                    project_dir=args.project_dir,
                    asset_dir=args.asset_dir,
                )
            )
        elif args.command == "package-windows":
            package_windows_bundle(
                PackageWindowsRequest(
                    project_dir=args.project_dir,
                    generator_exe=args.generator_exe,
                    output_dir=args.output_dir,
                    bundle_dir=args.bundle_dir,
                    datasets_dir=args.datasets_dir,
                    materials_dir=args.materials_dir,
                )
            )
        else:
            parser.error(f"unsupported release command: {args.command}")
    except ValueError as err:
        parser.exit(1, f"{err}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
