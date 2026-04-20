from __future__ import annotations

import math
from dataclasses import dataclass

from src.skills.osu.env.types import OsuAction, OsuObservation
from src.skills.osu.skill_system.config import SkillExecutorConfig, SkillSelectorConfig
from src.skills.osu.skill_system.models import SkillEntry
from src.skills.osu.skill_system.ranker import RankedSkill


@dataclass(slots=True)
class SkillExecutionState:
    active_skill: SkillEntry | None = None
    started_at_ms: float = 0.0
    last_reason: str = ""
    rank_score: float = 0.0
    fallback_used: bool = False

    @property
    def active(self) -> bool:
        return self.active_skill is not None


@dataclass(slots=True)
class SkillExecutionResult:
    action: OsuAction
    event: str
    skill_id: str = ""
    skill_type: str = ""
    reason: str = ""
    bias_strength: float = 0.0


class SkillExecutor:
    def __init__(self, cfg: SkillExecutorConfig | None = None, selector_cfg: SkillSelectorConfig | None = None) -> None:
        self.cfg = cfg or SkillExecutorConfig()
        self.selector_cfg = selector_cfg or SkillSelectorConfig()
        self.state = SkillExecutionState()

    def maybe_start(self, ranked: RankedSkill, now_ms: float) -> None:
        skill = ranked.match.skill
        self.state = SkillExecutionState(
            active_skill=skill,
            started_at_ms=now_ms,
            last_reason="started",
            rank_score=ranked.rank_score,
            fallback_used=False,
        )

    def apply(self, obs: OsuObservation, baseline_action: OsuAction) -> SkillExecutionResult:
        if self.state.active_skill is None:
            return SkillExecutionResult(action=baseline_action, event="baseline")

        skill = self.state.active_skill
        elapsed = obs.time_ms - self.state.started_at_ms
        abort_reason = self._abort_reason(skill, obs, elapsed)
        if abort_reason:
            self.state.fallback_used = True
            finished_skill = self.state.active_skill
            self.state = SkillExecutionState(last_reason=abort_reason, fallback_used=True)
            return SkillExecutionResult(
                action=baseline_action,
                event="abort",
                skill_id=finished_skill.skill_id,
                skill_type=finished_skill.skill_type,
                reason=abort_reason,
            )

        biased, strength = self._bias_action(skill, obs, baseline_action)
        if self._end_condition(skill, obs, elapsed):
            finished_skill = self.state.active_skill
            self.state = SkillExecutionState(last_reason="ended")
            return SkillExecutionResult(
                action=biased,
                event="end",
                skill_id=finished_skill.skill_id,
                skill_type=finished_skill.skill_type,
                reason="end_condition",
                bias_strength=strength,
            )

        return SkillExecutionResult(
            action=biased,
            event="active",
            skill_id=skill.skill_id,
            skill_type=skill.skill_type,
            reason="assist_bias",
            bias_strength=strength,
        )

    def _abort_reason(self, skill: SkillEntry, obs: OsuObservation, elapsed_ms: float) -> str:
        if elapsed_ms > self.selector_cfg.max_active_window_ms:
            return "window_timeout"
        primary = obs.upcoming[0] if obs.upcoming else None
        if self.selector_cfg.enable_fallback and primary is not None:
            if primary.distance_to_cursor > self.cfg.abort_far_distance_px and primary.time_to_hit_ms < 120.0:
                return "target_too_far_near_hit"
        if self.selector_cfg.enable_fallback and skill.skill_type in {"slider_follow", "reverse_slider", "kick_sliders"}:
            if obs.slider.active_slider > 0.5 and obs.slider.distance_to_target > self.cfg.abort_bad_slider_distance_px:
                return "slider_follow_lost"
        return ""

    def _end_condition(self, skill: SkillEntry, obs: OsuObservation, elapsed_ms: float) -> bool:
        if elapsed_ms < self.cfg.min_window_ms:
            return False
        if skill.skill_type in {"slider_follow", "reverse_slider", "kick_sliders"}:
            return obs.slider.active_slider <= 0.5 or obs.slider.progress >= self.cfg.end_progress
        if skill.skill_type == "spinner_control":
            return obs.spinner.active_spinner <= 0.5 or obs.spinner.progress >= self.cfg.end_progress
        primary = obs.upcoming[0] if obs.upcoming else None
        return primary is None or primary.time_to_hit_ms < -60.0

    def _bias_action(self, skill: SkillEntry, obs: OsuObservation, baseline: OsuAction) -> tuple[OsuAction, float]:
        if skill.skill_type in {"slider_follow", "reverse_slider", "kick_sliders"} and obs.slider.active_slider > 0.5:
            strength = self.cfg.slider_bias_strength
            target_dx = (obs.slider.target_x - obs.cursor_x) / 95.0
            target_dy = (obs.slider.target_y - obs.cursor_y) / 95.0
            click = max(baseline.click_strength, 0.58 + self.cfg.click_bias_strength)
        elif skill.skill_type == "spinner_control" and obs.spinner.active_spinner > 0.5:
            strength = self.cfg.spinner_bias_strength
            tangent_dx = -obs.spinner.angle_sin * 0.32
            tangent_dy = obs.spinner.angle_cos * 0.32
            radial = (76.0 - obs.spinner.distance_to_center) * 0.010
            target_dx = tangent_dx + obs.spinner.angle_cos * radial
            target_dy = tangent_dy + obs.spinner.angle_sin * radial
            click = max(baseline.click_strength, 0.62)
        else:
            strength = self.cfg.jump_bias_strength
            primary = obs.upcoming[0] if obs.upcoming else None
            if primary is None:
                return baseline, 0.0
            target_dx = (primary.x - obs.cursor_x) / 120.0
            target_dy = (primary.y - obs.cursor_y) / 120.0
            click_hint = float(skill.action_summary.get("mean_click_strength", 0.0))
            click = max(baseline.click_strength, min(0.86, click_hint))

        template_dx = float(skill.action_summary.get("mean_dx", 0.0))
        template_dy = float(skill.action_summary.get("mean_dy", 0.0))
        target_dx = 0.72 * target_dx + 0.28 * template_dx
        target_dy = 0.72 * target_dy + 0.28 * template_dy

        dx = baseline.dx * (1.0 - strength) + target_dx * strength
        dy = baseline.dy * (1.0 - strength) + target_dy * strength
        click_strength = baseline.click_strength * (1.0 - strength) + click * strength
        return (
            OsuAction(
                dx=max(-1.0, min(1.0, dx)),
                dy=max(-1.0, min(1.0, dy)),
                click_strength=max(0.0, min(1.0, click_strength)),
            ),
            strength,
        )
