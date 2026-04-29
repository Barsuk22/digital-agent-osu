from __future__ import annotations

from dataclasses import dataclass, field

from src.skills.minecraft.env.types import MinecraftAction, MinecraftObservation


@dataclass(frozen=True, slots=True)
class RewardBreakdown:
    total: float
    terms: dict[str, float] = field(default_factory=dict)


class RewardSystem:
    def compute(
        self,
        previous: MinecraftObservation | None,
        current: MinecraftObservation,
        action: MinecraftAction,
    ) -> RewardBreakdown:
        terms: dict[str, float] = {"alive": 0.01}

        if previous is not None:
            hp_delta = current.status.hp - previous.status.hp
            hunger_delta = current.status.hunger - previous.status.hunger
            terms["hp_delta"] = hp_delta * 0.2
            terms["hunger_delta"] = hunger_delta * 0.05

        if action.attack and not current.nearby_entities:
            terms["air_attack_penalty"] = -0.02
        if current.status.hp <= 0.0:
            terms["death"] = -10.0
        if "item_picked_up" in current.events:
            terms["item_picked_up"] = 0.5
        if "block_broken" in current.events:
            terms["block_broken"] = 0.25

        return RewardBreakdown(total=sum(terms.values()), terms=terms)
