from __future__ import annotations

from dataclasses import dataclass
from typing import List

from src.skills.osu.domain.math_utils import clamp_position, distance
from src.skills.osu.domain.models import HitObject, HitObjectType, ParsedBeatmap
from src.skills.osu.domain.osu_rules import ar_to_preempt_ms, slider_duration_ms
from src.skills.osu.env.types import OsuAction, OsuObservation, SliderStateView, SpinnerStateView, UpcomingObjectView
from src.skills.osu.reward.judgement import OsuJudge
from src.skills.osu.viewer.replay_models import ReplayFrame


@dataclass(slots=True)
class EnvStepResult:
    observation: OsuObservation
    reward: float
    done: bool
    info: dict


class OsuEnv:
    def __init__(
        self,
        beatmap: ParsedBeatmap,
        dt_ms: float = 16.6667,
        upcoming_count: int = 5,
        cursor_start_x: float = 256.0,
        cursor_start_y: float = 192.0,
        click_threshold: float = 0.75,
        slider_hold_threshold: float = 0.45,
        spinner_hold_threshold: float = 0.45,
        cursor_speed_scale: float = 14.0,
        spinner_cursor_speed_multiplier: float = 1.0,
    ) -> None:
        self.beatmap = beatmap
        self.dt_ms = dt_ms
        self.upcoming_count = upcoming_count
        self.click_threshold = click_threshold
        self.slider_hold_threshold = slider_hold_threshold
        self.spinner_hold_threshold = spinner_hold_threshold
        self.cursor_speed_scale = cursor_speed_scale
        self.spinner_cursor_speed_multiplier = max(1.0, spinner_cursor_speed_multiplier)
        self.judge = OsuJudge(beatmap)

        self.cursor_start_x = cursor_start_x
        self.cursor_start_y = cursor_start_y

        self.time_ms = 0.0
        self.cursor_x = cursor_start_x
        self.cursor_y = cursor_start_y
        self.done = False
        self.last_click_down = False
        self.last_raw_click_down = False
        self.current_click_down = False
        self.last_info: dict = {}
        self.replay_frames: list[ReplayFrame] = []
        self.recent_judgements: list[dict] = []

    def reset(self) -> OsuObservation:
        self.time_ms = 0.0
        self.cursor_x = self.cursor_start_x
        self.cursor_y = self.cursor_start_y
        self.done = False
        self.last_click_down = False
        self.last_raw_click_down = False
        self.current_click_down = False
        self.last_info = {}
        self.replay_frames = []
        self.recent_judgements = []
        self.judge.reset()
        return self._build_observation()

    def step(self, action: OsuAction, dt_ms_override: float | None = None) -> EnvStepResult:
        if self.done:
            obs = self._build_observation()
            return EnvStepResult(
                observation=obs,
                reward=0.0,
                done=True,
                info={"message": "env already done", **self.last_info},
            )

        dt_step = self.dt_ms if dt_ms_override is None else max(0.1, float(dt_ms_override))

        active_spinner_movement = self.judge.active_spinner is not None
        speed_scale = self.cursor_speed_scale * (
            self.spinner_cursor_speed_multiplier if active_spinner_movement else 1.0
        )
        new_x = self.cursor_x + action.dx * speed_scale
        new_y = self.cursor_y + action.dy * speed_scale
        self.cursor_x, self.cursor_y = clamp_position(new_x, new_y)

        raw_click_down = action.click_strength >= self.click_threshold
        slider_hold_down = self.judge.active_slider is not None and action.click_strength >= self.slider_hold_threshold
        spinner_hold_down = self.judge.active_spinner is not None and action.click_strength >= self.spinner_hold_threshold
        click_down = raw_click_down or slider_hold_down or spinner_hold_down
        just_pressed = raw_click_down and not self.last_raw_click_down
        self.current_click_down = click_down

        judge_result = self.judge.update(
            time_ms=self.time_ms,
            cursor_x=self.cursor_x,
            cursor_y=self.cursor_y,
            just_pressed=just_pressed,
            click_down=click_down,
            dt_ms=dt_step,
        )

        self.last_click_down = click_down
        self.last_raw_click_down = raw_click_down
        self.time_ms += dt_step

        if self.judge.is_finished(self.time_ms):
            self.done = True

        obs = self._build_observation()
        slider_state = self.judge.active_slider_state(self.time_ms, self.cursor_x, self.cursor_y)
        spinner_state = self.judge.active_spinner_state(self.time_ms, self.cursor_x, self.cursor_y)

        info = {
            "score_value": judge_result.score_value,
            "judgement": judge_result.judgement,
            "combo": self.judge.combo,
            "max_combo": self.judge.max_combo,
            "accuracy": self.judge.accuracy(),
            "hit_count": self.judge.hit_count,
            "miss_count": self.judge.miss_count,
            "time_ms": self.time_ms,
            "cursor_x": self.cursor_x,
            "cursor_y": self.cursor_y,
            "click_down": click_down,
            "raw_click_down": raw_click_down,
            "slider_hold_down": slider_hold_down,
            "spinner_hold_down": spinner_hold_down,
            "click_strength": action.click_strength,
            "click_threshold": self.click_threshold,
            "slider_hold_threshold": self.slider_hold_threshold,
            "spinner_hold_threshold": self.spinner_hold_threshold,
            "popup_x": judge_result.popup_x,
            "popup_y": judge_result.popup_y,
            "slider_state": slider_state,
            "spinner_state": spinner_state,
        }
        self.last_info = info

        if judge_result.judgement != "none":
            self.recent_judgements.append(
                {
                    "time_ms": self.time_ms,
                    "judgement": judge_result.judgement,
                    "score_value": judge_result.score_value,
                    "popup_x": judge_result.popup_x,
                    "popup_y": judge_result.popup_y,
                }
            )
            self.recent_judgements = self.recent_judgements[-20:]

        self.replay_frames.append(
            ReplayFrame(
                time_ms=self.time_ms,
                cursor_x=self.cursor_x,
                cursor_y=self.cursor_y,
                click_down=click_down,
                judgement=judge_result.judgement,
                combo=self.judge.combo,
                accuracy=self.judge.accuracy(),
                reward=judge_result.reward,
                score_value=judge_result.score_value,
                popup_x=judge_result.popup_x,
                popup_y=judge_result.popup_y,
            )
        )

        return EnvStepResult(
            observation=obs,
            reward=judge_result.reward,
            done=self.done,
            info=info,
        )

    def get_visible_objects(self) -> List[HitObject]:
        preempt = ar_to_preempt_ms(self.beatmap.difficulty.ar)
        visible: List[HitObject] = []

        for obj in self.beatmap.hit_objects:
            start_visible = obj.time_ms - preempt

            if obj.kind == HitObjectType.CIRCLE:
                end_visible = obj.time_ms + 220.0
            elif obj.kind == HitObjectType.SLIDER:
                end_visible = obj.slider.time_ms + slider_duration_ms(self.beatmap, obj.slider) + 220.0
            else:
                end_visible = obj.spinner.end_time_ms + 220.0

            if self.time_ms < start_visible:
                if visible:
                    break
                continue

            if self.time_ms <= end_visible:
                visible.append(obj)

        return visible

    def consume_recent_judgements(self, now_ms: float, ttl_ms: float = 700.0) -> list[dict]:
        active = [j for j in self.recent_judgements if now_ms - j["time_ms"] <= ttl_ms]
        self.recent_judgements = active
        return active

    def _build_observation(self) -> OsuObservation:
        upcoming = self.judge.peek_upcoming_objects(self.time_ms, self.upcoming_count)
        primary_is_slider = 1.0 if upcoming and upcoming[0].kind == HitObjectType.SLIDER else 0.0
        primary_is_spinner = 1.0 if upcoming and upcoming[0].kind == HitObjectType.SPINNER else 0.0

        views: List[UpcomingObjectView] = []
        for obj in upcoming:
            x, y = self._object_anchor(obj)
            kind_id = self._kind_to_id(obj.kind)

            if obj.kind == HitObjectType.CIRCLE:
                is_active = 1.0 if abs(obj.circle.time_ms - self.time_ms) <= 80.0 else 0.0
            elif obj.kind == HitObjectType.SLIDER:
                is_active = 1.0 if self.time_ms >= obj.slider.time_ms else 0.0
            else:
                is_active = 1.0 if self.time_ms >= obj.spinner.time_ms else 0.0

            views.append(
                UpcomingObjectView(
                    kind_id=kind_id,
                    x=x,
                    y=y,
                    time_to_hit_ms=obj.time_ms - self.time_ms,
                    distance_to_cursor=distance(self.cursor_x, self.cursor_y, x, y),
                    is_active=is_active,
                )
            )

        while len(views) < self.upcoming_count:
            views.append(
                UpcomingObjectView(
                    kind_id=-1,
                    x=0.0,
                    y=0.0,
                    time_to_hit_ms=0.0,
                    distance_to_cursor=0.0,
                    is_active=0.0,
                )
            )

        slider_state = self.judge.active_slider_state(self.time_ms, self.cursor_x, self.cursor_y)
        spinner_state = self.judge.active_spinner_state(self.time_ms, self.cursor_x, self.cursor_y)

        return OsuObservation(
            time_ms=self.time_ms,
            cursor_x=self.cursor_x,
            cursor_y=self.cursor_y,
            upcoming=views,
            slider=SliderStateView(
                active_slider=1.0 if slider_state["active_slider"] else 0.0,
                primary_is_slider=primary_is_slider,
                progress=float(slider_state["progress"]),
                target_x=float(slider_state["target_x"]),
                target_y=float(slider_state["target_y"]),
                distance_to_target=float(slider_state["distance_to_target"]),
                distance_to_ball=float(slider_state["distance_to_ball"]),
                inside_follow=1.0 if slider_state["inside_follow"] else 0.0,
                head_hit=1.0 if slider_state["head_hit"] else 0.0,
                time_to_end_ms=float(slider_state["time_to_end_ms"]),
                tangent_x=float(slider_state["tangent_x"]),
                tangent_y=float(slider_state["tangent_y"]),
                follow_radius=float(slider_state["follow_radius"]),
            ),
            spinner=SpinnerStateView(
                active_spinner=1.0 if spinner_state["active_spinner"] else 0.0,
                primary_is_spinner=primary_is_spinner,
                progress=float(spinner_state["progress"]),
                spins=float(spinner_state["spins"]),
                target_spins=float(spinner_state["target_spins"]),
                time_to_end_ms=float(spinner_state["time_to_end_ms"]),
                center_x=float(spinner_state["center_x"]),
                center_y=float(spinner_state["center_y"]),
                distance_to_center=float(spinner_state["distance_to_center"]),
                radius_error=float(spinner_state["radius_error"]),
                angle_sin=float(spinner_state["angle_sin"]),
                angle_cos=float(spinner_state["angle_cos"]),
                angular_velocity=float(spinner_state["angular_velocity"]),
            ),
        )

    @staticmethod
    def _kind_to_id(kind: HitObjectType) -> int:
        if kind == HitObjectType.CIRCLE:
            return 0
        if kind == HitObjectType.SLIDER:
            return 1
        if kind == HitObjectType.SPINNER:
            return 2
        return -1

    @staticmethod
    def _object_anchor(obj: HitObject) -> tuple[float, float]:
        if obj.kind == HitObjectType.CIRCLE:
            return obj.circle.x, obj.circle.y
        if obj.kind == HitObjectType.SLIDER:
            return obj.slider.x, obj.slider.y
        return obj.spinner.x, obj.spinner.y
