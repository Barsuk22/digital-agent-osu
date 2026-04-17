from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class UpcomingObjectView:
    kind_id: int          # 0 circle, 1 slider, 2 spinner, -1 empty
    x: float
    y: float
    time_to_hit_ms: float
    distance_to_cursor: float
    is_active: float


@dataclass(slots=True)
class OsuObservation:
    time_ms: float
    cursor_x: float
    cursor_y: float
    upcoming: List[UpcomingObjectView]


@dataclass(slots=True)
class OsuAction:
    dx: float
    dy: float
    click_strength: float