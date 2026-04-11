"""CLI for the unified local solver service and bundle management."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common.paths import default_work_root
from solve.bundle import SolverBundleError, build_solver_bundle, load_solver_bundle
from solve.contracts import (
    SolveContractError,
    SolveRequest,
    create_error_response,
    load_request_payload,
    write_solve_response,
)
from solve.service import UnifiedSolverService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build, validate, and run the unified local solver bundle.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser_ = subparsers.add_parser("build-bundle", help="copy trained models into a self-contained solver bundle")
    build_parser_.add_argument("--bundle-dir", type=Path, required=True)
    build_parser_.add_argument("--group1-run", required=True)
    build_parser_.add_argument("--group2-run", required=True)
    build_parser_.add_argument("--train-root", type=Path, default=None)
    build_parser_.add_argument("--bundle-version", default=None)
    build_parser_.add_argument("--force", action="store_true")

    validate_parser = subparsers.add_parser("validate-bundle", help="validate a solver bundle manifest and files")
    validate_parser.add_argument("--bundle-dir", type=Path, required=True)

    run_parser = subparsers.add_parser("run", help="solve one request with a validated solver bundle")
    run_parser.add_argument("--bundle-dir", type=Path, required=True)
    run_parser.add_argument("--request", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build-bundle":
        return _build_bundle(args, parser)
    if args.command == "validate-bundle":
        return _validate_bundle(args, parser)
    if args.command == "run":
        return _run_request(args, parser)
    parser.error(f"unsupported command: {args.command}")
    return 1


def _build_bundle(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    train_root = args.train_root or default_work_root(Path.cwd())
    try:
        bundle = build_solver_bundle(
            bundle_dir=args.bundle_dir,
            train_root=train_root,
            group1_run=str(args.group1_run),
            group2_run=str(args.group2_run),
            bundle_version=args.bundle_version,
            force=bool(args.force),
        )
    except SolverBundleError as err:
        parser.exit(1, f"{err}\n")
    print(json.dumps(bundle.summary(), ensure_ascii=False, indent=2))
    return 0


def _validate_bundle(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        bundle = load_solver_bundle(args.bundle_dir)
    except SolverBundleError as err:
        parser.exit(1, f"{err}\n")
    print(json.dumps(bundle.summary(), ensure_ascii=False, indent=2))
    return 0


def _run_request(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    payload: dict[str, object] | None = None
    try:
        payload = load_request_payload(args.request)
        request = SolveRequest.from_dict(payload, base_dir=args.request.parent.resolve())
    except SolveContractError as err:
        request_id = "unknown"
        task = "unknown"
        if isinstance(payload, dict):
            request_id = str(payload.get("request_id") or "unknown")
            raw_task_hint = payload.get("task_hint")
            task = str(raw_task_hint) if raw_task_hint else "unknown"
        response = create_error_response(
            request_id=request_id,
            task=task,
            route_source="unknown",
            bundle_version="unknown",
            code="invalid_request",
            message=str(err),
        )
        _emit_response(args.output, response)
        return 1

    try:
        service = UnifiedSolverService.from_bundle_dir(args.bundle_dir)
    except SolverBundleError as err:
        response = create_error_response(
            request_id=request.request_id,
            task=request.task_hint or request.input_task,
            route_source="task_hint" if request.task_hint else "input_shape",
            bundle_version="unknown",
            code="invalid_bundle",
            message=str(err),
        )
        _emit_response(args.output, response)
        return 1

    response = service.solve(request)
    _emit_response(args.output, response)
    return 0 if response.status == "ok" else 1


def _emit_response(output_path: Path | None, response: Any) -> None:
    if output_path is not None:
        write_solve_response(output_path, response)
        return
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
