from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from src.skills.osu.domain.math_utils import distance
from src.skills.osu.domain.models import HitObject, HitObjectType, ParsedBeatmap
from src.skills.osu.domain.osu_rules import slider_duration_ms
from src.skills.osu.replay.replay_io import load_replay
from src.skills.osu.skill_system.config import SkillExtractionConfig
from src.skills.osu.skill_system.features import build_context_signature, object_anchor, object_end_time_ms
from src.skills.osu.skill_system.models import SkillCreationSource, SkillExtractionCandidate, SkillType
from src.skills.osu.viewer.replay_models import ReplayFrame


@dataclass(slots=True)
class LocalWindowMetrics:
    frame_start: int
    frame_end: int
    duration_ms: float
    click_count: int
    hit_count: int
    miss_count: int
    slider_inside_ratio: float
    slider_follow_dist_mean: float
    slider_finish_rate: float
    slider_drop_count: int
    reverse_follow_proxy: float
    spinner_hold_ratio: float
    spinner_step_ratio: float
    mean_click_distance_px: float
    timing_median_proxy_ms: float
    mean_speed_px: float
    max_speed_px: float
    click_hold_ratio: float
    judgement_counts: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractionReport:
    candidates_found: int = 0
    rejected: int = 0
    reject_reasons: Counter = field(default_factory=Counter)
    by_type: Counter = field(default_factory=Counter)

    def reject(self, reason: str) -> None:
        self.rejected += 1
        self.reject_reasons[reason] += 1

    def accept(self, skill_type: str) -> None:
        self.candidates_found += 1
        self.by_type[skill_type] += 1


def frames_in_range(frames: list[ReplayFrame], start_ms: float, end_ms: float) -> tuple[int, int, list[ReplayFrame]]:
    selected: list[ReplayFrame] = []
    start_idx = -1
    end_idx = -1
    for idx, frame in enumerate(frames):
        if start_ms <= frame.time_ms <= end_ms:
            if start_idx < 0:
                start_idx = idx
            end_idx = idx
            selected.append(frame)
    return start_idx, end_idx, selected


def click_edges(frames: list[ReplayFrame]) -> list[ReplayFrame]:
    result = []
    prev = False
    for frame in frames:
        if frame.click_down and not prev:
            result.append(frame)
        prev = frame.click_down
    return result


