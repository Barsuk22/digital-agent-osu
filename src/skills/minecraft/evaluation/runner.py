from __future__ import annotations

from dataclasses import dataclass

from src.skills.minecraft.config import MinecraftRuntimeConfig
from src.skills.minecraft.training.runner import TrainingRunner


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    run_id: str
    connector: str
    steps: int
    total_reward: float
    passed: bool


class EvaluationRunner:
    def __init__(self, config: MinecraftRuntimeConfig) -> None:
        self.config = config

    def run_phase_a_smoke(self, steps: int = 5) -> EvaluationSummary:
        summary = TrainingRunner(self.config).dry_run(steps=steps)
        return EvaluationSummary(
            run_id=summary.run_id,
            connector=self.config.connector,
            steps=summary.steps,
            total_reward=summary.total_reward,
            passed=summary.steps == steps and not summary.done,
        )
