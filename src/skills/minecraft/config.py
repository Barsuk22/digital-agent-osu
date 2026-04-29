from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MinecraftPaths:
    checkpoints_dir: Path = Path("artifacts/checkpoints/minecraft")
    logs_dir: Path = Path("artifacts/logs/minecraft")
    debug_dir: Path = Path("artifacts/debug/minecraft")
    runs_dir: Path = Path("artifacts/runs/minecraft")
    recordings_dir: Path = Path("data/minecraft/recordings")
    datasets_dir: Path = Path("data/minecraft/datasets")
    worlds_dir: Path = Path("data/minecraft/worlds")

    def ensure(self) -> None:
        for path in (
            self.checkpoints_dir,
            self.logs_dir,
            self.debug_dir,
            self.runs_dir,
            self.recordings_dir,
            self.datasets_dir,
            self.worlds_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class MinecraftBridgeConfig:
    host: str = "127.0.0.1"
    port: int = 4711
    timeout_seconds: float = 2.0


@dataclass(frozen=True, slots=True)
class MinecraftRuntimeConfig:
    connector: str = "null"
    observation_hz: float = 5.0
    frame_stack: int = 4
    max_episode_steps: int = 200
    run_id: str = "minecraft_phase_a_dry_run"
    paths: MinecraftPaths = MinecraftPaths()
    bridge: MinecraftBridgeConfig = MinecraftBridgeConfig()

    @property
    def step_dt_seconds(self) -> float:
        return 1.0 / max(0.1, self.observation_hz)


def default_minecraft_config() -> MinecraftRuntimeConfig:
    return MinecraftRuntimeConfig()
