"""Inference output contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClickPoint:
    x: int
    y: int


def map_group1_clicks() -> list[ClickPoint]:
    raise NotImplementedError("Group1 click mapping is not implemented yet.")


def map_group2_center() -> ClickPoint:
    raise NotImplementedError("Group2 center mapping is not implemented yet.")
