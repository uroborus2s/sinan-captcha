"""Unified Python CLI for training and data-engineering flows."""

from __future__ import annotations

import sys
from collections.abc import Callable

from core.autolabel import cli as autolabel_cli
from core.auto_train import cli as auto_train_cli
from core.dataset import cli as dataset_cli
from core.evaluate import cli as evaluate_cli
from core.materials import cli as materials_cli
from core.modeltest import cli as modeltest_cli
from core.ops import env as env_cli
from core.ops import setup_train as setup_train_cli
from core.predict import cli as predict_cli
from core.release import cli as release_cli
from core.solve import cli as solve_cli
from core.train.group1 import cli as train_group1_cli
from core.train.group2 import cli as train_group2_cli

CommandHandler = tuple[tuple[str, ...], Callable[[list[str] | None], int]]

COMMANDS: list[CommandHandler] = [
    (("env", "check"), lambda argv: env_cli.main(argv)),
    (("env", "setup-train"), lambda argv: setup_train_cli.main(argv)),
    (("materials", "build"), lambda argv: materials_cli.main(argv)),
    (("dataset", "validate"), lambda argv: dataset_cli.main(argv)),
    (("autolabel",), lambda argv: autolabel_cli.main(argv)),
    (("auto-train",), lambda argv: auto_train_cli.main(argv)),
    (("evaluate",), lambda argv: evaluate_cli.main(argv)),
    (("predict",), lambda argv: predict_cli.main(argv)),
    (("test",), lambda argv: modeltest_cli.main(argv)),
    (("train", "group1"), lambda argv: train_group1_cli.main(argv)),
    (("train", "group2"), lambda argv: train_group2_cli.main(argv)),
    (("release",), lambda argv: release_cli.main(argv)),
    (("solve",), lambda argv: solve_cli.main(argv)),
]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_usage())
        return 0

    for tokens, handler in COMMANDS:
        if args[: len(tokens)] == list(tokens):
            return handler(args[len(tokens) :])

    print(f"unknown command: {' '.join(args)}", file=sys.stderr)
    print(_usage(), file=sys.stderr)
    return 1


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
            "  autolabel                     Run offline autolabel flows.",
            "  auto-train                    Run the autonomous-training controller skeleton.",
            "  evaluate                      Evaluate prediction JSONL files against gold data.",
            "  predict group1|group2         Run task-specific pipeline prediction with default model/source/project paths.",
            "  test group1|group2            Run task-specific predict + evaluate and export a beginner-friendly Chinese report.",
            "  train group1                  Run group1 two-model pipeline training.",
            "  train group2                  Run group2 paired-input training.",
            "  release <subcommand>          Build, publish, or package delivery artifacts.",
            "  solve <subcommand>            Build bundles and run unified local solver requests.",
            "",
            "Examples:",
            "  uv run sinan env check",
            "  uv run sinan env setup-train --train-root D:\\sinan-captcha-work",
            "  uv run sinan materials build --spec configs/materials-pack.toml --output-root materials",
            "  uv run sinan auto-train run group1 --study-name study_001 --train-root D:\\sinan-captcha-work --generator-workspace D:\\sinan-generator\\workspace",
            "  uv run sinan predict group1 --dataset-version firstpass --train-name firstpass",
            "  uv run sinan test group2 --dataset-version firstpass --train-name firstpass",
            "  uv run sinan train group1 --dataset-version v1 --name firstpass",
            "  uv run sinan release build --project-dir .",
            "  uv run sinan solve run --bundle-dir bundles/solver/current --request req.json",
        ]
    )
