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
class SliderStateView:
    active_slider: float
    primary_is_slider: float
    progress: float
    target_x: float
    target_y: float
    distance_to_target: float
    distance_to_ball: float
    inside_follow: float
    head_hit: float
    time_to_end_ms: float
    tangent_x: float
    tangent_y: float
    follow_radius: float


@dataclass(slots=True)
class OsuObservation:
    time_ms: float
    cursor_x: float
    cursor_y: float
    upcoming: List[UpcomingObjectView]
    slider: SliderStateView


@dataclass(slots=True)
class OsuAction:
    dx: float
    dy: float
    click_strength: float
