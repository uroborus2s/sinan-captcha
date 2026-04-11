"""Shared helpers for autonomous-training runner adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


class RunnerExecutionError(RuntimeError):
    """Structured runner failure surfaced to the controller."""

    def __init__(
        self,
        *,
        stage: str,
        reason: str,
        message: str,
        retryable: bool,
        command: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.reason = reason
        self.retryable = retryable
        self.command = command


def command_string(command: Sequence[str]) -> str:
    """Render a command list into a simple audit string."""

    return " ".join(str(part) for part in command)


def require_existing_path(path: Path, *, stage: str, label: str, command: str | None = None) -> None:
    """Raise a non-retryable runner error when an expected path is missing."""

    if path.exists():
        return
    raise RunnerExecutionError(
        stage=stage,
        reason="missing_input",
        message=f"未找到 {label}：{path}",
        retryable=False,
        command=command,
    )


def classify_runtime_error(stage: str, message: str, *, command: str | None = None) -> RunnerExecutionError:
    """Map runtime messages from lower layers into stable runner failure reasons."""

    reason = "runtime_failure"
    retryable = False

    if "模型测试失败" in message or "查看上面的 YOLO 原始输出" in message:
        reason = "command_failed"
        retryable = True
    elif "未检测到 `uv`" in message or "缺少依赖" in message or "未找到训练启动器" in message:
        reason = "missing_dependency"
    elif "未找到预测启动器" in message or "未找到测试启动器" in message:
        reason = "missing_dependency"
    elif "未找到" in message:
        reason = "missing_input"

    return RunnerExecutionError(
        stage=stage,
        reason=reason,
        message=message,
        retryable=retryable,
        command=command,
    )
