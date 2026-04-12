"""Model bundle contracts for the unified local solver service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from train.base import default_best_weights
from train.group1.service import (
    EMBEDDER_COMPONENT,
    PROPOSAL_COMPONENT,
    resolve_group1_component_best_weights,
)

BUNDLE_FORMAT = "sinan.solver.bundle.v1"
ROUTER_STRATEGY = "task_hint_or_input_shape_v1"
MATCHER_STRATEGY = "global_assignment_match_v1"
GROUP1_MATCHER_SIMILARITY_THRESHOLD = 0.9
GROUP1_MATCHER_AMBIGUITY_MARGIN = 0.015


class SolverBundleError(ValueError):
    """Raised when a solver bundle is malformed."""


@dataclass(frozen=True)
class SolverBundle:
    root: Path
    bundle_version: str
    manifest_path: Path
    proposal_model_path: Path
    icon_embedder_model_path: Path
    matcher_config_path: Path
    group2_model_path: Path
    router_strategy: str

    def summary(self) -> dict[str, Any]:
        return {
            "bundle_version": self.bundle_version,
            "manifest": str(self.manifest_path),
            "router_strategy": self.router_strategy,
            "proposal_model": str(self.proposal_model_path),
            "icon_embedder_model": str(self.icon_embedder_model_path),
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
    proposal_source = resolve_group1_component_best_weights(train_root, group1_run, PROPOSAL_COMPONENT)
    embedder_source = resolve_group1_component_best_weights(train_root, group1_run, EMBEDDER_COMPONENT)
    group2_source = default_best_weights(train_root, "group2", group2_run)
    for label, source in (
        ("group1 proposal-detector", proposal_source),
        ("group1 icon-embedder", embedder_source),
        ("group2 locator", group2_source),
    ):
        if not source.exists():
            raise SolverBundleError(f"未找到 {label} 权重：{source}")

    if bundle_dir.exists() and any(bundle_dir.iterdir()):
        if not force:
            raise SolverBundleError(f"bundle 目录已存在且非空：{bundle_dir}")
        shutil.rmtree(bundle_dir)

    version = bundle_version or bundle_dir.name
    proposal_target = bundle_dir / "models" / "group1" / PROPOSAL_COMPONENT / "model.pt"
    embedder_target = bundle_dir / "models" / "group1" / EMBEDDER_COMPONENT / "model.pt"
    matcher_target = bundle_dir / "models" / "group1" / "matcher" / "config.json"
    group2_target = bundle_dir / "models" / "group2" / "locator" / "model.pt"
    _copy_with_metadata(proposal_source, proposal_target, source_run=group1_run, component=PROPOSAL_COMPONENT)
    _copy_with_metadata(embedder_source, embedder_target, source_run=group1_run, component=EMBEDDER_COMPONENT)
    _copy_with_metadata(group2_source, group2_target, source_run=group2_run, component="locator")
    matcher_target.parent.mkdir(parents=True, exist_ok=True)
    matcher_target.write_text(
        json.dumps(
            {
                "strategy": MATCHER_STRATEGY,
                "embedding_model": {
                    "format": "sinan.group1.icon_embedder.pt.v1",
                    "path": embedder_target.relative_to(bundle_dir).as_posix(),
                },
                "similarity_threshold": GROUP1_MATCHER_SIMILARITY_THRESHOLD,
                "ambiguity_margin": GROUP1_MATCHER_AMBIGUITY_MARGIN,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "bundle_format": BUNDLE_FORMAT,
        "bundle_version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "router": {"strategy": ROUTER_STRATEGY},
        "models": {
            "group1": {
                "proposal_detector": {
                    "format": "ultralytics.detect.pt.v1",
                    "path": proposal_target.relative_to(bundle_dir).as_posix(),
                    "metadata": proposal_target.with_name("metadata.json").relative_to(bundle_dir).as_posix(),
                },
                "icon_embedder": {
                    "format": "sinan.group1.icon_embedder.pt.v1",
                    "path": embedder_target.relative_to(bundle_dir).as_posix(),
                    "metadata": embedder_target.with_name("metadata.json").relative_to(bundle_dir).as_posix(),
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
    proposal_model = _resolve_model_path(bundle_dir, _require_dict(group1.get("proposal_detector"), field="models.group1.proposal_detector"))
    icon_embedder_model = _resolve_model_path(bundle_dir, _require_dict(group1.get("icon_embedder"), field="models.group1.icon_embedder"))
    matcher = _require_dict(group1.get("matcher"), field="models.group1.matcher")
    matcher_config = _resolve_relative_path(bundle_dir, matcher.get("path"), field="models.group1.matcher.path")
    matcher_strategy = str(matcher.get("strategy", ""))
    if matcher_strategy != MATCHER_STRATEGY:
        raise SolverBundleError(f"matcher.strategy 非法，当前仅支持 {MATCHER_STRATEGY}")
    group2_model = _resolve_model_path(bundle_dir, _require_dict(group2.get("locator"), field="models.group2.locator"))
    return SolverBundle(
        root=bundle_dir.resolve(),
        bundle_version=bundle_version,
        manifest_path=manifest_path.resolve(),
        proposal_model_path=proposal_model,
        icon_embedder_model_path=icon_embedder_model,
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
