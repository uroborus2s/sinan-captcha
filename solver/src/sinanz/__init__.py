"""Standalone public API for captcha solver consumers."""

from .api import CaptchaSolver, sn_match_slider, sn_match_targets
from .errors import SolverAssetError, SolverError, SolverInputError, SolverRuntimeError
from . import native_bridge
from .types import (
    BBox,
    ClickCaptchaDebugInfo,
    ImageInput,
    OrderedClickTarget,
    OrderedClickTargetsResult,
    SliderGapCenterResult,
    SliderGapDebugInfo,
)

__all__ = [
    "BBox",
    "CaptchaSolver",
    "ClickCaptchaDebugInfo",
    "ImageInput",
    "OrderedClickTarget",
    "OrderedClickTargetsResult",
    "SliderGapCenterResult",
    "SliderGapDebugInfo",
    "SolverAssetError",
    "SolverError",
    "SolverInputError",
    "SolverRuntimeError",
    "sn_match_slider",
    "sn_match_targets",
    "native_bridge",
]

__version__ = "0.1.0"
