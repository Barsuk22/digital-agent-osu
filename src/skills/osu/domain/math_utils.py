from __future__ import annotations

import math
from typing import Tuple


OSU_PLAYFIELD_WIDTH = 512
OSU_PLAYFIELD_HEIGHT = 384


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def clamp_position(x: float, y: float) -> Tuple[float, float]:
    return (
        clamp(x, 0.0, OSU_PLAYFIELD_WIDTH),
        clamp(y, 0.0, OSU_PLAYFIELD_HEIGHT),
    )


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def osu_circle_radius(cs: float) -> float:
    # стандартная формула osu! примерно такая:
    # radius = 54.4 - 4.48 * CS
    return 54.4 - 4.48 * cs