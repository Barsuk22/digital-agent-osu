from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from src.skills.osu.domain.models import SliderObject

Vec2 = Tuple[float, float]


def _lerp(a: Vec2, b: Vec2, t: float) -> Vec2:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _distance(a: Vec2, b: Vec2) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _bezier_point(points: Sequence[Vec2], t: float) -> Vec2:
    pts = list(points)
    while len(pts) > 1:
        pts = [_lerp(pts[i], pts[i + 1], t) for i in range(len(pts) - 1)]
    return pts[0]


def _sample_line(points: Sequence[Vec2], samples_per_segment: int = 24) -> List[Vec2]:
    result: List[Vec2] = []
    for i in range(len(points) - 1):
        a = points[i]
        b = points[i + 1]
        for s in range(samples_per_segment):
            t = s / samples_per_segment
            result.append(_lerp(a, b, t))
    result.append(points[-1])
    return result


def _sample_bezier(points: Sequence[Vec2], samples: int = 128) -> List[Vec2]:
    if len(points) == 1:
        return [points[0]]
    return [_bezier_point(points, i / (samples - 1)) for i in range(samples)]


def _sample_passthrough(points: Sequence[Vec2], samples: int = 128) -> List[Vec2]:
    # Для Phase 0.7: passthrough временно ведём как bezier-подобную кривую.
    # Это не osu-perfect arc solver, но уже даёт гладкий путь.
    return _sample_bezier(points, samples=samples)


def sample_slider_curve(slider: SliderObject) -> List[Vec2]:
    points: List[Vec2] = [(slider.x, slider.y), *slider.control_points]

    if len(points) < 2:
        return points

    curve_type = slider.curve_type.upper()

    if curve_type == "L":
        return _sample_line(points)
    if curve_type == "B":
        return _sample_bezier(points)
    if curve_type == "P":
        return _sample_passthrough(points)

    # fallback
    return _sample_bezier(points)


@dataclass(slots=True)
class SliderPath:
    sampled_points: List[Vec2]
    cumulative_lengths: List[float]
    total_length: float

    def position_at_distance(self, distance_value: float) -> Vec2:
        if not self.sampled_points:
            return (0.0, 0.0)

        if self.total_length <= 1e-6:
            return self.sampled_points[0]

        d = max(0.0, min(self.total_length, distance_value))

        for i in range(1, len(self.cumulative_lengths)):
            prev_len = self.cumulative_lengths[i - 1]
            curr_len = self.cumulative_lengths[i]
            if d <= curr_len:
                seg_len = curr_len - prev_len
                if seg_len <= 1e-9:
                    return self.sampled_points[i]
                t = (d - prev_len) / seg_len
                return _lerp(self.sampled_points[i - 1], self.sampled_points[i], t)

        return self.sampled_points[-1]

    def position_at_progress(self, progress_0_1: float) -> Vec2:
        if self.total_length <= 1e-6:
            return self.sampled_points[0] if self.sampled_points else (0.0, 0.0)
        d = max(0.0, min(1.0, progress_0_1)) * self.total_length
        return self.position_at_distance(d)


def build_slider_path(slider: SliderObject) -> SliderPath:
    sampled = sample_slider_curve(slider)

    if not sampled:
        sampled = [(slider.x, slider.y)]

    cumulative = [0.0]
    total = 0.0

    for i in range(1, len(sampled)):
        total += _distance(sampled[i - 1], sampled[i])
        cumulative.append(total)

    # Подрезаем/растягиваем путь под pixel_length карты
    if total > 1e-6 and slider.pixel_length > 0:
        target_length = slider.pixel_length

        # Если путь длиннее нужного — обрезаем до pixel_length
        if total >= target_length:
            trimmed_points: List[Vec2] = [sampled[0]]
            trimmed_cumulative: List[float] = [0.0]

            for i in range(1, len(sampled)):
                prev_len = cumulative[i - 1]
                curr_len = cumulative[i]

                if curr_len < target_length:
                    trimmed_points.append(sampled[i])
                    trimmed_cumulative.append(curr_len)
                    continue

                seg_len = curr_len - prev_len
                if seg_len <= 1e-9:
                    trimmed_points.append(sampled[i])
                    trimmed_cumulative.append(target_length)
                    break

                t = (target_length - prev_len) / seg_len
                cut_point = _lerp(sampled[i - 1], sampled[i], t)
                trimmed_points.append(cut_point)
                trimmed_cumulative.append(target_length)
                break

            return SliderPath(
                sampled_points=trimmed_points,
                cumulative_lengths=trimmed_cumulative,
                total_length=target_length,
            )

    return SliderPath(
        sampled_points=sampled,
        cumulative_lengths=cumulative,
        total_length=total,
    )


def slider_progress_at_time(
    start_time_ms: float,
    end_time_ms: float,
    current_time_ms: float,
) -> float:
    if end_time_ms <= start_time_ms:
        return 1.0
    return max(0.0, min(1.0, (current_time_ms - start_time_ms) / (end_time_ms - start_time_ms)))


def slider_ball_position(
    path: SliderPath,
    repeats: int,
    start_time_ms: float,
    end_time_ms: float,
    current_time_ms: float,
) -> Vec2:
    if repeats <= 0:
        return path.sampled_points[0] if path.sampled_points else (0.0, 0.0)

    total_progress = slider_progress_at_time(start_time_ms, end_time_ms, current_time_ms)
    span_progress = total_progress * repeats

    span_index = min(repeats - 1, int(span_progress))
    local_progress = span_progress - span_index

    reverse = (span_index % 2) == 1
    if reverse:
        local_progress = 1.0 - local_progress

    return path.position_at_progress(local_progress)