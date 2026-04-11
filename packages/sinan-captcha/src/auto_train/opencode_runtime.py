"""Runtime adapter for invoking OpenCode commands from the controller."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from auto_train import opencode_commands, opencode_skills
from common.paths import repository_root

DEFAULT_PROJECT_ROOT = repository_root(Path(__file__))
DEFAULT_OPENCODE_BINARY = "opencode"
DEFAULT_TIMEOUT_SECONDS = 300.0
TRACE_TEXT_PREVIEW_LIMIT = 40_000
_LOCAL_ATTACH_RETRYABLE_MESSAGES = {
    "opencode_empty_stdout",
    "opencode_incomplete_event_stream",
    "opencode_incomplete_tool_calls",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_local_attach_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def _json_event_payloads(raw_output: str) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _collect_event_output_strings(node: object, *, path: tuple[str, ...], sink: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _collect_event_output_strings(value, path=path + (key,), sink=sink)
        return
    if isinstance(node, list):
        for value in node:
            _collect_event_output_strings(value, path=path, sink=sink)
        return
    if not isinstance(node, str):
        return
    if "input" in path:
        return
    leaf = path[-1] if path else ""
    if leaf in {"output", "text", "content"}:
        sink.append(node)


def _detect_incomplete_event_stream(raw_output: str) -> str | None:
    event_payloads = [payload for payload in _json_event_payloads(raw_output) if isinstance(payload.get("type"), str)]
    if not event_payloads:
        return None
    last_payload = event_payloads[-1]
    if last_payload.get("type") != "step_finish":
        text_candidates: list[str] = []
        for payload in event_payloads:
            _collect_event_output_strings(payload, path=(), sink=text_candidates)
        if text_candidates:
            return None
        return "opencode_incomplete_event_stream"
    part = last_payload.get("part")
    if isinstance(part, dict) and part.get("reason") == "tool-calls":
        return "opencode_incomplete_tool_calls"
    text_candidates = []
    for payload in event_payloads:
        _collect_event_output_strings(payload, path=(), sink=text_candidates)
    if text_candidates:
        return None
    return "opencode_incomplete_event_stream"


def _read_text_preview(path: Path, *, limit: int = TRACE_TEXT_PREVIEW_LIMIT) -> tuple[str | None, bool, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return None, False, f"unicode_decode_error: {exc}"
    except OSError as exc:
        return None, False, f"os_error: {exc}"
    if len(text) <= limit:
        return text, False, None
    return text[:limit], True, None


@dataclass(frozen=True)
class OpenCodeAttachedFileTrace:
    path: str
    exists: bool
    size_bytes: int | None
    content_text: str | None
    truncated: bool
    read_error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "exists": self.exists,
            "size_bytes": self.size_bytes,
            "content_text": self.content_text,
            "truncated": self.truncated,
            "read_error": self.read_error,
        }


@dataclass(frozen=True)
class OpenCodeTraceRecord:
    created_at: str
    command_name: str
    arguments: tuple[str, ...]
    project_root: str
    attach_url: str | None
    model: str | None
    command: tuple[str, ...]
    command_markdown_path: str
    command_markdown_text: str | None
    command_markdown_truncated: bool
    command_markdown_error: str | None
    skill_markdown_path: str | None
    skill_markdown_text: str | None
    skill_markdown_truncated: bool
    skill_markdown_error: str | None
    attached_files: tuple[OpenCodeAttachedFileTrace, ...]
    stdout: str
    stderr: str
    returncode: int | None
    success: bool
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "created_at": self.created_at,
            "command_name": self.command_name,
            "arguments": list(self.arguments),
            "project_root": self.project_root,
            "attach_url": self.attach_url,
            "model": self.model,
            "command": list(self.command),
            "command_markdown_path": self.command_markdown_path,
            "command_markdown_text": self.command_markdown_text,
            "command_markdown_truncated": self.command_markdown_truncated,
            "command_markdown_error": self.command_markdown_error,
            "skill_markdown_path": self.skill_markdown_path,
            "skill_markdown_text": self.skill_markdown_text,
            "skill_markdown_truncated": self.skill_markdown_truncated,
            "skill_markdown_error": self.skill_markdown_error,
            "attached_files": [item.to_dict() for item in self.attached_files],
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
            "success": self.success,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class OpenCodeRuntimeConfig:
    project_root: Path = DEFAULT_PROJECT_ROOT
    binary: str = DEFAULT_OPENCODE_BINARY
    attach_url: str | None = None
    model: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    trace_sink: Callable[[OpenCodeTraceRecord], None] | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")


@dataclass(frozen=True)
class OpenCodeInvocationResult:
    stdout: str
    stderr: str
    command: tuple[str, ...]
    returncode: int


class OpenCodeRuntimeError(RuntimeError):
    def __init__(
        self,
        *,
        command_name: str,
        message: str,
        command: list[str],
        returncode: int | None = None,
    ) -> None:
        super().__init__(message)
        self.command_name = command_name
        self.command = tuple(command)
        self.returncode = returncode


def subprocess_runner(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
) -> OpenCodeInvocationResult:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    return OpenCodeInvocationResult(
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        command=tuple(command),
        returncode=completed.returncode,
    )


@dataclass(frozen=True)
class OpenCodeRuntimeAdapter:
    config: OpenCodeRuntimeConfig
    runner: object = subprocess_runner

    def judge_trial(
        self,
        *,
        study_name: str,
        task: str,
        trial_id: str,
        files: list[Path],
    ) -> OpenCodeInvocationResult:
        return self.run_command(
            "judge-trial",
            arguments=[study_name, task, trial_id],
            files=files,
        )

    def result_read(
        self,
        *,
        study_name: str,
        task: str,
        trial_id: str,
        dataset_version: str,
        train_name: str,
        primary_metric: str,
        files: list[Path],
    ) -> OpenCodeInvocationResult:
        return self.run_command(
            "result-read",
            arguments=[study_name, task, trial_id, dataset_version, train_name, primary_metric],
            files=files,
        )

    def study_status(
        self,
        *,
        study_name: str,
        task: str,
        files: list[Path],
    ) -> OpenCodeInvocationResult:
        return self.run_command(
            "study-status",
            arguments=[study_name, task],
            files=files,
        )

    def plan_dataset(
        self,
        *,
        study_name: str,
        task: str,
        trial_id: str,
        files: list[Path],
    ) -> OpenCodeInvocationResult:
        return self.run_command(
            "plan-dataset",
            arguments=[study_name, task, trial_id],
            files=files,
        )

    def run_command(
        self,
        name: str,
        *,
        arguments: list[str],
        files: list[Path],
    ) -> OpenCodeInvocationResult:
        spec = opencode_commands.get_command_spec(name)
        command = self._build_command(name, arguments=arguments, files=files, attach_url=self.config.attach_url)
        command_markdown_path = spec.markdown_path(self.config.project_root)
        try:
            return self._invoke_once(
                spec=spec,
                name=name,
                arguments=arguments,
                files=files,
                command=command,
                command_markdown_path=command_markdown_path,
                attach_url=self.config.attach_url,
                empty_stdout_error_message="opencode_empty_stdout",
            )
        except OpenCodeRuntimeError as exc:
            if not _is_local_attach_url(self.config.attach_url) or str(exc) not in _LOCAL_ATTACH_RETRYABLE_MESSAGES:
                raise

        retry_command = self._build_command(name, arguments=arguments, files=files, attach_url=None)
        try:
            return self._invoke_once(
                spec=spec,
                name=name,
                arguments=arguments,
                files=files,
                command=retry_command,
                command_markdown_path=command_markdown_path,
                attach_url=None,
                empty_stdout_error_message="opencode_empty_stdout_after_local_retry",
            )
        except OpenCodeRuntimeError as retry_exc:
            raise OpenCodeRuntimeError(
                command_name=name,
                message=f"opencode_empty_stdout; local_retry_failed: {retry_exc}",
                command=list(retry_exc.command),
                returncode=retry_exc.returncode,
            ) from retry_exc

    def _build_command(
        self,
        name: str,
        *,
        arguments: list[str],
        files: list[Path],
        attach_url: str | None,
    ) -> list[str]:
        command = opencode_commands.build_headless_invocation(
            name,
            arguments=arguments,
            files=files,
            project_root=self.config.project_root,
            attach_url=attach_url,
            model=self.config.model,
        )
        command[0] = self.config.binary
        return command

    def _invoke_once(
        self,
        *,
        spec: opencode_commands.OpenCodeCommandSpec,
        name: str,
        arguments: list[str],
        files: list[Path],
        command: list[str],
        command_markdown_path: Path,
        attach_url: str | None,
        empty_stdout_error_message: str,
    ) -> OpenCodeInvocationResult:
        try:
            result = self.runner(
                command,
                cwd=self.config.project_root,
                timeout_seconds=self.config.timeout_seconds,
            )
        except FileNotFoundError as exc:
            self._emit_trace(
                spec=spec,
                name=name,
                arguments=arguments,
                files=files,
                command=command,
                command_markdown_path=command_markdown_path,
                attach_url=attach_url,
                stdout="",
                stderr="",
                returncode=None,
                success=False,
                error_message=f"opencode_binary_not_found: {self.config.binary}",
            )
            raise OpenCodeRuntimeError(
                command_name=name,
                message=f"opencode_binary_not_found: {self.config.binary}",
                command=command,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            self._emit_trace(
                spec=spec,
                name=name,
                arguments=arguments,
                files=files,
                command=command,
                command_markdown_path=command_markdown_path,
                attach_url=attach_url,
                stdout="",
                stderr="",
                returncode=None,
                success=False,
                error_message=(
                    f"opencode_timeout: {self.config.timeout_seconds}s; "
                    "increase --opencode-timeout-seconds for slow local models"
                ),
            )
            raise OpenCodeRuntimeError(
                command_name=name,
                message=(
                    f"opencode_timeout: {self.config.timeout_seconds}s; "
                    "increase --opencode-timeout-seconds for slow local models"
                ),
                command=command,
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit_code={result.returncode}"
            self._emit_trace(
                spec=spec,
                name=name,
                arguments=arguments,
                files=files,
                command=command,
                command_markdown_path=command_markdown_path,
                attach_url=attach_url,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                success=False,
                error_message=f"opencode_command_failed: {detail}",
            )
            raise OpenCodeRuntimeError(
                command_name=name,
                message=f"opencode_command_failed: {detail}",
                command=list(result.command),
                returncode=result.returncode,
            )

        if not result.stdout.strip():
            self._emit_trace(
                spec=spec,
                name=name,
                arguments=arguments,
                files=files,
                command=command,
                command_markdown_path=command_markdown_path,
                attach_url=attach_url,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                success=False,
                error_message=empty_stdout_error_message,
            )
            raise OpenCodeRuntimeError(
                command_name=name,
                message=empty_stdout_error_message,
                command=list(result.command),
                returncode=result.returncode,
            )
        incomplete_output_error = _detect_incomplete_event_stream(result.stdout)
        if incomplete_output_error is not None:
            self._emit_trace(
                spec=spec,
                name=name,
                arguments=arguments,
                files=files,
                command=command,
                command_markdown_path=command_markdown_path,
                attach_url=attach_url,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                success=False,
                error_message=incomplete_output_error,
            )
            raise OpenCodeRuntimeError(
                command_name=name,
                message=incomplete_output_error,
                command=list(result.command),
                returncode=result.returncode,
            )
        self._emit_trace(
            spec=spec,
            name=name,
            arguments=arguments,
            files=files,
            command=command,
            command_markdown_path=command_markdown_path,
            attach_url=attach_url,
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            success=True,
            error_message=None,
        )
        return result

    def _emit_trace(
        self,
        *,
        spec: opencode_commands.OpenCodeCommandSpec,
        name: str,
        arguments: list[str],
        files: list[Path],
        command: list[str],
        command_markdown_path: Path,
        attach_url: str | None,
        stdout: str,
        stderr: str,
        returncode: int | None,
        success: bool,
        error_message: str | None,
    ) -> None:
        if self.config.trace_sink is None:
            return
        command_markdown_text, command_markdown_truncated, command_markdown_error = _read_text_preview(command_markdown_path)
        skill_markdown_path: Path | None = None
        skill_markdown_text: str | None = None
        skill_markdown_truncated = False
        skill_markdown_error: str | None = None
        if spec.skill_name is not None:
            skill_markdown_path = opencode_skills.skill_registry()[spec.skill_name].markdown_path(self.config.project_root)
            skill_markdown_text, skill_markdown_truncated, skill_markdown_error = _read_text_preview(skill_markdown_path)
        attached_files = tuple(_build_attached_file_trace(path) for path in files)
        record = OpenCodeTraceRecord(
            created_at=_utc_now_iso(),
            command_name=name,
            arguments=tuple(arguments),
            project_root=str(self.config.project_root),
            attach_url=attach_url,
            model=self.config.model,
            command=tuple(command),
            command_markdown_path=str(command_markdown_path),
            command_markdown_text=command_markdown_text,
            command_markdown_truncated=command_markdown_truncated,
            command_markdown_error=command_markdown_error,
            skill_markdown_path=str(skill_markdown_path) if skill_markdown_path is not None else None,
            skill_markdown_text=skill_markdown_text,
            skill_markdown_truncated=skill_markdown_truncated,
            skill_markdown_error=skill_markdown_error,
            attached_files=attached_files,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            success=success,
            error_message=error_message,
        )
        self.config.trace_sink(record)


def _build_attached_file_trace(path: Path) -> OpenCodeAttachedFileTrace:
    exists = path.exists()
    size_bytes = path.stat().st_size if exists else None
    if not exists:
        return OpenCodeAttachedFileTrace(
            path=str(path),
            exists=False,
            size_bytes=None,
            content_text=None,
            truncated=False,
            read_error="file_not_found",
        )
    content_text, truncated, read_error = _read_text_preview(path)
    return OpenCodeAttachedFileTrace(
        path=str(path),
        exists=True,
        size_bytes=size_bytes,
        content_text=content_text,
        truncated=truncated,
        read_error=read_error,
    )
