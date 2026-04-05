"""Dataset-build runner adapter for the autonomous-training controller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

from core.auto_train import contracts
from core.auto_train.runners.common import RunnerExecutionError, command_string, require_existing_path

DatasetCommandExecutor = Callable[[list[str]], object]


@dataclass(frozen=True)
class DatasetRunnerRequest:
    task: str
    dataset_version: str
    generator_workspace: Path
    dataset_dir: Path
    preset: str | None = None
    override_file: Path | None = None
    generator_executable: str = "sinan-generator"
    force: bool = False

    def command(self) -> list[str]:
        command = [
            self.generator_executable,
            "make-dataset",
            "--workspace",
            str(self.generator_workspace),
            "--task",
            self.task,
            "--dataset-dir",
            str(self.dataset_dir),
        ]
        if self.preset:
            command.extend(["--preset", self.preset])
        if self.override_file is not None:
            command.extend(["--override-file", str(self.override_file)])
        if self.force:
            command.append("--force")
        return command


@dataclass(frozen=True)
class DatasetRunnerResult:
    record: contracts.DatasetRecord
    command: str


def run_dataset_request(
    request: DatasetRunnerRequest,
    *,
    executor: DatasetCommandExecutor | None = None,
) -> DatasetRunnerResult:
    """Run the generator dataset command and normalize its output for the study ledger."""

    command = request.command()
    command_text = command_string(command)
    require_existing_path(
        request.generator_workspace,
        stage="BUILD_DATASET",
        label="生成器工作区",
        command=command_text,
    )
    if request.override_file is not None:
        require_existing_path(
            request.override_file,
            stage="BUILD_DATASET",
            label="生成器覆盖配置文件",
            command=command_text,
        )

    try:
        (executor or _execute_command)(command)
    except FileNotFoundError as exc:
        raise RunnerExecutionError(
            stage="BUILD_DATASET",
            reason="missing_launcher",
            message=f"未找到数据集生成命令：{request.generator_executable}",
            retryable=False,
            command=command_text,
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RunnerExecutionError(
            stage="BUILD_DATASET",
            reason="command_failed",
            message=f"数据集生成命令执行失败，退出码：{exc.returncode}",
            retryable=True,
            command=command_text,
        ) from exc

    return DatasetRunnerResult(
        record=contracts.DatasetRecord(
            task=request.task,
            dataset_version=request.dataset_version,
            dataset_root=str(request.dataset_dir),
            label_source=str(request.generator_workspace),
        ),
        command=command_text,
    )


def _execute_command(command: list[str]) -> None:
    subprocess.run(command, check=True)
