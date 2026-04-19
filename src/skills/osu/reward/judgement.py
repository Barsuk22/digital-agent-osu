from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from src.skills.osu.domain.math_utils import distance, osu_circle_radius
from src.skills.osu.domain.models import HitObject, HitObjectType, ParsedBeatmap, SliderObject
from src.skills.osu.domain.osu_rules import (
    hit_window_100,
    hit_window_300,
    hit_window_50,
    slider_duration_ms,
    slider_span_duration_ms,
)
from src.skills.osu.domain.slider_path import (
    build_slider_path,
    slider_ball_position,
    slider_local_progress,
    slider_progress_at_time,
)


SPINNER_CENTER_X = 256.0
SPINNER_CENTER_Y = 192.0
SPINNER_TARGET_RADIUS = 76.0
SPINNER_GOOD_RADIUS_TOLERANCE = 26.0
SPINNER_MIN_VALID_RADIUS = 42.0
SPINNER_MAX_VALID_RADIUS = 125.0
SPINNER_MAX_DELTA_PER_STEP = 0.50
SPINNER_MIN_DELTA_PER_STEP = 0.025
SPINNER_CLEAR_MIN_SPINS = 2.0
SPINNER_PARTIAL_MIN_SPINS = 0.9


@dataclass(slots=True)
class JudgeResult:
    reward: float = 0.0
    score_value: int = 0
    judgement: str = "none"
    popup_x: float | None = None
    popup_y: float | None = None


