"""Unified Python CLI for training and data-engineering flows."""

from __future__ import annotations

import importlib
import sys

CommandHandler = tuple[tuple[str, ...], str]

COMMANDS: list[CommandHandler] = [
    (("env", "check"), "core.ops.env"),
    (("env", "setup-train"), "core.ops.setup_train"),
    (("materials", "build"), "core.materials.cli"),
    (("dataset", "validate"), "core.dataset.cli"),
    (("exam",), "core.exam.cli"),
    (("autolabel",), "core.autolabel.cli"),
    (("auto-train",), "core.auto_train.cli"),
    (("evaluate",), "core.evaluate.cli"),
    (("predict",), "core.predict.cli"),
    (("test",), "core.modeltest.cli"),
    (("train", "group1"), "core.train.group1.cli"),
    (("train", "group2"), "core.train.group2.cli"),
    (("release",), "core.release.cli"),
    (("solve",), "core.solve.cli"),
]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_usage())
        return 0

    for tokens, module_path in COMMANDS:
        if args[: len(tokens)] == list(tokens):
            return _run_command(module_path, args[len(tokens) :])

    print(f"unknown command: {' '.join(args)}", file=sys.stderr)
    print(_usage(), file=sys.stderr)
    return 1


def _run_command(module_path: str, argv: list[str]) -> int:
    module = importlib.import_module(module_path)
    return module.main(argv)


def _usage() -> str:
    return "\n".join(
        [
            "uv run sinan <command>",
            "",
            "Commands:",
            "  env check                     Check whether the training host is ready.",
            "  env setup-train               Create a dedicated training root and bootstrap its uv environment.",
            "  materials build               Build a local offline materials pack.",
            "  dataset validate              Validate a JSONL dataset file.",
            "  exam                          Prepare business exam workspaces and export reviewed labels.",
            "  autolabel                     Run offline autolabel flows.",
            "  auto-train                    Run the autonomous-training controller skeleton.",
            "  evaluate                      Evaluate prediction JSONL files against gold data.",
            "  predict group1|group2         Run task-specific pipeline prediction with default model/source/project paths.",
            "  test group1|group2            Run task-specific predict + evaluate and export a beginner-friendly Chinese report.",
            "  train group1                  Run group1 training or reviewed-exam prelabel export.",
            "  train group2                  Run group2 training or reviewed-exam prelabel export.",
            "  release <subcommand>          Build, publish, or package delivery artifacts.",
            "  solve <subcommand>            Build bundles and run unified local solver requests.",
            "",
            "Examples:",
            "  uv run sinan env check",
            "  uv run sinan env setup-train --train-root D:\\sinan-captcha-work",
            "  uv run sinan materials build --spec configs/materials-pack.toml --output-root materials",
            "  uv run sinan exam prepare --task group1 --materials-root materials --output-dir materials/business_exams/group1/reviewed-v1",
            "  uv run sinan auto-train run group1 --study-name study_001 --train-root D:\\sinan-captcha-work --generator-workspace D:\\sinan-generator\\workspace",
            "  uv run sinan predict group1 --dataset-version firstpass --train-name firstpass",
            "  uv run sinan test group2 --dataset-version firstpass --train-name firstpass",
            "  uv run sinan train group1 --dataset-version v1 --name firstpass",
            "  uv run sinan train group1 prelabel --exam-root materials/business_exams/group1/reviewed-v1 --train-name firstpass",
            "  uv run sinan release build-all --project-dir .",
            "  uv run sinan solve run --bundle-dir bundles/solver/current --request req.json",
        ]
    )
