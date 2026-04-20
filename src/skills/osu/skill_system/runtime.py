from __future__ import annotations

from dataclasses import dataclass, field

from src.skills.osu.env.types import OsuAction, OsuObservation
from src.skills.osu.skill_system.config import SkillSystemConfig
from src.skills.osu.skill_system.executor import SkillExecutionResult, SkillExecutor
from src.skills.osu.skill_system.matcher import SkillMatcher
from src.skills.osu.skill_system.models import SkillEntry, SkillUsageRecord, utc_now_iso
from src.skills.osu.skill_system.ranker import RankedSkill, SkillRanker
from src.skills.osu.skill_system.selector import SkillSelector
from src.skills.osu.skill_system.storage import make_skill_memory_store


@dataclass(slots=True)
class SkillRuntimeReport:
    matched: int = 0
    selected: int = 0
    rejected: int = 0
    active_steps: int = 0
    aborts: int = 0
    ended: int = 0
    helpful_uses: int = 0
    harmful_uses: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)


class SkillRuntime:
    def __init__(self, skills: list[SkillEntry], cfg: SkillSystemConfig | None = None) -> None:
        self.cfg = cfg or SkillSystemConfig(enable_skill_system=True)
        self.skills = skills
        self.matcher = SkillMatcher(skills)
        self.ranker = SkillRanker(self.cfg.selector)
        self.selector = SkillSelector(self.cfg.selector)
        self.executor = SkillExecutor(self.cfg.executor, self.cfg.selector)
        self.report = SkillRuntimeReport()
        self._active_baseline_snapshot: dict[str, float] = {}

    @classmethod
    def from_path(cls, path: str, cfg: SkillSystemConfig | None = None) -> SkillRuntime:
        store = make_skill_memory_store(path)
        skills = store.load()
        return cls(skills=skills, cfg=cfg or SkillSystemConfig(enable_skill_system=True, skill_memory_path=path))

    def save(self, path: str | None = None) -> None:
        store = make_skill_memory_store(path or self.cfg.skill_memory_path)
        store.save(self.skills)

    def act(self, obs: OsuObservation, baseline_action: OsuAction) -> OsuAction:
        if not self.cfg.enable_skill_system or not self.skills:
            return baseline_action

        if not self.executor.state.active:
            matches = self.matcher.match(obs)
            self.report.matched += len(matches)
            counts = self.selector.recent_type_counts(obs.time_ms)
            if self.cfg.selector.enable_ranker:
                ranked = self.ranker.rank(matches, obs, recent_type_counts=counts)
            else:
                ranked = [
                    RankedSkill(
                        match=match,
                        rank_score=match.similarity,
                        expected_gain=0.0,
                        local_risk=0.25,
                        explanation={"mode": "similarity_only"},
                    )
                    for match in matches
                ]
                ranked.sort(key=lambda item: item.rank_score, reverse=True)
            selection = self.selector.select(ranked, obs.time_ms)
            self.report.rejected += len(selection.rejected)
            if selection.selected is not None:
                self.executor.maybe_start(selection.selected, obs.time_ms)
                skill = selection.selected.match.skill
                self.report.selected += 1
                self.report.by_type[skill.skill_type] = self.report.by_type.get(skill.skill_type, 0) + 1
                self._active_baseline_snapshot = self._snapshot(obs)
                self._event(obs, "select", skill.skill_id, skill.skill_type, selection.reason, selection.selected.rank_score)

        result = self.executor.apply(obs, baseline_action)
        self._consume_result(obs, result)
        return result.action

    def post_step(self, before: OsuObservation, after: OsuObservation, info: dict) -> None:
        # Lightweight online post-use evaluation. Full baseline-vs-skill comparison is done
        # by eval_skill_system.py; this update keeps per-skill stats useful during runtime.
        if not self.cfg.selector.enable_post_use_adaptation:
            return
        judgement = str(info.get("judgement", "none"))
        score_value = float(info.get("score_value", 0.0))
        if judgement == "none" and not self.executor.state.active:
            return
        skill = self.executor.state.active_skill
        if skill is None:
            return
        success_signal = score_value > 0.0 or (
            before.slider.active_slider > 0.5 and before.slider.inside_follow > 0.5 and after.slider.distance_to_target <= before.slider.distance_to_target + 8.0
        )
        if judgement in {"miss", "slider_drop", "spinner_miss"}:
            success_signal = False
        confidence_before = skill.confidence
        delta = 0.012 if success_signal else -0.020
        skill.confidence = max(0.05, min(1.0, skill.confidence + delta))
        skill.last_used_at = utc_now_iso()
        record = SkillUsageRecord(
            skill_id=skill.skill_id,
            skill_type=skill.skill_type,
            map_id="runtime",
            started_at_ms=self.executor.state.started_at_ms,
            ended_at_ms=after.time_ms,
            success=success_signal,
            gain_vs_baseline=delta,
            hit_delta=1.0 if score_value > 0 else 0.0,
            slider_quality_delta=max(-1.0, min(1.0, before.slider.distance_to_target - after.slider.distance_to_target)) / 100.0,
            timing_delta=0.0,
            confidence_before_use=confidence_before,
            confidence_after_use=skill.confidence,
            fallback_used=self.executor.state.fallback_used,
            reason=judgement,
        )
        skill.success_stats.update(record)

    def _consume_result(self, obs: OsuObservation, result: SkillExecutionResult) -> None:
        if result.event == "baseline":
            return
        if result.event == "active":
            self.report.active_steps += 1
        elif result.event == "abort":
            self.report.aborts += 1
            self._event(obs, "abort", result.skill_id, result.skill_type, result.reason, 0.0)
        elif result.event == "end":
            self.report.ended += 1
            self._event(obs, "end", result.skill_id, result.skill_type, result.reason, result.bias_strength)

    def _event(self, obs: OsuObservation, event: str, skill_id: str, skill_type: str, reason: str, score: float) -> None:
        if not self.cfg.log_runtime:
            return
        self.report.events.append(
            {
                "time_ms": obs.time_ms,
                "event": event,
                "skill_id": skill_id,
                "skill_type": skill_type,
                "reason": reason,
                "score": score,
            }
        )
        self.report.events = self.report.events[-500:]

    @staticmethod
    def _snapshot(obs: OsuObservation) -> dict[str, float]:
        primary = obs.upcoming[0] if obs.upcoming else None
        return {
            "time_ms": obs.time_ms,
            "primary_distance": 0.0 if primary is None else primary.distance_to_cursor,
            "slider_distance": obs.slider.distance_to_target,
            "slider_inside": obs.slider.inside_follow,
        }
