from __future__ import annotations

from dataclasses import dataclass, field

from src.skills.osu.env.types import OsuObservation
from src.skills.osu.skill_system.config import SkillSelectorConfig
from src.skills.osu.skill_system.matcher import SkillMatch


@dataclass(slots=True)
class RankedSkill:
    match: SkillMatch
    rank_score: float
    expected_gain: float
    local_risk: float
    explanation: dict[str, float | str] = field(default_factory=dict)


class SkillRanker:
    def __init__(self, cfg: SkillSelectorConfig | None = None) -> None:
        self.cfg = cfg or SkillSelectorConfig()

    def rank(self, matches: list[SkillMatch], obs: OsuObservation, recent_type_counts: dict[str, int] | None = None) -> list[RankedSkill]:
        recent_type_counts = recent_type_counts or {}
        ranked: list[RankedSkill] = []
        for match in matches:
            skill = match.skill
            risk = self._risk(obs, match)
            recent_success = skill.success_stats.success_rate if skill.success_stats.uses > 0 else 0.5
            support_score = min(1.0, skill.support_count / 8.0)
            expected_gain = float(skill.success_stats.avg_gain_vs_baseline)
            if skill.success_stats.uses == 0:
                expected_gain = skill.confidence * 0.08
            overuse = min(0.30, 0.08 * recent_type_counts.get(skill.skill_type, 0))
            mismatch_penalty = 0.0 if match.applicable else 0.35
            score = (
                0.34 * match.similarity
                + 0.25 * skill.confidence
                + 0.15 * support_score
                + 0.13 * recent_success
                + 0.13 * max(0.0, min(1.0, 0.5 + expected_gain))
                - 0.22 * risk
                - overuse
                - mismatch_penalty
            )
            ranked.append(
                RankedSkill(
                    match=match,
                    rank_score=max(0.0, min(1.0, score)),
                    expected_gain=expected_gain,
                    local_risk=risk,
                    explanation={
                        "similarity": match.similarity,
                        "confidence": skill.confidence,
                        "support_score": support_score,
                        "recent_success": recent_success,
                        "expected_gain": expected_gain,
                        "risk": risk,
                        "overuse_penalty": overuse,
                        "mismatch_penalty": mismatch_penalty,
                    },
                )
            )
        ranked.sort(key=lambda item: item.rank_score, reverse=True)
        return ranked

    @staticmethod
    def _risk(obs: OsuObservation, match: SkillMatch) -> float:
        primary = obs.upcoming[0] if obs.upcoming else None
        risk = 0.18
        if primary is not None:
            if primary.time_to_hit_ms < -60.0:
                risk += 0.25
            if primary.distance_to_cursor > 170.0 and primary.time_to_hit_ms < 220.0:
                risk += 0.22
        if obs.slider.active_slider > 0.5 and obs.slider.distance_to_target > 115.0:
            risk += 0.22
        if not match.applicable:
            risk += 0.22
        return max(0.0, min(1.0, risk))