def local_metrics(
    beatmap: ParsedBeatmap,
    objects: list[HitObject],
    object_start: int,
    object_end: int,
    frames: list[ReplayFrame],
) -> LocalWindowMetrics | None:
    selected_objects = objects[object_start : object_end + 1]
    if not selected_objects:
        return None

    start_ms = max(0.0, selected_objects[0].time_ms - 90.0)
    end_ms = object_end_time_ms(beatmap, selected_objects[-1]) + 120.0
    frame_start, frame_end, local_frames = frames_in_range(frames, start_ms, end_ms)
    if len(local_frames) < 3:
        return None

    clicks = click_edges(local_frames)
    judgement_counts = Counter(frame.judgement for frame in local_frames if frame.judgement != "none")
    hit_count = sum(1 for frame in local_frames if frame.score_value > 0)
    miss_count = judgement_counts.get("miss", 0)

    speeds = []
    for prev, curr in zip(local_frames, local_frames[1:], strict=False):
        dt = max(1.0, curr.time_ms - prev.time_ms)
        speeds.append(distance(prev.cursor_x, prev.cursor_y, curr.cursor_x, curr.cursor_y) * 16.6667 / dt)

    click_distances = []
    timing_proxies = []
    for click in clicks:
        nearest_obj = min(selected_objects, key=lambda obj: abs(obj.time_ms - click.time_ms))
        anchor_x, anchor_y = object_anchor(nearest_obj)
        click_distances.append(distance(click.cursor_x, click.cursor_y, anchor_x, anchor_y))
        timing_proxies.append(abs(nearest_obj.time_ms - click.time_ms))

    slider_frames = []
    slider_distances = []
    slider_inside = 0
    slider_drops = judgement_counts.get("slider_drop", 0)
    slider_finishes = judgement_counts.get("slider_finish", 0)
    reverse_quality_values = []

    for obj in selected_objects:
        if obj.kind != HitObjectType.SLIDER:
            continue
        start = obj.slider.time_ms
        end = start + slider_duration_ms(beatmap, obj.slider)
        _, _, slider_local = frames_in_range(frames, start, end)
        if not slider_local:
            continue
        slider_frames.extend(slider_local)
        follow_radius = 54.0
        # Replay frames do not store live ball position, so use a conservative proxy:
        # a successful slider window keeps cursor movement smooth and emits finish/tick judgements.
        anchor_x, anchor_y = obj.slider.x, obj.slider.y
        for frame in slider_local:
            d = distance(frame.cursor_x, frame.cursor_y, anchor_x, anchor_y)
            slider_distances.append(d)
            if d <= 140.0:
                slider_inside += 1
        if obj.slider.repeats > 1:
            reverse_quality_values.append(1.0 if slider_drops == 0 else max(0.0, 1.0 - slider_drops / max(1, obj.slider.repeats)))

    slider_inside_ratio = 0.0 if not slider_frames else slider_inside / len(slider_frames)
    slider_follow_dist_mean = 0.0 if not slider_distances else sum(slider_distances) / len(slider_distances)
    slider_finish_rate = 0.0
    if slider_finishes + slider_drops > 0:
        slider_finish_rate = slider_finishes / (slider_finishes + slider_drops)
    elif slider_frames:
        slider_finish_rate = 1.0 if slider_drops == 0 else 0.0

    spinner_frames = []
    spinner_steps = 0
    for obj in selected_objects:
        if obj.kind != HitObjectType.SPINNER:
            continue
        _, _, spin_local = frames_in_range(frames, obj.spinner.time_ms, obj.spinner.end_time_ms)
        spinner_frames.extend(spin_local)
        center_x, center_y = obj.spinner.x, obj.spinner.y
        prev_angle = None
        for frame in spin_local:
            angle = math.atan2(frame.cursor_y - center_y, frame.cursor_x - center_x)
            if prev_angle is not None:
                delta = abs(math.atan2(math.sin(angle - prev_angle), math.cos(angle - prev_angle)))
                if 0.025 <= delta <= 0.50:
                    spinner_steps += 1
            prev_angle = angle

    spinner_hold_ratio = 0.0 if not spinner_frames else sum(1 for frame in spinner_frames if frame.click_down) / len(spinner_frames)
    spinner_step_ratio = 0.0 if len(spinner_frames) <= 1 else spinner_steps / (len(spinner_frames) - 1)

    return LocalWindowMetrics(
        frame_start=frame_start,
        frame_end=frame_end,
        duration_ms=end_ms - start_ms,
        click_count=len(clicks),
        hit_count=hit_count,
        miss_count=miss_count,
        slider_inside_ratio=slider_inside_ratio,
        slider_follow_dist_mean=slider_follow_dist_mean,
        slider_finish_rate=slider_finish_rate,
        slider_drop_count=slider_drops,
        reverse_follow_proxy=0.0 if not reverse_quality_values else sum(reverse_quality_values) / len(reverse_quality_values),
        spinner_hold_ratio=spinner_hold_ratio,
        spinner_step_ratio=spinner_step_ratio,
        mean_click_distance_px=0.0 if not click_distances else sum(click_distances) / len(click_distances),
        timing_median_proxy_ms=0.0 if not timing_proxies else sorted(timing_proxies)[len(timing_proxies) // 2],
        mean_speed_px=0.0 if not speeds else sum(speeds) / len(speeds),
        max_speed_px=0.0 if not speeds else max(speeds),
        click_hold_ratio=sum(1 for frame in local_frames if frame.click_down) / len(local_frames),
        judgement_counts=dict(judgement_counts),
    )


def sequence_features(
    beatmap: ParsedBeatmap,
    objects: list[HitObject],
    object_start: int,
    object_end: int,
    metrics: LocalWindowMetrics,
) -> dict[str, float | int | str]:
    selected = objects[object_start : object_end + 1]
    anchors = [object_anchor(obj) for obj in selected]
    spacings = [
        distance(anchors[i - 1][0], anchors[i - 1][1], anchors[i][0], anchors[i][1])
        for i in range(1, len(anchors))
    ]
    duration = max(1.0, object_end_time_ms(beatmap, selected[-1]) - selected[0].time_ms)
    slider_count = sum(1 for obj in selected if obj.kind == HitObjectType.SLIDER)
    circle_count = sum(1 for obj in selected if obj.kind == HitObjectType.CIRCLE)
    spinner_count = sum(1 for obj in selected if obj.kind == HitObjectType.SPINNER)
    reverse_count = sum(
        max(0, obj.slider.repeats - 1)
        for obj in selected
        if obj.kind == HitObjectType.SLIDER
    )
    return {
        "object_count": len(selected),
        "duration_ms": duration,
        "density_per_second": len(selected) * 1000.0 / duration,
        "mean_spacing_px": 0.0 if not spacings else sum(spacings) / len(spacings),
        "max_spacing_px": 0.0 if not spacings else max(spacings),
        "slider_count": slider_count,
        "circle_count": circle_count,
        "spinner_count": spinner_count,
        "reverse_count": reverse_count,
        "hit_count": metrics.hit_count,
        "miss_count": metrics.miss_count,
        "click_count": metrics.click_count,
        "slider_inside_ratio": metrics.slider_inside_ratio,
        "slider_follow_dist_mean": metrics.slider_follow_dist_mean,
        "slider_finish_rate": metrics.slider_finish_rate,
        "reverse_follow_proxy": metrics.reverse_follow_proxy,
        "spinner_hold_ratio": metrics.spinner_hold_ratio,
        "spinner_step_ratio": metrics.spinner_step_ratio,
        "timing_median_proxy_ms": metrics.timing_median_proxy_ms,
        "mean_click_distance_px": metrics.mean_click_distance_px,
        "mean_speed_px": metrics.mean_speed_px,
        "max_speed_px": metrics.max_speed_px,
        "click_hold_ratio": metrics.click_hold_ratio,
    }


def action_summary_from_frames(frames: list[ReplayFrame], metrics: LocalWindowMetrics, cursor_speed_scale: float = 14.0) -> dict[str, float | int | str]:
    if metrics.frame_start < 0 or metrics.frame_end < metrics.frame_start:
        return {}
    local = frames[metrics.frame_start : metrics.frame_end + 1]
    if len(local) < 2:
        return {}
    dxs = []
    dys = []
    speeds = []
    click_frames = 0
    for prev, curr in zip(local, local[1:], strict=False):
        dx = (curr.cursor_x - prev.cursor_x) / cursor_speed_scale
        dy = (curr.cursor_y - prev.cursor_y) / cursor_speed_scale
        dxs.append(max(-1.0, min(1.0, dx)))
        dys.append(max(-1.0, min(1.0, dy)))
        speeds.append(math.hypot(dx, dy))
        if curr.click_down:
            click_frames += 1
    return {
        "mean_dx": sum(dxs) / len(dxs),
        "mean_dy": sum(dys) / len(dys),
        "mean_action_speed": sum(speeds) / len(speeds),
        "max_action_speed": max(speeds),
        "click_hold_ratio": click_frames / max(1, len(local) - 1),
        "mean_click_strength": 0.82 if click_frames > 0 else 0.10,
        "follow_stability": metrics.slider_inside_ratio,
        "entry_distance_px": metrics.mean_click_distance_px,
        "exit_speed_px": metrics.mean_speed_px,
    }


def quality_scores(skill_type: str, features: dict[str, float | int | str], cfg: SkillExtractionConfig) -> tuple[float, float, float, float, str]:
    miss_count = float(features.get("miss_count", 0.0))
    hit_count = float(features.get("hit_count", 0.0))
    object_count = max(1.0, float(features.get("object_count", 1.0)))
    miss_penalty = min(0.45, miss_count / object_count)
    timing_penalty = min(0.20, float(features.get("timing_median_proxy_ms", 0.0)) / 500.0)
    click_noise = min(0.20, max(0.0, float(features.get("click_count", 0.0)) - object_count - 2.0) / 18.0)
    noise_penalty = miss_penalty + timing_penalty + click_noise

    base_hit_quality = min(1.0, hit_count / object_count)
    slider_quality = float(features.get("slider_inside_ratio", 0.0))
    finish_quality = float(features.get("slider_finish_rate", 0.0))
    dpx = float(features.get("slider_follow_dist_mean", 0.0))
    dpx_quality = 1.0 if dpx <= 1.0 else max(0.0, 1.0 - dpx / 120.0)

    if skill_type in {SkillType.SLIDER_FOLLOW.value, SkillType.SLIDER_AIM.value, SkillType.KICK_SLIDERS.value}:
        extraction = 0.40 * slider_quality + 0.25 * finish_quality + 0.20 * dpx_quality + 0.15 * base_hit_quality
        if slider_quality < cfg.slider_min_inside_ratio or dpx > cfg.slider_max_dpx * 2.2:
            return extraction, slider_quality, dpx_quality, noise_penalty, "slider_quality_below_threshold"
    elif skill_type == SkillType.REVERSE_SLIDER.value:
        reverse_quality = float(features.get("reverse_follow_proxy", 0.0))
        extraction = 0.35 * slider_quality + 0.30 * reverse_quality + 0.20 * finish_quality + 0.15 * base_hit_quality
        if reverse_quality < cfg.reverse_min_follow_ratio:
            return extraction, reverse_quality, dpx_quality, noise_penalty, "reverse_quality_below_threshold"
    elif skill_type == SkillType.SPINNER_CONTROL.value:
        hold = float(features.get("spinner_hold_ratio", 0.0))
        step = float(features.get("spinner_step_ratio", 0.0))
        extraction = 0.45 * hold + 0.40 * step + 0.15 * base_hit_quality
        if hold < cfg.spinner_min_hold_ratio or step < cfg.spinner_min_step_ratio:
            return extraction, min(hold, step), 0.65, noise_penalty, "spinner_quality_below_threshold"
    else:
        click_distance_quality = max(0.0, 1.0 - float(features.get("mean_click_distance_px", 0.0)) / 150.0)
        timing_quality = max(0.0, 1.0 - float(features.get("timing_median_proxy_ms", 0.0)) / 180.0)
        extraction = 0.38 * base_hit_quality + 0.32 * click_distance_quality + 0.30 * timing_quality
        if float(features.get("timing_median_proxy_ms", 0.0)) > cfg.chain_max_timing_median_ms * 2.0:
            return extraction, timing_quality, click_distance_quality, noise_penalty, "timing_noise"

    stability = max(0.0, min(1.0, extraction - noise_penalty * 0.40))
    transfer = max(0.0, min(1.0, 0.55 + 0.25 * base_hit_quality + 0.20 * min(1.0, object_count / 6.0) - noise_penalty))
    reason = "" if extraction >= cfg.min_extraction_score else "extraction_score_below_threshold"
    return extraction, stability, transfer, noise_penalty, reason


def infer_skill_types(objects: list[HitObject], object_start: int, object_end: int) -> list[str]:
    selected = objects[object_start : object_end + 1]
    kinds = [obj.kind for obj in selected]
    skill_types: list[str] = []
    if any(kind == HitObjectType.SPINNER for kind in kinds):
        skill_types.append(SkillType.SPINNER_CONTROL.value)
    slider_objs = [obj for obj in selected if obj.kind == HitObjectType.SLIDER]
    if slider_objs:
        skill_types.append(SkillType.SLIDER_FOLLOW.value)
        skill_types.append(SkillType.SLIDER_AIM.value)
        if any(obj.slider.repeats > 1 for obj in slider_objs):
            skill_types.append(SkillType.REVERSE_SLIDER.value)
        if len(selected) <= 3 and len(slider_objs) >= 1:
            skill_types.append(SkillType.KICK_SLIDERS.value)
    circle_count = sum(1 for kind in kinds if kind == HitObjectType.CIRCLE)
    if 2 <= len(selected) <= 4 and circle_count >= 2:
        skill_types.append(SkillType.SHORT_CHAIN.value)
    if len(selected) == 2 and circle_count == 2:
        skill_types.append(SkillType.SIMPLE_DOUBLE.value)
        skill_types.append(SkillType.SIMPLE_JUMP.value)
    if len(selected) == 3 and circle_count >= 2:
        skill_types.append(SkillType.TRIPLETS.value)
    if 3 <= len(selected) <= 6 and circle_count >= 3:
        skill_types.append(SkillType.BURST.value)
    return skill_types


def make_candidate(
    beatmap: ParsedBeatmap,
    frames: list[ReplayFrame],
    replay_id: str,
    checkpoint_id: str,
    object_start: int,
    object_end: int,
    skill_type: str,
    metrics: LocalWindowMetrics,
    cfg: SkillExtractionConfig,
) -> SkillExtractionCandidate:
    features = sequence_features(beatmap, beatmap.hit_objects, object_start, object_end, metrics)
    extraction_score, stability_score, transfer_score, noise_penalty, reject_reason = quality_scores(skill_type, features, cfg)
    source = SkillCreationSource(
        map_id=f"{beatmap.artist} - {beatmap.title} [{beatmap.version}]",
        replay_id=replay_id,
        checkpoint_id=checkpoint_id,
        frame_start=metrics.frame_start,
        frame_end=metrics.frame_end,
        object_start=object_start,
        object_end=object_end,
    )
    action_summary = action_summary_from_frames(frames, metrics)
    return SkillExtractionCandidate(
        skill_type=skill_type,
        creation_source=source,
        context_signature=build_context_signature(beatmap, beatmap.hit_objects, object_start, object_end),
        pattern_features=features,
        action_summary=action_summary,
        applicability_conditions={
            "max_risk": 0.68,
            "max_spacing_px": features.get("max_spacing_px", 0.0),
            "min_confidence": cfg.min_confidence,
            "local_window_ms": metrics.duration_ms,
        },
        extraction_score=extraction_score,
        stability_score=stability_score,
        transfer_potential_score=transfer_score,
        noise_penalty=noise_penalty,
        reject_reason=reject_reason,
        tags=["phase10", "micro_skill"],
    )


class SkillExtractor:
    def __init__(self, cfg: SkillExtractionConfig | None = None) -> None:
        self.cfg = cfg or SkillExtractionConfig()

    def extract_from_replay(
        self,
        beatmap: ParsedBeatmap,
        replay_path: str | Path,
        checkpoint_id: str = "",
    ) -> tuple[list[SkillExtractionCandidate], ExtractionReport]:
        frames = load_replay(replay_path)
        replay_id = str(Path(replay_path).name)
        return self.extract_from_frames(beatmap, frames, replay_id=replay_id, checkpoint_id=checkpoint_id)

    def extract_from_frames(
        self,
        beatmap: ParsedBeatmap,
        frames: list[ReplayFrame],
        replay_id: str,
        checkpoint_id: str = "",
    ) -> tuple[list[SkillExtractionCandidate], ExtractionReport]:
        candidates: list[SkillExtractionCandidate] = []
        report = ExtractionReport()
        objects = beatmap.hit_objects

        windows: set[tuple[int, int]] = set()
        for idx, obj in enumerate(objects):
            windows.add((idx, idx))
            for length in (2, 3, 4, 5, 6):
                end = idx + length - 1
                if end < len(objects):
                    windows.add((idx, end))

        for object_start, object_end in sorted(windows):
            metrics = local_metrics(beatmap, objects, object_start, object_end, frames)
            if metrics is None:
                report.reject("empty_or_short_window")
                continue
            if metrics.miss_count > max(1, (object_end - object_start + 1) // 2):
                report.reject("too_many_misses")
                continue

            skill_types = infer_skill_types(objects, object_start, object_end)
            if not skill_types:
                report.reject("unsupported_pattern")
                continue

            for skill_type in skill_types:
                candidate = make_candidate(
                    beatmap=beatmap,
                    frames=frames,
                    replay_id=replay_id,
                    checkpoint_id=checkpoint_id,
                    object_start=object_start,
                    object_end=object_end,
                    skill_type=skill_type,
                    metrics=metrics,
                    cfg=self.cfg,
                )
                if candidate.reject_reason:
                    report.reject(candidate.reject_reason)
                    continue
                if candidate.confidence < self.cfg.min_confidence:
                    report.reject("confidence_below_threshold")
                    continue
                candidates.append(candidate)
                report.accept(skill_type)

        return candidates, report


def summarize_candidates(candidates: list[SkillExtractionCandidate]) -> dict[str, dict[str, float]]:
    by_type: dict[str, list[SkillExtractionCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_type[candidate.skill_type].append(candidate)
    summary: dict[str, dict[str, float]] = {}
    for skill_type, items in by_type.items():
        summary[skill_type] = {
            "count": len(items),
            "avg_confidence": sum(item.confidence for item in items) / len(items),
            "avg_extraction_score": sum(item.extraction_score for item in items) / len(items),
        }
    return summary
