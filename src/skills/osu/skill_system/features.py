from __future__ import annotations

import math
from collections.abc import Sequence

from src.skills.osu.domain.math_utils import distance
from src.skills.osu.domain.models import HitObject, HitObjectType, ParsedBeatmap
from src.skills.osu.domain.osu_rules import base_timing_point_at, slider_duration_ms
from src.skills.osu.env.types import OsuObservation
from src.skills.osu.skill_system.models import SkillContextSignature


def bucket(value: float, limits: Sequence[float], labels: Sequence[str]) -> str:
    for limit, label in zip(limits, labels, strict=False):
        if value <= limit:
            return label
    return labels[-1]


def object_kind_name(obj: HitObject) -> str:
    if obj.kind == HitObjectType.CIRCLE:
        return "circle"
    if obj.kind == HitObjectType.SLIDER:
        return "slider"
    return "spinner"


def object_anchor(obj: HitObject) -> tuple[float, float]:
    if obj.kind == HitObjectType.CIRCLE:
        return obj.circle.x, obj.circle.y
    if obj.kind == HitObjectType.SLIDER:
        return obj.slider.x, obj.slider.y
    return obj.spinner.x, obj.spinner.y


def object_end_time_ms(beatmap: ParsedBeatmap, obj: HitObject) -> float:
    if obj.kind == HitObjectType.CIRCLE:
        return obj.circle.time_ms
    if obj.kind == HitObjectType.SLIDER:
        return obj.slider.time_ms + slider_duration_ms(beatmap, obj.slider)
    return obj.spinner.end_time_ms


def angle_between(prev_obj: HitObject | None, obj: HitObject, next_obj: HitObject | None) -> float:
    if prev_obj is None or next_obj is None:
        return 0.0
    ax, ay = object_anchor(prev_obj)
    bx, by = object_anchor(obj)
    cx, cy = object_anchor(next_obj)
    v1 = (ax - bx, ay - by)
    v2 = (cx - bx, cy - by)
    n1 = math.hypot(v1[0], v1[1])
    n2 = math.hypot(v2[0], v2[1])
    if n1 < 1e-6 or n2 < 1e-6:
        return 0.0
    dot = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(dot))


def build_context_signature(
    beatmap: ParsedBeatmap,
    objects: Sequence[HitObject],
    object_start: int,
    object_end: int,
) -> SkillContextSignature:
    selected = list(objects[object_start : object_end + 1])
    if not selected:
        raise ValueError("cannot build context signature for empty object sequence")

    start_time = selected[0].time_ms
    end_time = object_end_time_ms(beatmap, selected[-1])
    duration = max(1.0, end_time - start_time)
    density_per_second = len(selected) * 1000.0 / duration

    anchors = [object_anchor(obj) for obj in selected]
    spacings = [
        distance(anchors[i - 1][0], anchors[i - 1][1], anchors[i][0], anchors[i][1])
        for i in range(1, len(anchors))
    ]
    mean_spacing = 0.0 if not spacings else sum(spacings) / len(spacings)

    base_tp = base_timing_point_at(beatmap, start_time)
    bpm = 0.0 if base_tp.beat_length <= 0 else 60000.0 / base_tp.beat_length

    slider_lengths = [
        obj.slider.pixel_length
        for obj in selected
        if obj.kind == HitObjectType.SLIDER and obj.slider is not None
    ]
    mean_slider_length = 0.0 if not slider_lengths else sum(slider_lengths) / len(slider_lengths)
    reverse_count = sum(
        max(0, obj.slider.repeats - 1)
        for obj in selected
        if obj.kind == HitObjectType.SLIDER and obj.slider is not None
    )

    mid_index = object_start + len(selected) // 2
    prev_obj = objects[mid_index - 1] if mid_index > 0 else None
    mid_obj = objects[mid_index]
    next_obj = objects[mid_index + 1] if mid_index + 1 < len(objects) else None
    angle = angle_between(prev_obj, mid_obj, next_obj)

    previous_gap = 9999.0
    if object_start > 0:
        previous_gap = max(0.0, selected[0].time_ms - object_end_time_ms(beatmap, objects[object_start - 1]))
    next_gap = 9999.0
    if object_end + 1 < len(objects):
        next_gap = max(0.0, objects[object_end + 1].time_ms - object_end_time_ms(beatmap, selected[-1]))

    return SkillContextSignature(
        object_sequence=tuple(object_kind_name(obj) for obj in selected),
        local_density_bucket=bucket(density_per_second, [2.2, 4.5, 7.5], ["low", "mid", "high", "burst"]),
        bpm_bucket=bucket(bpm, [105.0, 140.0, 180.0], ["slow", "mid", "fast", "very_fast"]),
        spacing_bucket=bucket(mean_spacing, [70.0, 140.0, 230.0], ["tight", "medium", "wide", "jump"]),
        angle_bucket=bucket(angle, [35.0, 80.0, 135.0], ["straight", "soft_angle", "angle", "sharp"]),
        slider_length_bucket=bucket(mean_slider_length, [0.1, 160.0, 340.0], ["none", "short", "medium", "long"]),
        reverse_count=int(reverse_count),
        approach_difficulty_bucket=bucket(beatmap.difficulty.ar, [5.0, 7.0, 8.5], ["low", "mid", "high", "very_high"]),
        timing_pressure_bucket=bucket(duration / len(selected), [130.0, 220.0, 380.0], ["very_tight", "tight", "medium", "relaxed"]),
        previous_relation_bucket=bucket(previous_gap, [90.0, 220.0, 500.0], ["overlap", "linked", "near", "separate"]),
        next_relation_bucket=bucket(next_gap, [90.0, 220.0, 500.0], ["overlap", "linked", "near", "separate"]),
    )


