"""Model bundle contracts for the unified local solver service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from core.train.base import default_best_weights
from core.train.group1.service import QUERY_COMPONENT, SCENE_COMPONENT, group1_component_best_weights

BUNDLE_FORMAT = "sinan.solver.bundle.v1"
ROUTER_STRATEGY = "task_hint_or_input_shape_v1"
MATCHER_STRATEGY = "ordered_class_match_v1"


class SolverBundleError(ValueError):
    """Raised when a solver bundle is malformed."""


@dataclass(frozen=True)
class SolverBundle:
    root: Path
    bundle_version: str
    manifest_path: Path
    scene_model_path: Path
    query_model_path: Path
    matcher_config_path: Path
    group2_model_path: Path
    router_strategy: str

    def summary(self) -> dict[str, Any]:
        return {
            "bundle_version": self.bundle_version,
            "manifest": str(self.manifest_path),
            "router_strategy": self.router_strategy,
            "scene_model": str(self.scene_model_path),
            "query_model": str(self.query_model_path),
            "matcher_config": str(self.matcher_config_path),
            "group2_model": str(self.group2_model_path),
        }


def build_solver_bundle(
    *,
    bundle_dir: Path,
    train_root: Path,
    group1_run: str,
    group2_run: str,
    bundle_version: str | None = None,
    force: bool = False,
) -> SolverBundle:
    scene_source = group1_component_best_weights(train_root, group1_run, SCENE_COMPONENT)
    query_source = group1_component_best_weights(train_root, group1_run, QUERY_COMPONENT)
    group2_source = default_best_weights(train_root, "group2", group2_run)
    for label, source in (
        ("group1 scene-detector", scene_source),
        ("group1 query-parser", query_source),
        ("group2 locator", group2_source),
    ):
        if not source.exists():
            raise SolverBundleError(f"未找到 {label} 权重：{source}")

    if bundle_dir.exists() and any(bundle_dir.iterdir()):
        if not force:
            raise SolverBundleError(f"bundle 目录已存在且非空：{bundle_dir}")
        shutil.rmtree(bundle_dir)

    version = bundle_version or bundle_dir.name
    scene_target = bundle_dir / "models" / "group1" / SCENE_COMPONENT / "model.pt"
    query_target = bundle_dir / "models" / "group1" / QUERY_COMPONENT / "model.pt"
    matcher_target = bundle_dir / "models" / "group1" / "matcher" / "config.json"
    group2_target = bundle_dir / "models" / "group2" / "locator" / "model.pt"
    _copy_with_metadata(scene_source, scene_target, source_run=group1_run, component=SCENE_COMPONENT)
    _copy_with_metadata(query_source, query_target, source_run=group1_run, component=QUERY_COMPONENT)
    _copy_with_metadata(group2_source, group2_target, source_run=group2_run, component="locator")
    matcher_target.parent.mkdir(parents=True, exist_ok=True)
    matcher_target.write_text(
        json.dumps({"strategy": MATCHER_STRATEGY}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "bundle_format": BUNDLE_FORMAT,
        "bundle_version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "router": {"strategy": ROUTER_STRATEGY},
        "models": {
            "group1": {
                "scene_detector": {
                    "format": "ultralytics.detect.pt.v1",
                    "path": scene_target.relative_to(bundle_dir).as_posix(),
                    "metadata": scene_target.with_name("metadata.json").relative_to(bundle_dir).as_posix(),
                },
                "query_parser": {
                    "format": "ultralytics.detect.pt.v1",
                    "path": query_target.relative_to(bundle_dir).as_posix(),
                    "metadata": query_target.with_name("metadata.json").relative_to(bundle_dir).as_posix(),
                },
                "matcher": {
                    "strategy": MATCHER_STRATEGY,
                    "path": matcher_target.relative_to(bundle_dir).as_posix(),
                },
            },
            "group2": {
                "locator": {
                    "format": "sinan.group2.paired.pt.v1",
                    "path": group2_target.relative_to(bundle_dir).as_posix(),
                    "metadata": group2_target.with_name("metadata.json").relative_to(bundle_dir).as_posix(),
                }
            },
        },
    }
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return load_solver_bundle(bundle_dir)


def load_solver_bundle(bundle_dir: Path) -> SolverBundle:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise SolverBundleError(f"未找到 solver bundle manifest：{manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SolverBundleError(f"bundle manifest JSON 非法：{manifest_path}") from exc
    if not isinstance(payload, dict):
        raise SolverBundleError("bundle manifest 顶层必须是对象。")
    if str(payload.get("bundle_format", "")) != BUNDLE_FORMAT:
        raise SolverBundleError(
            f"bundle_format 非法：{payload.get('bundle_format', '<empty>')}，当前仅支持 {BUNDLE_FORMAT}"
        )
    bundle_version = str(payload.get("bundle_version", "")).strip()
    if not bundle_version:
        raise SolverBundleError("bundle_version 不能为空。")

    router = payload.get("router")
    if not isinstance(router, dict) or str(router.get("strategy", "")) != ROUTER_STRATEGY:
        raise SolverBundleError(f"router.strategy 非法，当前仅支持 {ROUTER_STRATEGY}")

    models = payload.get("models")
    if not isinstance(models, dict):
        raise SolverBundleError("bundle manifest 缺少 `models` 对象。")
    group1 = _require_dict(models.get("group1"), field="models.group1")
    group2 = _require_dict(models.get("group2"), field="models.group2")
    scene_model = _resolve_model_path(bundle_dir, _require_dict(group1.get("scene_detector"), field="models.group1.scene_detector"))
    query_model = _resolve_model_path(bundle_dir, _require_dict(group1.get("query_parser"), field="models.group1.query_parser"))
    matcher = _require_dict(group1.get("matcher"), field="models.group1.matcher")
    matcher_config = _resolve_relative_path(bundle_dir, matcher.get("path"), field="models.group1.matcher.path")
    if str(matcher.get("strategy", "")) != MATCHER_STRATEGY:
        raise SolverBundleError(f"matcher.strategy 非法，当前仅支持 {MATCHER_STRATEGY}")
    group2_model = _resolve_model_path(bundle_dir, _require_dict(group2.get("locator"), field="models.group2.locator"))
    return SolverBundle(
        root=bundle_dir.resolve(),
        bundle_version=bundle_version,
        manifest_path=manifest_path.resolve(),
        scene_model_path=scene_model,
        query_model_path=query_model,
        matcher_config_path=matcher_config,
        group2_model_path=group2_model,
        router_strategy=ROUTER_STRATEGY,
    )


def _copy_with_metadata(source: Path, target: Path, *, source_run: str, component: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    metadata = {
        "component": component,
        "source_run": source_run,
        "source_path": str(source),
        "copied_at": datetime.now(timezone.utc).isoformat(),
    }
    target.with_name("metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_model_path(bundle_dir: Path, model_payload: dict[str, Any]) -> Path:
    return _resolve_relative_path(bundle_dir, model_payload.get("path"), field="model.path")


def _resolve_relative_path(bundle_dir: Path, raw_path: Any, *, field: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SolverBundleError(f"`{field}` 必须是非空相对路径。")
    rel_path = Path(raw_path.strip())
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise SolverBundleError(f"`{field}` 只能使用 bundle 内相对路径：{raw_path}")
    resolved = (bundle_dir / rel_path).resolve()
    if not resolved.exists():
        raise SolverBundleError(f"bundle 缺少文件：{resolved}")
    return resolved


def _require_dict(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SolverBundleError(f"`{field}` 必须是对象。")
    return value

