"""CLI for the autonomous-training controller skeleton."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.auto_train import controller, storage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the autonomous-training controller skeleton.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="create or resume a study and run controller stages")
    _add_common_arguments(run_parser)
    run_parser.add_argument("--max-steps", type=int, default=1)

    stage_parser = subparsers.add_parser("stage", help="run one stage capsule against a study")
    stage_parser.add_argument("stage")
    _add_common_arguments(stage_parser)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    request = controller.AutoTrainRequest(
        task=args.task,
        study_name=args.study_name,
        train_root=args.train_root,
        generator_workspace=args.generator_workspace,
        generator_executable=args.generator_executable,
        studies_root=args.studies_root,
        mode=args.mode,
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
        opencode_attach_url=args.opencode_attach_url,
        opencode_binary=args.opencode_binary,
        opencode_timeout_seconds=args.opencode_timeout_seconds,
        max_trials=args.max_trials,
        max_hours=args.max_hours,
        max_new_datasets=args.max_new_datasets,
        max_no_improve_trials=args.max_no_improve_trials,
        dataset_version=args.dataset_version,
        train_name=args.train_name,
        train_mode=args.train_mode,
        base_run=args.base_run,
        model=args.model,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        gold_dir=args.gold_dir,
        prediction_dir=args.prediction_dir,
        point_tolerance_px=args.point_tolerance_px,
        iou_threshold=args.iou_threshold,
        business_eval_dir=args.business_eval_dir,
        business_eval_success_threshold=args.business_eval_success_threshold,
        business_eval_min_cases=args.business_eval_min_cases,
        business_eval_sample_size=args.business_eval_sample_size,
        business_eval_occlusion_threshold=args.business_eval_occlusion_threshold,
    )
    ctrl = controller.AutoTrainController(request=request)

    if args.command == "run":
        result = ctrl.run(max_steps=args.max_steps)
        for item in result.executed:
            print(f"{item.stage} -> {item.next_stage} [{item.trial_id}]")
        print(f"final_stage={result.final_stage}")
        return _run_exit_code(ctrl, result)

    execution = ctrl.run_stage(args.stage)
    print(f"{execution.stage} -> {execution.next_stage} [{execution.trial_id}]")
    return 0


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("task", choices=sorted(controller.contracts.ALLOWED_TASKS))
    parser.add_argument("--study-name", required=True)
    parser.add_argument("--studies-root", type=Path, default=Path("studies"))
    parser.add_argument("--train-root", type=Path, required=True)
    parser.add_argument("--generator-workspace", type=Path, required=True)
    parser.add_argument("--generator-executable", default=controller.default_generator_executable())
    parser.add_argument("--mode", choices=sorted(controller.contracts.ALLOWED_STUDY_MODES), default="full_auto")
    parser.add_argument("--judge-provider", default=controller.DEFAULT_JUDGE_PROVIDER)
    parser.add_argument("--judge-model", default=controller.DEFAULT_JUDGE_MODEL)
    parser.add_argument("--opencode-attach-url", default=None)
    parser.add_argument("--opencode-binary", default=controller.opencode_runtime.DEFAULT_OPENCODE_BINARY)
    parser.add_argument("--opencode-timeout-seconds", type=float, default=controller.opencode_runtime.DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-trials", type=int, default=20)
    parser.add_argument("--max-hours", type=float, default=24.0)
    parser.add_argument("--max-new-datasets", type=int, default=None)
    parser.add_argument("--max-no-improve-trials", type=int, default=4)
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument("--train-name", default=None)
    parser.add_argument("--train-mode", choices=sorted(controller.contracts.ALLOWED_TRAIN_MODES), default="fresh")
    parser.add_argument("--base-run", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--device", default="0")
    parser.add_argument("--gold-dir", type=Path, default=None)
    parser.add_argument("--prediction-dir", type=Path, default=None)
    parser.add_argument("--point-tolerance-px", type=int, default=12)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--business-eval-dir", type=Path, default=None)
    parser.add_argument("--business-eval-success-threshold", type=float, default=0.98)
    parser.add_argument("--business-eval-min-cases", type=int, default=100)
    parser.add_argument("--business-eval-sample-size", type=int, default=100)
    parser.add_argument("--business-eval-occlusion-threshold", type=float, default=0.78)


if __name__ == "__main__":
    raise SystemExit(main())


def _run_exit_code(ctrl: controller.AutoTrainController, result: controller.AutoTrainRunResult) -> int:
    if result.final_stage != "STOP":
        return 0
    if not ctrl.paths.study_status_file.exists():
        return 0
    record = storage.read_study_status_record(ctrl.paths.study_status_file)
    print(f"study_status={record.status}")
    if record.final_reason is not None:
        print(f"final_reason={record.final_reason}")
    if record.final_detail is not None:
        print(f"final_detail={record.final_detail}")
    if record.commercial_ready is not None:
        print(f"commercial_ready={record.commercial_ready}")
    if record.business_success_rate is not None:
        print(f"business_success_rate={record.business_success_rate:.4f}")
    if record.status == "stopped" and record.commercial_ready is False:
        print("final_verdict=FAILED_GOAL")
        return 2
    print("final_verdict=SUCCESS")
    return 0
