from __future__ import annotations

from src.skills.osu.domain.models import ParsedBeatmap, SliderObject, TimingPoint


def ar_to_preempt_ms(ar: float) -> float:
    if ar < 5.0:
        return 1200.0 + 600.0 * (5.0 - ar) / 5.0
    return 1200.0 - 750.0 * (ar - 5.0) / 5.0


def hit_window_300(od: float) -> float:
    return 79.5 - 6.0 * od


def hit_window_100(od: float) -> float:
    return 139.5 - 8.0 * od


def hit_window_50(od: float) -> float:
    return 199.5 - 10.0 * od


def timing_point_at(beatmap: ParsedBeatmap, time_ms: float) -> TimingPoint:
    chosen = beatmap.timing_points[0]
    for tp in beatmap.timing_points:
        if tp.time_ms <= time_ms:
            chosen = tp
        else:
            break
    return chosen


def inherited_timing_point_at(beatmap: ParsedBeatmap, time_ms: float) -> TimingPoint | None:
    chosen = None
    for tp in beatmap.timing_points:
        if tp.time_ms > time_ms:
            break
        if not tp.uninherited:
            chosen = tp
    return chosen


def base_timing_point_at(beatmap: ParsedBeatmap, time_ms: float) -> TimingPoint:
    chosen = beatmap.timing_points[0]
    for tp in beatmap.timing_points:
        if tp.time_ms > time_ms:
            break
        if tp.uninherited:
            chosen = tp
    return chosen


def slider_duration_ms(beatmap: ParsedBeatmap, slider: SliderObject) -> float:
    base_tp = base_timing_point_at(beatmap, slider.time_ms)
    inherited_tp = inherited_timing_point_at(beatmap, slider.time_ms)

    sv_multiplier = 1.0 if inherited_tp is None else inherited_tp.slider_velocity_multiplier

    beats = (slider.pixel_length * slider.repeats) / (
        100.0 * beatmap.difficulty.slider_multiplier * sv_multiplier
    )
    return beats * base_tp.beat_length


def slider_span_duration_ms(beatmap: ParsedBeatmap, slider: SliderObject) -> float:
    total = slider_duration_ms(beatmap, slider)
    return total / max(1, slider.repeats)