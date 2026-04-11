"""Unified Python CLI for training and data-engineering flows."""

from __future__ import annotations

import importlib
import sys

CommandHandler = tuple[tuple[str, ...], str]

COMMANDS: list[CommandHandler] = [
    (("env", "check"), "ops.env"),
    (("env", "setup-train"), "ops.setup_train"),
    (("materials", "build"), "materials.cli"),
    (("materials", "audit-group1-query"), "materials.query_audit_cli"),
    (("materials", "collect-backgrounds"), "materials.background_style_cli"),
    (("dataset", "validate"), "dataset.cli"),
    (("exam",), "exam.cli"),
    (("autolabel",), "autolabel.cli"),
    (("auto-train",), "auto_train.cli"),
    (("evaluate",), "evaluate.cli"),
    (("predict",), "predict.cli"),
    (("test",), "modeltest.cli"),
    (("train", "group1"), "train.group1.cli"),
    (("train", "group2"), "train.group2.cli"),
    (("solve",), "solve.cli"),
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
            "  materials audit-group1-query  Analyze validation query images and build a tpl_/var_ group1 icon pack.",
            "  materials collect-backgrounds Analyze reference background style and download similar web backgrounds.",
            "  dataset validate              Validate a JSONL dataset file.",
            "  exam                          Prepare business exam workspaces and export reviewed labels.",
            "  autolabel                     Run offline autolabel flows.",
            "  auto-train                    Run the autonomous-training controller skeleton.",
            "  evaluate                      Evaluate prediction JSONL files against gold data.",
            "  predict group1|group2         Run task-specific pipeline prediction with default model/source/project paths.",
            "  test group1|group2            Run task-specific predict + evaluate; group1 verifies final position selection.",
            "  train group1                  Run group1 split training or reviewed-exam prelabel export.",
            "  train group2                  Run group2 training or reviewed-exam prelabel export.",
            "  solve <subcommand>            Build bundles and run unified local solver requests.",
            "",
            "Examples:",
            "  uv run sinan env check",
            "  uv run sinan env setup-train --train-root D:\\sinan-captcha-work",
            "  uv run sinan materials build --spec configs/materials-pack.toml --output-root work_home/materials",
            "  uv run sinan materials audit-group1-query --model gemma4:26b --overwrite",
            "  uv run sinan materials collect-backgrounds --source-dir work_home/materials/backgrounds --model qwen2.5vl:7b",
            "  uv run sinan exam prepare --task group1 --materials-root work_home/materials --output-dir work_home/materials/business_exams/group1/reviewed-v1",
            "  uv run sinan auto-train run group1 --study-name study_001 --train-root D:\\sinan-captcha-work --generator-workspace D:\\sinan-generator\\workspace",
            "  uv run sinan predict group1 --dataset-version firstpass --train-name firstpass",
            "  uv run sinan train group1 --dataset-version v1 --name g1_query --component query-parser",
            "  uv run sinan train group1 --dataset-version v1 --name g1_proposal --component proposal-detector",
            "  uv run sinan train group1 --dataset-version v1 --name g1_embed --component icon-embedder",
            "  uv run sinan test group2 --dataset-version firstpass --train-name firstpass",
            "  uv run sinan train group1 --dataset-version v1 --name firstpass",
            "  uv run sinan train group1 prelabel --exam-root work_home/materials/business_exams/group1/reviewed-v1 --train-name firstpass",
            "  uv run sinan solve run --bundle-dir bundles/solver/current --request req.json",
        ]
    )
