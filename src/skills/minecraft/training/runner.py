from __future__ import annotations

from dataclasses import dataclass

from src.skills.minecraft.actions import ActionController
from src.skills.minecraft.config import MinecraftRuntimeConfig
from src.skills.minecraft.env.connector import MinecraftConnector
from src.skills.minecraft.env.factory import make_minecraft_connector
from src.skills.minecraft.env.observation_builder import ObservationBuilder
from src.skills.minecraft.env.types import EnvStepResult, MinecraftAction
from src.skills.minecraft.reward import RewardSystem
from src.skills.minecraft.training.checkpoints import CheckpointManager


@dataclass(frozen=True, slots=True)
class TrainingRunSummary:
    run_id: str
    steps: int
    total_reward: float
    done: bool


class TrainingRunner:
    def __init__(
        self,
        config: MinecraftRuntimeConfig,
        connector: MinecraftConnector | None = None,
        reward_system: RewardSystem | None = None,
    ) -> None:
        self.config = config
        self.connector = connector or make_minecraft_connector(config)
        self.observation_builder = ObservationBuilder(config.frame_stack)
        self.action_controller = ActionController(self.connector)
        self.reward_system = reward_system or RewardSystem()
        self.checkpoints = CheckpointManager(config.paths.checkpoints_dir)

    def dry_run(self, steps: int | None = None) -> TrainingRunSummary:
        self.config.paths.ensure()
        max_steps = self.config.max_episode_steps if steps is None else max(0, int(steps))
        self.observation_builder.reset()
        current = self.observation_builder.build(self.connector.reset())
        total_reward = 0.0
        done = False

        for index in range(max_steps):
            action = self._baseline_action(index)
            raw = self.action_controller.send(action)
            next_obs = self.observation_builder.build(raw)
            reward = self.reward_system.compute(current, next_obs, action)
            total_reward += reward.total
            done = next_obs.status.hp <= 0.0
            current = next_obs
            if done:
                break

        summary = TrainingRunSummary(
            run_id=self.config.run_id,
            steps=max_steps if not done else current.tick,
            total_reward=total_reward,
            done=done,
        )
        self.checkpoints.save_manifest(self.config.run_id, {"summary": summary, "config": self.config})
        return summary

    @staticmethod
    def _baseline_action(index: int) -> MinecraftAction:
        if index == 0:
            return MinecraftAction(command="noop", duration_ms=80)
        if index % 2 == 0:
            return MinecraftAction(command="move_forward", forward=1.0, duration_ms=80)
        return MinecraftAction(command="look_delta", camera_yaw_delta=2.0, duration_ms=80)
