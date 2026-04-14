"""Standalone public API for slider captcha solver consumers."""

from __future__ import annotations

from pathlib import Path

from sinanz_errors import SolverAssetError, SolverError, SolverInputError, SolverRuntimeError
from sinanz_group2_service import solve_slider_gap
from sinanz_types import BBox, ImageInput, SliderGapCenterResult, SliderGapDebugInfo

_default_solver: "CaptchaSolver | None" = None


class CaptchaSolver:
    """Public facade for the standalone slider captcha solver package."""

    def __init__(self, *, device: str = "auto", asset_root: str | Path | None = None) -> None:
        self.device = device
        self.asset_root = Path(asset_root).expanduser().resolve() if asset_root is not None else None

    def sn_match_slider(
        self,
        background_image: ImageInput,
        puzzle_piece_image: ImageInput,
        *,
        puzzle_piece_start_bbox: BBox | None = None,
        return_debug: bool = False,
    ) -> SliderGapCenterResult:
        return solve_slider_gap(
            background_image=background_image,
            puzzle_piece_image=puzzle_piece_image,
            puzzle_piece_start_bbox=puzzle_piece_start_bbox,
            device=self.device,
            asset_root=self.asset_root,
            return_debug=return_debug,
        )


def sn_match_slider(
    background_image: ImageInput,
    puzzle_piece_image: ImageInput,
    *,
    puzzle_piece_start_bbox: BBox | None = None,
    device: str = "auto",
    return_debug: bool = False,
) -> SliderGapCenterResult:
    return _get_default_solver(device=device).sn_match_slider(
        background_image=background_image,
        puzzle_piece_image=puzzle_piece_image,
        puzzle_piece_start_bbox=puzzle_piece_start_bbox,
        return_debug=return_debug,
    )


def _get_default_solver(*, device: str) -> CaptchaSolver:
    global _default_solver
    if _default_solver is None or _default_solver.device != device:
        _default_solver = CaptchaSolver(device=device)
    return _default_solver


__all__ = [
    "BBox",
    "CaptchaSolver",
    "ImageInput",
    "SliderGapCenterResult",
    "SliderGapDebugInfo",
    "SolverAssetError",
    "SolverError",
    "SolverInputError",
    "SolverRuntimeError",
    "sn_match_slider",
]

__version__ = "0.0.1.dev0"