class OsuJudge:
    def __init__(self, beatmap: ParsedBeatmap) -> None:
        self.beatmap = beatmap
        self.objects = beatmap.hit_objects
        self.cs = beatmap.difficulty.cs
        self.od = beatmap.difficulty.od
        self.radius = osu_circle_radius(self.cs)

        self.object_index = 0
        self.combo = 0
        self.max_combo = 0
        self.hit_count = 0
        self.miss_count = 0
        self.score_sum = 0
        self.score_max_sum = 0

        self.active_slider: Optional[dict] = None
        self.active_spinner: Optional[dict] = None

    def reset(self) -> None:
        self.object_index = 0
        self.combo = 0
        self.max_combo = 0
        self.hit_count = 0
        self.miss_count = 0
        self.score_sum = 0
        self.score_max_sum = 0
        self.active_slider = None
        self.active_spinner = None

    def accuracy(self) -> float:
        if self.score_max_sum <= 0:
            return 1.0
        return self.score_sum / self.score_max_sum

    def is_finished(self, time_ms: float) -> bool:
        if self.object_index < len(self.objects):
            return False
        if self.active_slider is not None:
            return False
        if self.active_spinner is not None:
            return False
        return True

    def peek_upcoming_objects(self, time_ms: float, count: int):
        result = []
        idx = self.object_index
        while idx < len(self.objects) and len(result) < count:
            result.append(self.objects[idx])
            idx += 1
        return result

    def update(
        self,
        time_ms: float,
        cursor_x: float,
        cursor_y: float,
        just_pressed: bool,
        click_down: bool,
        dt_ms: float,
    ) -> JudgeResult:
        result = JudgeResult()

        self._expire_missed_objects(time_ms, result)
        self._update_active_slider(time_ms, cursor_x, cursor_y, click_down, dt_ms, result)
        self._update_active_spinner(time_ms, cursor_x, cursor_y, click_down, dt_ms, result)

        if self.object_index >= len(self.objects):
            return result

        obj = self.objects[self.object_index]

        if obj.kind == HitObjectType.CIRCLE and just_pressed:
            return self._try_hit_circle(obj, time_ms, cursor_x, cursor_y)

        if obj.kind == HitObjectType.SLIDER and just_pressed:
            return self._try_start_slider(obj, time_ms, cursor_x, cursor_y)

        if obj.kind == HitObjectType.SPINNER:
            return self._try_start_spinner(obj, time_ms)

        return result

    def current_slider_ball_position(self, time_ms: float) -> tuple[float, float] | None:
        if self.active_slider is None:
            return None

        return slider_ball_position(
            path=self.active_slider["path"],
            repeats=self.active_slider["slider"].repeats,
            start_time_ms=self.active_slider["start_time"],
            end_time_ms=self.active_slider["end_time"],
            current_time_ms=time_ms,
        )

    def active_slider_state(self, time_ms: float, cursor_x: float, cursor_y: float) -> dict:
        if self.active_slider is None:
            return {
                "active_slider": False,
                "progress": 0.0,
                "target_x": 0.0,
                "target_y": 0.0,
                "distance_to_target": 0.0,
                "distance_to_ball": 0.0,
                "inside_follow": False,
                "head_hit": False,
                "time_to_end_ms": 0.0,
                "tangent_x": 0.0,
                "tangent_y": 0.0,
                "follow_radius": self.radius * 1.65,
            }

        slider: SliderObject = self.active_slider["slider"]
        path = self.active_slider["path"]
        start_time = self.active_slider["start_time"]
        end_time = self.active_slider["end_time"]
        progress = slider_progress_at_time(start_time, end_time, time_ms)
        local_progress, _ = slider_local_progress(progress, slider.repeats)
        ball_x, ball_y = path.position_at_progress(local_progress)
        tangent_x, tangent_y = path.tangent_at_progress(local_progress)
        if slider.repeats > 0 and int(min(slider.repeats - 1, progress * slider.repeats)) % 2 == 1:
            tangent_x = -tangent_x
            tangent_y = -tangent_y
        follow_radius = self.radius * 1.65
        dist = distance(cursor_x, cursor_y, ball_x, ball_y)

        return {
            "active_slider": True,
            "progress": progress,
            "target_x": ball_x,
            "target_y": ball_y,
            "distance_to_target": dist,
            "distance_to_ball": dist,
            "inside_follow": dist <= follow_radius,
            "head_hit": bool(self.active_slider.get("head_hit", False)),
            "time_to_end_ms": max(0.0, end_time - time_ms),
            "tangent_x": tangent_x,
            "tangent_y": tangent_y,
            "follow_radius": follow_radius,
        }

    def active_spinner_state(self, time_ms: float, cursor_x: float, cursor_y: float) -> dict:
        center_x, center_y = SPINNER_CENTER_X, SPINNER_CENTER_Y
        target_radius = SPINNER_TARGET_RADIUS
        dx = cursor_x - center_x
        dy = cursor_y - center_y
        dist = math.hypot(dx, dy)
        angle = math.atan2(dy, dx) if dist > 1e-6 else 0.0

        if self.active_spinner is None:
            return {
                "active_spinner": False,
                "progress": 0.0,
                "spins": 0.0,
                "target_spins": SPINNER_CLEAR_MIN_SPINS,
                "time_to_end_ms": 0.0,
                "center_x": center_x,
                "center_y": center_y,
                "distance_to_center": dist,
                "radius_error": abs(dist - target_radius),
                "angle_sin": math.sin(angle),
                "angle_cos": math.cos(angle),
                "angular_velocity": 0.0,
            }

        start_time = float(self.active_spinner["start_time"])
        end_time = float(self.active_spinner["end_time"])
        duration = max(1.0, end_time - start_time)
        progress = max(0.0, min(1.0, (time_ms - start_time) / duration))
        spins = float(self.active_spinner["spin_progress"]) / (2.0 * math.pi)
        target_spins = float(self.active_spinner.get("target_spins", SPINNER_CLEAR_MIN_SPINS))
        angular_velocity = float(self.active_spinner.get("last_angular_velocity", 0.0))

        return {
            "active_spinner": True,
            "progress": progress,
            "spins": spins,
            "target_spins": target_spins,
            "time_to_end_ms": max(0.0, end_time - time_ms),
            "center_x": center_x,
            "center_y": center_y,
            "distance_to_center": dist,
            "radius_error": abs(dist - target_radius),
            "angle_sin": math.sin(angle),
            "angle_cos": math.cos(angle),
            "angular_velocity": angular_velocity,
        }

    def _object_anchor(self, obj: HitObject) -> tuple[float, float]:
        if obj.kind == HitObjectType.CIRCLE:
            return obj.circle.x, obj.circle.y
        if obj.kind == HitObjectType.SLIDER:
            return obj.slider.x, obj.slider.y
        return obj.spinner.x, obj.spinner.y

    def _expire_missed_objects(self, time_ms: float, result: JudgeResult) -> None:
        while self.object_index < len(self.objects):
            obj = self.objects[self.object_index]

            if obj.kind == HitObjectType.SPINNER:
                break
            if obj.kind == HitObjectType.SLIDER and self.active_slider is not None:
                break

            miss_deadline = obj.time_ms + hit_window_50(self.od)

            if time_ms <= miss_deadline:
                break

            if obj.kind in (HitObjectType.CIRCLE, HitObjectType.SLIDER):
                self._register_miss(result, obj)
                self.object_index += 1
                continue

            break

    def _try_hit_circle(
        self,
        obj: HitObject,
        time_ms: float,
        cursor_x: float,
        cursor_y: float,
    ) -> JudgeResult:
        timing_error = abs(time_ms - obj.circle.time_ms)
        dist = distance(cursor_x, cursor_y, obj.circle.x, obj.circle.y)

        if dist > self.radius:
            return JudgeResult(
                reward=-0.15,
                score_value=0,
                judgement="click_outside",
                popup_x=obj.circle.x,
                popup_y=obj.circle.y,
            )

        if timing_error <= hit_window_300(self.od):
            self.object_index += 1
            return self._register_scored_hit(300, "300", obj.circle.x, obj.circle.y)
        if timing_error <= hit_window_100(self.od):
            self.object_index += 1
            return self._register_scored_hit(100, "100", obj.circle.x, obj.circle.y)
        if timing_error <= hit_window_50(self.od):
            self.object_index += 1
            return self._register_scored_hit(50, "50", obj.circle.x, obj.circle.y)

        return JudgeResult(
            reward=-0.05,
            score_value=0,
            judgement="bad_timing",
            popup_x=obj.circle.x,
            popup_y=obj.circle.y,
        )

    def _try_start_slider(
        self,
        obj: HitObject,
        time_ms: float,
        cursor_x: float,
        cursor_y: float,
    ) -> JudgeResult:
        slider = obj.slider
        timing_error = abs(time_ms - slider.time_ms)
        dist = distance(cursor_x, cursor_y, slider.x, slider.y)

        if dist > self.radius:
            return JudgeResult(
                reward=-0.15,
                score_value=0,
                judgement="slider_head_outside",
                popup_x=slider.x,
                popup_y=slider.y,
            )

        if timing_error > hit_window_50(self.od):
            return JudgeResult(
                reward=-0.05,
                score_value=0,
                judgement="slider_bad_timing",
                popup_x=slider.x,
                popup_y=slider.y,
            )

        total_duration_ms = slider_duration_ms(self.beatmap, slider)
        span_duration_ms = slider_span_duration_ms(self.beatmap, slider)
        path = build_slider_path(slider)

        tick_times = self._build_slider_tick_times(slider, span_duration_ms)

        self.active_slider = {
            "slider": slider,
            "path": path,
            "start_time": slider.time_ms,
            "end_time": slider.time_ms + total_duration_ms,
            "tick_times": tick_times,
            "next_tick_index": 0,
            "tick_hits": 0,
            "tick_misses": 0,
            "head_hit": True,
            "follow_samples": 0,
            "inside_samples": 0,
            "follow_dist_total": 0.0,
            "lost_follow_count": 0,
            "last_inside": True,
            "last_progress": 0.0,
        }

        self.object_index += 1

        head_value = self._score_value_from_timing_error(timing_error)
        hit = self._register_scored_hit(head_value, "slider_head", slider.x, slider.y)
        hit.reward += 0.15
        return hit

    def _build_slider_tick_times(self, slider: SliderObject, span_duration_ms: float) -> list[float]:
        tick_times: list[float] = []

        tick_rate = max(0.0, self.beatmap.difficulty.slider_tick_rate)
        if tick_rate <= 0.0:
            return tick_times

        base_tp = self.beatmap.timing_points[0]
        for tp in self.beatmap.timing_points:
            if tp.time_ms > slider.time_ms:
                break
            if tp.uninherited:
                base_tp = tp

        tick_interval = abs(base_tp.beat_length) / tick_rate
        if tick_interval <= 1e-6:
            return tick_times

        ticks_per_span = max(0, int(math.floor((span_duration_ms - 1.0) / tick_interval)))
        if ticks_per_span <= 0:
            return tick_times

        for span_idx in range(slider.repeats):
            span_start = slider.time_ms + span_idx * span_duration_ms
            for i in range(1, ticks_per_span + 1):
                tick_time = span_start + i * tick_interval
                if tick_time < span_start + span_duration_ms - 1.0:
                    tick_times.append(tick_time)

        return tick_times

    def _update_active_slider(
        self,
        time_ms: float,
        cursor_x: float,
        cursor_y: float,
        click_down: bool,
        dt_ms: float,
        result: JudgeResult,
    ) -> None:
        if self.active_slider is None:
            return

        slider: SliderObject = self.active_slider["slider"]
        path = self.active_slider["path"]
        start_time = self.active_slider["start_time"]
        end_time = self.active_slider["end_time"]

        ball_x, ball_y = slider_ball_position(
            path=path,
            repeats=slider.repeats,
            start_time_ms=start_time,
            end_time_ms=end_time,
            current_time_ms=time_ms,
        )

        dist = distance(cursor_x, cursor_y, ball_x, ball_y)
        follow_radius = self.radius * 1.65
        progress = slider_progress_at_time(start_time, end_time, time_ms)
        inside = click_down and dist <= follow_radius

        self.active_slider["follow_samples"] += 1
        self.active_slider["follow_dist_total"] += dist
        if inside:
            self.active_slider["inside_samples"] += 1
        elif self.active_slider.get("last_inside", True) and time_ms > start_time + dt_ms * 0.5:
            self.active_slider["lost_follow_count"] += 1
        self.active_slider["last_inside"] = inside

        if time_ms < end_time:
            step_scale = dt_ms / 16.6667
            closeness = max(0.0, 1.0 - dist / max(1.0, follow_radius))
            progress_gain = max(0.0, progress - float(self.active_slider.get("last_progress", 0.0)))
            if inside:
                result.reward += (0.018 + 0.016 * closeness) * step_scale
                result.reward += min(0.035, progress_gain * 0.45)
                if result.judgement == "none":
                    result.judgement = "slider_follow"
                    result.popup_x = ball_x
                    result.popup_y = ball_y
            else:
                result.reward -= 0.0015 * step_scale
                if dist > follow_radius * 3.0:
                    result.reward -= 0.0025 * step_scale

            self.active_slider["last_progress"] = progress

        tick_times = self.active_slider["tick_times"]
        while self.active_slider["next_tick_index"] < len(tick_times):
            tick_time = tick_times[self.active_slider["next_tick_index"]]

            if time_ms < tick_time:
                break

            tick_x, tick_y = slider_ball_position(
                path=path,
                repeats=slider.repeats,
                start_time_ms=start_time,
                end_time_ms=end_time,
                current_time_ms=tick_time,
            )
            tick_dist = distance(cursor_x, cursor_y, tick_x, tick_y)

            if click_down and tick_dist <= follow_radius:
                result.reward += 0.14
                result.score_value = max(result.score_value, 10)
                result.judgement = "slider_tick"
                result.popup_x = tick_x
                result.popup_y = tick_y
                self.active_slider["tick_hits"] += 1
            else:
                result.reward -= 0.015
                if result.judgement == "none":
                    result.judgement = "slider_tick_miss"
                    result.popup_x = tick_x
                    result.popup_y = tick_y
                self.active_slider["tick_misses"] += 1

            self.active_slider["next_tick_index"] += 1

        if time_ms < end_time:
            return

        if click_down and dist <= follow_radius:
            result.reward += 0.55
            if result.judgement == "none":
                result.judgement = "slider_finish"
                result.popup_x = ball_x
                result.popup_y = ball_y
        else:
            result.reward -= 0.12
            if result.judgement == "none":
                result.judgement = "slider_drop"
                result.popup_x = ball_x
                result.popup_y = ball_y

        self.active_slider = None

    def _try_start_spinner(self, obj: HitObject, time_ms: float) -> JudgeResult:
        spinner = obj.spinner

        if self.active_spinner is None and time_ms >= spinner.time_ms:
            self.active_spinner = {
                "start_time": spinner.time_ms,
                "end_time": spinner.end_time_ms,
                "spin_progress": 0.0,
                "last_angle": None,
                "last_angular_velocity": 0.0,
                "target_spins": SPINNER_CLEAR_MIN_SPINS,
                "samples": 0,
                "hold_samples": 0,
                "valid_radius_samples": 0,
                "good_radius_samples": 0,
                "excess_delta_samples": 0,
                "direction_flips": 0,
                "last_delta_sign": 0,
            }
            self.object_index += 1
            return JudgeResult(reward=0.05, score_value=0, judgement="spinner_start", popup_x=256.0, popup_y=192.0)

        return JudgeResult()

    def _update_active_spinner(
        self,
        time_ms: float,
        cursor_x: float,
        cursor_y: float,
        click_down: bool,
        dt_ms: float,
        result: JudgeResult,
    ) -> None:
        if self.active_spinner is None:
            return

        center_x, center_y = SPINNER_CENTER_X, SPINNER_CENTER_Y
        target_radius = SPINNER_TARGET_RADIUS
        angle = math.atan2(cursor_y - center_y, cursor_x - center_x)
        radius = distance(cursor_x, cursor_y, center_x, center_y)
        radius_error = abs(radius - target_radius)
        step_scale = dt_ms / 16.6667
        valid_radius = SPINNER_MIN_VALID_RADIUS <= radius <= SPINNER_MAX_VALID_RADIUS
        good_radius = radius_error <= SPINNER_GOOD_RADIUS_TOLERANCE
        self.active_spinner["samples"] += 1
        if click_down:
            self.active_spinner["hold_samples"] += 1
        if valid_radius:
            self.active_spinner["valid_radius_samples"] += 1
        if good_radius:
            self.active_spinner["good_radius_samples"] += 1

        radius_score = max(0.0, 1.0 - radius_error / SPINNER_GOOD_RADIUS_TOLERANCE)
        result.reward += 0.0015 * radius_score * step_scale
        if click_down:
            result.reward += 0.0015 * step_scale
        else:
            result.reward -= 0.010 * step_scale
        if radius < SPINNER_MIN_VALID_RADIUS:
            center_excess = (SPINNER_MIN_VALID_RADIUS - radius) / SPINNER_MIN_VALID_RADIUS
            result.reward -= 0.028 * (1.0 + center_excess) * step_scale
        elif radius > SPINNER_MAX_VALID_RADIUS:
            result.reward -= 0.010 * step_scale

        if self.active_spinner["last_angle"] is not None:
            delta = angle - self.active_spinner["last_angle"]

            while delta > math.pi:
                delta -= 2 * math.pi
            while delta < -math.pi:
                delta += 2 * math.pi

            delta_abs = abs(delta)
            delta_sign = 1 if delta > SPINNER_MIN_DELTA_PER_STEP else -1 if delta < -SPINNER_MIN_DELTA_PER_STEP else 0
            last_delta_sign = int(self.active_spinner.get("last_delta_sign", 0))
            if last_delta_sign != 0 and delta_sign != 0 and delta_sign != last_delta_sign:
                self.active_spinner["direction_flips"] += 1
                result.reward -= 0.010 * step_scale
            if delta_sign != 0:
                self.active_spinner["last_delta_sign"] = delta_sign

            too_fast = delta_abs > SPINNER_MAX_DELTA_PER_STEP
            if too_fast:
                self.active_spinner["excess_delta_samples"] += 1
                result.reward -= min(0.040, (delta_abs - SPINNER_MAX_DELTA_PER_STEP) * 0.035) * step_scale

            effective_delta = min(delta_abs, SPINNER_MAX_DELTA_PER_STEP)
            if click_down and valid_radius and not too_fast and effective_delta >= SPINNER_MIN_DELTA_PER_STEP:
                self.active_spinner["spin_progress"] += effective_delta
            angular_velocity = delta_abs / max(1e-6, dt_ms / 1000.0)
            self.active_spinner["last_angular_velocity"] = angular_velocity
            if click_down and good_radius and not too_fast:
                result.reward += min(0.070, effective_delta * 0.250)
            elif click_down and valid_radius and not too_fast:
                result.reward += min(0.030, effective_delta * 0.120)
            elif click_down and valid_radius:
                result.reward -= 0.012 * step_scale
            if SPINNER_MIN_DELTA_PER_STEP <= delta_abs <= SPINNER_MAX_DELTA_PER_STEP and good_radius and click_down:
                result.reward += 0.010 * step_scale
        else:
            self.active_spinner["last_angular_velocity"] = 0.0

        self.active_spinner["last_angle"] = angle

        if time_ms < self.active_spinner["end_time"]:
            return

        spins = self.active_spinner["spin_progress"] / (2.0 * math.pi)
        samples = max(1, int(self.active_spinner.get("samples", 0)))
        hold_samples = int(self.active_spinner.get("hold_samples", 0))
        valid_radius_samples = int(self.active_spinner.get("valid_radius_samples", 0))
        good_radius_samples = int(self.active_spinner.get("good_radius_samples", 0))
        direction_flips = int(self.active_spinner.get("direction_flips", 0))
        excess_delta_samples = int(self.active_spinner.get("excess_delta_samples", 0))
        hold_ratio = hold_samples / samples
        valid_radius_ratio = valid_radius_samples / samples
        good_radius_ratio = good_radius_samples / samples
        flip_ratio = direction_flips / samples
        excess_delta_ratio = excess_delta_samples / samples

        clean_orbit = (
            valid_radius_ratio >= 0.60
            and good_radius_ratio >= 0.28
            and flip_ratio <= 0.40
            and excess_delta_ratio <= 0.20
        )
        partial_orbit = valid_radius_ratio >= 0.40 and flip_ratio <= 0.55 and excess_delta_ratio <= 0.35

        target_spins = float(self.active_spinner.get("target_spins", SPINNER_CLEAR_MIN_SPINS))
        partial_spins = max(SPINNER_PARTIAL_MIN_SPINS, target_spins * 0.5)

        if spins >= target_spins and hold_ratio >= 0.65 and clean_orbit:
            hit = self._register_scored_hit(300, "spinner_clear", center_x, center_y)
            result.reward += hit.reward + 0.5
            result.score_value = hit.score_value
            result.judgement = hit.judgement
            result.popup_x = hit.popup_x
            result.popup_y = hit.popup_y
        elif spins >= partial_spins and hold_ratio >= 0.45 and partial_orbit:
            hit = self._register_scored_hit(100, "spinner_partial", center_x, center_y)
            result.reward += hit.reward + 0.2
            result.score_value = hit.score_value
            result.judgement = hit.judgement
            result.popup_x = hit.popup_x
            result.popup_y = hit.popup_y
        elif spins >= partial_spins:
            self._register_miss(result, None, center_x, center_y)
            result.reward -= 0.25
            result.judgement = "spinner_no_hold"
        else:
            self._register_miss(result, None, center_x, center_y)
            result.judgement = "spinner_miss"

        self.active_spinner = None

    def _score_value_from_timing_error(self, timing_error: float) -> int:
        if timing_error <= hit_window_300(self.od):
            return 300
        if timing_error <= hit_window_100(self.od):
            return 100
        if timing_error <= hit_window_50(self.od):
            return 50
        return 0

    def _register_scored_hit(self, value: int, judgement: str, x: float, y: float) -> JudgeResult:
        self.combo += 1
        self.max_combo = max(self.max_combo, self.combo)
        self.hit_count += 1
        self.score_sum += value
        self.score_max_sum += 300

        reward = {300: 1.0, 100: 0.5, 50: 0.2, 10: 0.05}.get(value, 0.0)
        return JudgeResult(
            reward=reward,
            score_value=value,
            judgement=judgement,
            popup_x=x,
            popup_y=y,
        )

    def _register_miss(
        self,
        result: JudgeResult,
        obj: HitObject | None = None,
        popup_x: float | None = None,
        popup_y: float | None = None,
    ) -> None:
        self.combo = 0
        self.miss_count += 1
        self.score_max_sum += 300
        result.reward -= 1.0
        result.score_value = 0
        result.judgement = "miss"

        if obj is not None:
            x, y = self._object_anchor(obj)
            result.popup_x = x
            result.popup_y = y
        else:
            result.popup_x = popup_x
            result.popup_y = popup_y
