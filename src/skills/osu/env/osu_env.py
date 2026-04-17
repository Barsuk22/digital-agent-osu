from __future__ import annotations

from dataclasses import dataclass
from typing import List

from src.skills.osu.domain.math_utils import clamp_position, distance
from src.skills.osu.domain.models import HitObject, HitObjectType, ParsedBeatmap
from src.skills.osu.domain.osu_rules import ar_to_preempt_ms, slider_duration_ms
from src.skills.osu.env.types import OsuAction, OsuObservation, UpcomingObjectView
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
        cursor_speed_scale: float = 14.0,
    ) -> None:
        self.beatmap = beatmap
        self.dt_ms = dt_ms
        self.upcoming_count = upcoming_count
        self.click_threshold = click_threshold
        self.cursor_speed_scale = cursor_speed_scale
        self.judge = OsuJudge(beatmap)

        self.cursor_start_x = cursor_start_x
        self.cursor_start_y = cursor_start_y

        self.time_ms = 0.0
        self.cursor_x = cursor_start_x
        self.cursor_y = cursor_start_y
        self.done = False
        self.last_click_down = False
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

        new_x = self.cursor_x + action.dx * self.cursor_speed_scale
        new_y = self.cursor_y + action.dy * self.cursor_speed_scale
        self.cursor_x, self.cursor_y = clamp_position(new_x, new_y)

        click_down = action.click_strength >= self.click_threshold
        just_pressed = click_down and not self.last_click_down
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
        self.time_ms += dt_step

        if self.judge.is_finished(self.time_ms):
            self.done = True

        obs = self._build_observation()

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
            "popup_x": judge_result.popup_x,
            "popup_y": judge_result.popup_y,
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

        return OsuObservation(
            time_ms=self.time_ms,
            cursor_x=self.cursor_x,
            cursor_y=self.cursor_y,
            upcoming=views,
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