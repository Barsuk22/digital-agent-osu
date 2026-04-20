from __future__ import annotations

from dataclasses import dataclass, field

from src.skills.osu.env.types import OsuObservation
from src.skills.osu.skill_system.features import runtime_context_signature, signature_similarity
from src.skills.osu.skill_system.models import SkillContextSignature, SkillEntry


@dataclass(slots=True)
class SkillMatch:
    skill: SkillEntry
    runtime_context: SkillContextSignature
    similarity: float
    applicability_flags: dict[str, bool]
    reason_codes: list[str] = field(default_factory=list)

    @property
    def applicable(self) -> bool:
        return all(self.applicability_flags.values())


class SkillMatcher:
    def __init__(self, skills: list[SkillEntry]) -> None:
        self.skills = skills

    def match(self, obs: OsuObservation) -> list[SkillMatch]:
        runtime_sig = runtime_context_signature(obs)
        matches: list[SkillMatch] = []
        for skill in self.skills:
            sim = signature_similarity(runtime_sig, skill.context_signature)
            flags, reasons = self._applicability(skill, obs, sim)
            matches.append(
                SkillMatch(
                    skill=skill,
                    runtime_context=runtime_sig,
                    similarity=sim,
                    applicability_flags=flags,
                    reason_codes=reasons,
                )
            )
        matches.sort(key=lambda item: item.similarity, reverse=True)
        return matches

    def _applicability(self, skill: SkillEntry, obs: OsuObservation, similarity: float) -> tuple[dict[str, bool], list[str]]:
        reasons: list[str] = []
        flags = {
            "similarity_positive": similarity > 0.0,
            "type_compatible": self._type_compatible(skill, obs),
            "risk_within_bounds": self._risk_estimate(obs) <= float(skill.applicability_conditions.get("max_risk", 0.85)),
        }
        for key, value in flags.items():
            if not value:
                reasons.append(key)
        return flags, reasons

    @staticmethod
    def _type_compatible(skill: SkillEntry, obs: OsuObservation) -> bool:
        primary_kind = obs.upcoming[0].kind_id if obs.upcoming else -1
        if skill.skill_type in {"slider_follow", "reverse_slider", "kick_sliders", "slider_aim"}:
            return obs.slider.active_slider > 0.5 or primary_kind == 1
        if skill.skill_type == "spinner_control":
            return obs.spinner.active_spinner > 0.5 or primary_kind == 2
        if skill.skill_type in {"short_chain", "simple_jump", "simple_double", "burst", "triplets"}:
            return primary_kind == 0
        return True

    @staticmethod
    def _risk_estimate(obs: OsuObservation) -> float:
        primary = obs.upcoming[0] if obs.upcoming else None
        risk = 0.20
        if primary is not None:
            if primary.time_to_hit_ms < -80.0:
                risk += 0.30
            if primary.distance_to_cursor > 180.0 and primary.time_to_hit_ms < 180.0:
                risk += 0.25
        if obs.slider.active_slider > 0.5 and obs.slider.distance_to_target > 120.0:
            risk += 0.20
        return max(0.0, min(1.0, risk))
