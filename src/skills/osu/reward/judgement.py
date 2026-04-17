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
from src.skills.osu.domain.slider_path import build_slider_path, slider_ball_position


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

        ticks_per_span = max(0, int(math.floor((tick_rate - 0.01))))
        if ticks_per_span <= 0:
            return tick_times

        for span_idx in range(slider.repeats):
            span_start = slider.time_ms + span_idx * span_duration_ms
            for i in range(1, ticks_per_span + 1):
                frac = i / (ticks_per_span + 1)
                tick_times.append(span_start + frac * span_duration_ms)

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
        follow_radius = self.radius * 1.4

        if time_ms < end_time:
            if click_down and dist <= follow_radius:
                result.reward += 0.014 * (dt_ms / 16.6667)
                if result.judgement == "none":
                    result.judgement = "slider_follow"
                    result.popup_x = ball_x
                    result.popup_y = ball_y
            else:
                result.reward -= 0.002 * (dt_ms / 16.6667)

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
                result.reward += 0.08
                result.score_value = max(result.score_value, 10)
                result.judgement = "slider_tick"
                result.popup_x = tick_x
                result.popup_y = tick_y
                self.active_slider["tick_hits"] += 1
            else:
                result.reward -= 0.04
                if result.judgement == "none":
                    result.judgement = "slider_tick_miss"
                    result.popup_x = tick_x
                    result.popup_y = tick_y
                self.active_slider["tick_misses"] += 1

            self.active_slider["next_tick_index"] += 1

        if time_ms < end_time:
            return

        if click_down and dist <= follow_radius:
            result.reward += 0.35
            if result.judgement == "none":
                result.judgement = "slider_finish"
                result.popup_x = ball_x
                result.popup_y = ball_y
        else:
            result.reward -= 0.20
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

        center_x, center_y = 256.0, 192.0
        angle = math.atan2(cursor_y - center_y, cursor_x - center_x)

        if self.active_spinner["last_angle"] is not None and click_down:
            delta = angle - self.active_spinner["last_angle"]

            while delta > math.pi:
                delta -= 2 * math.pi
            while delta < -math.pi:
                delta += 2 * math.pi

            delta_abs = abs(delta)
            self.active_spinner["spin_progress"] += delta_abs
            result.reward += delta_abs * 0.02

        self.active_spinner["last_angle"] = angle

        if time_ms < self.active_spinner["end_time"]:
            return

        spins = self.active_spinner["spin_progress"] / (2.0 * math.pi)

        if spins >= 3.0:
            hit = self._register_scored_hit(300, "spinner_clear", center_x, center_y)
            result.reward += hit.reward + 0.5
            result.score_value = hit.score_value
            result.judgement = hit.judgement
            result.popup_x = hit.popup_x
            result.popup_y = hit.popup_y
        elif spins >= 1.5:
            hit = self._register_scored_hit(100, "spinner_partial", center_x, center_y)
            result.reward += hit.reward + 0.2
            result.score_value = hit.score_value
            result.judgement = hit.judgement
            result.popup_x = hit.popup_x
            result.popup_y = hit.popup_y
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