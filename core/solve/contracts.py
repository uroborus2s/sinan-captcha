"""Contracts for the unified local solver service."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class SolveContractError(ValueError):
    """Raised when a solver request/response contract is invalid."""


@dataclass(frozen=True)
class Group1SolveInputs:
    query_image: Path
    scene_image: Path


@dataclass(frozen=True)
class Group2SolveInputs:
    master_image: Path
    tile_image: Path
    tile_start_bbox: list[int] | None = None


@dataclass(frozen=True)
class SolveRequest:
    request_id: str
    task_hint: str | None
    inputs: Group1SolveInputs | Group2SolveInputs
    device: str = "0"
    return_debug: bool = False

    @property
    def input_task(self) -> str:
        if isinstance(self.inputs, Group1SolveInputs):
            return "group1"
        return "group2"

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, base_dir: Path | None = None) -> "SolveRequest":
        request_id = _require_non_empty_string(payload.get("request_id"), field="request_id")
        raw_task_hint = payload.get("task_hint")
        task_hint: str | None = None
        if raw_task_hint not in {None, ""}:
            task_hint = _require_known_task(raw_task_hint, field="task_hint")

        raw_inputs = payload.get("inputs")
        if not isinstance(raw_inputs, dict):
            raise SolveContractError("请求缺少合法的 `inputs` 对象。")
        inputs = _parse_inputs(raw_inputs, base_dir=base_dir)

        raw_options = payload.get("options", {})
        if raw_options is None or raw_options == "":
            raw_options = {}
        if not isinstance(raw_options, dict):
            raise SolveContractError("`options` 必须是对象。")

        raw_device = raw_options.get("device", "0")
        device = "0" if raw_device in {None, ""} else str(raw_device)
        return_debug = bool(raw_options.get("return_debug", False))
        return cls(
            request_id=request_id,
            task_hint=task_hint,
            inputs=inputs,
            device=device,
            return_debug=return_debug,
        )


@dataclass(frozen=True)
class SolveError:
    code: str
    message: str
    details: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": list(self.details),
        }


@dataclass(frozen=True)
class SolveResponse:
    request_id: str
    task: str
    status: str
    route_source: str
    bundle_version: str
    result: dict[str, Any] | None = None
    error: SolveError | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "task": self.task,
            "status": self.status,
            "route_source": self.route_source,
            "bundle_version": self.bundle_version,
        }
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        return payload


def create_error_response(
    *,
    request_id: str,
    task: str,
    route_source: str,
    bundle_version: str,
    code: str,
    message: str,
    details: list[str] | None = None,
) -> SolveResponse:
    return SolveResponse(
        request_id=request_id,
        task=task,
        status="error",
        route_source=route_source,
        bundle_version=bundle_version,
        error=SolveError(code=code, message=message, details=list(details or [])),
    )


def load_request_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SolveContractError(f"请求 JSON 非法：{path}") from exc
    if not isinstance(payload, dict):
        raise SolveContractError("请求 JSON 顶层必须是对象。")
    return payload


def load_solve_request(path: Path) -> SolveRequest:
    payload = load_request_payload(path)
    return SolveRequest.from_dict(payload, base_dir=path.parent.resolve())


def write_solve_response(path: Path, response: SolveResponse) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(response.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_inputs(raw_inputs: dict[str, Any], *, base_dir: Path | None) -> Group1SolveInputs | Group2SolveInputs:
    present = {key for key, value in raw_inputs.items() if value not in {None, ""}}
    group1_keys = {"query_image", "scene_image"}
    group2_required_keys = {"master_image", "tile_image"}
    group2_optional_keys = {"tile_start_bbox"}

    if group1_keys.issubset(present) and not present.intersection(group2_required_keys | group2_optional_keys):
        return Group1SolveInputs(
            query_image=_resolve_path(raw_inputs["query_image"], base_dir=base_dir, field="inputs.query_image"),
            scene_image=_resolve_path(raw_inputs["scene_image"], base_dir=base_dir, field="inputs.scene_image"),
        )
    if group2_required_keys.issubset(present) and not present.intersection(group1_keys):
        return Group2SolveInputs(
            master_image=_resolve_path(raw_inputs["master_image"], base_dir=base_dir, field="inputs.master_image"),
            tile_image=_resolve_path(raw_inputs["tile_image"], base_dir=base_dir, field="inputs.tile_image"),
            tile_start_bbox=(
                _require_bbox(raw_inputs["tile_start_bbox"], field="inputs.tile_start_bbox")
                if raw_inputs.get("tile_start_bbox") not in {None, ""}
                else None
            ),
        )
    raise SolveContractError(
        "无法根据 `inputs` 判定任务类型。"
        "请提供 `query_image + scene_image`，或 `master_image + tile_image`。"
    )


def _resolve_path(value: Any, *, base_dir: Path | None, field: str) -> Path:
    raw = _require_non_empty_string(value, field=field)
    path = Path(raw)
    if not path.is_absolute() and base_dir is not None:
        path = (base_dir / path).resolve()
    return path


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SolveContractError(f"`{field}` 必须是非空字符串。")
    return value.strip()


def _require_known_task(value: Any, *, field: str) -> str:
    task = _require_non_empty_string(value, field=field)
    if task not in {"group1", "group2"}:
        raise SolveContractError(f"`{field}` 非法：{task}")
    return task


def _require_bbox(value: Any, *, field: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 4:
        raise SolveContractError(f"`{field}` 必须是长度为 4 的整数数组。")
    try:
        return [int(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise SolveContractError(f"`{field}` 必须是长度为 4 的整数数组。") from exc