def runtime_context_signature(obs: OsuObservation) -> SkillContextSignature:
    active = [item for item in obs.upcoming if item.kind_id >= 0]
    if not active:
        object_sequence = ("none",)
        mean_spacing = 0.0
        mean_time = 9999.0
    else:
        names = {0: "circle", 1: "slider", 2: "spinner"}
        object_sequence = tuple(names.get(item.kind_id, "none") for item in active[:4])
        mean_spacing = sum(item.distance_to_cursor for item in active[:4]) / max(1, min(4, len(active)))
        mean_time = sum(abs(item.time_to_hit_ms) for item in active[:4]) / max(1, min(4, len(active)))

    primary = active[0] if active else None
    slider_length_bucket = "none"
    reverse_count = 0
    if obs.slider.active_slider > 0.5 or (primary is not None and primary.kind_id == 1):
        slider_length_bucket = "medium"
        reverse_count = 1 if abs(obs.slider.tangent_x) + abs(obs.slider.tangent_y) > 0.1 else 0

    return SkillContextSignature(
        object_sequence=object_sequence,
        local_density_bucket=bucket(len(active), [1.0, 3.0, 5.0], ["low", "mid", "high", "burst"]),
        bpm_bucket="mid",
        spacing_bucket=bucket(mean_spacing, [70.0, 140.0, 230.0], ["tight", "medium", "wide", "jump"]),
        angle_bucket="soft_angle",
        slider_length_bucket=slider_length_bucket,
        reverse_count=reverse_count,
        approach_difficulty_bucket="mid",
        timing_pressure_bucket=bucket(mean_time, [130.0, 220.0, 380.0], ["very_tight", "tight", "medium", "relaxed"]),
        previous_relation_bucket="near",
        next_relation_bucket="near",
    )


def signature_similarity(a: SkillContextSignature, b: SkillContextSignature) -> float:
    score = 0.0
    total = 0.0

    seq_a = a.object_sequence
    seq_b = b.object_sequence
    max_len = max(len(seq_a), len(seq_b), 1)
    seq_matches = sum(1 for left, right in zip(seq_a, seq_b, strict=False) if left == right)
    score += 2.0 * (seq_matches / max_len)
    total += 2.0

    fields = [
        "local_density_bucket",
        "bpm_bucket",
        "spacing_bucket",
        "angle_bucket",
        "slider_length_bucket",
        "approach_difficulty_bucket",
        "timing_pressure_bucket",
        "previous_relation_bucket",
        "next_relation_bucket",
    ]
    for field in fields:
        score += 1.0 if getattr(a, field) == getattr(b, field) else 0.0
        total += 1.0

    reverse_delta = abs(a.reverse_count - b.reverse_count)
    score += max(0.0, 1.0 - reverse_delta / 3.0)
    total += 1.0

    return score / total
