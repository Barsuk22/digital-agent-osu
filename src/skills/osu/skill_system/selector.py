from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from src.skills.osu.skill_system.config import SkillSelectorConfig
from src.skills.osu.skill_system.ranker import RankedSkill


@dataclass(slots=True)
class SkillSelection:
    selected: RankedSkill | None
    rejected: list[tuple[str, str]]
    reason: str


class SkillSelector:
    def __init__(self, cfg: SkillSelectorConfig | None = None) -> None:
        self.cfg = cfg or SkillSelectorConfig()
        self.last_selected_at_ms = -1e9
        self.recent_uses: deque[tuple[float, str]] = deque(maxlen=128)

    def recent_type_counts(self, now_ms: float) -> dict[str, int]:
        while self.recent_uses and now_ms - self.recent_uses[0][0] > self.cfg.overuse_window_ms:
            self.recent_uses.popleft()
        counts: dict[str, int] = {}
        for _, skill_type in self.recent_uses:
            counts[skill_type] = counts.get(skill_type, 0) + 1
        return counts

    def select(self, ranked: list[RankedSkill], now_ms: float) -> SkillSelection:
        rejected: list[tuple[str, str]] = []
        if now_ms - self.last_selected_at_ms < self.cfg.cooldown_ms:
            return SkillSelection(None, rejected, "cooldown")

        counts = self.recent_type_counts(now_ms)
        for item in ranked:
            skill = item.match.skill
            if item.match.similarity < self.cfg.min_similarity:
                rejected.append((skill.skill_id, "low_similarity"))
                continue
            if self.cfg.enable_confidence_gate and skill.confidence < self.cfg.min_confidence:
                rejected.append((skill.skill_id, "low_confidence"))
                continue
            if item.local_risk > self.cfg.max_risk:
                rejected.append((skill.skill_id, "risk_gate"))
                continue
            if counts.get(skill.skill_type, 0) >= self.cfg.max_recent_uses_per_type:
                rejected.append((skill.skill_id, "overuse_gate"))
                continue
            if not item.match.applicable:
                rejected.append((skill.skill_id, "not_applicable"))
                continue

            self.last_selected_at_ms = now_ms
            self.recent_uses.append((now_ms, skill.skill_type))
            return SkillSelection(item, rejected, "selected")

        return SkillSelection(None, rejected, "no_candidate")
