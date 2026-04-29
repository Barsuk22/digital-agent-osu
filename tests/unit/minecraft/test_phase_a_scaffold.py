from __future__ import annotations

from pathlib import Path

from src.skills.minecraft.actions import ActionController
from src.skills.minecraft.config import MinecraftPaths, MinecraftRuntimeConfig
from src.skills.minecraft.debug import DebugViewer
from src.skills.minecraft.env import NullMinecraftConnector, ObservationBuilder
from src.skills.minecraft.env.types import MinecraftAction
from src.skills.minecraft.evaluation import EvaluationRunner
from src.skills.minecraft.reward import RewardSystem
from src.skills.minecraft.training import TrainingRunner


def test_null_connector_observation_and_action_flow() -> None:
    connector = NullMinecraftConnector()
    builder = ObservationBuilder(frame_stack_size=4)
    controller = ActionController(connector)

    obs = builder.build(connector.reset())
    assert obs.status.hp == 20.0
    assert obs.nearby_blocks[0].block_id == "minecraft:oak_log"

    next_obs = builder.build(controller.send(MinecraftAction(forward=5.0, hotbar_slot=99, camera_pitch_delta=100.0)))
    assert connector.last_action.forward == 1.0
    assert connector.last_action.hotbar_slot == 8
    assert next_obs.tick == 1
    assert next_obs.pitch == 45.0


def test_reward_system_tracks_basic_survival_terms() -> None:
    connector = NullMinecraftConnector()
    builder = ObservationBuilder()
    reward_system = RewardSystem()

    obs = builder.build(connector.reset())
    next_obs = builder.build(connector.send_action(MinecraftAction(attack=True)))
    reward = reward_system.compute(obs, next_obs, MinecraftAction(attack=True))

    assert reward.total < 0.02
    assert "air_attack_penalty" in reward.terms


def test_training_and_evaluation_dry_run_write_manifest(tmp_path: Path) -> None:
    paths = MinecraftPaths(
        checkpoints_dir=tmp_path / "checkpoints",
        logs_dir=tmp_path / "logs",
        debug_dir=tmp_path / "debug",
        runs_dir=tmp_path / "runs",
        recordings_dir=tmp_path / "recordings",
        datasets_dir=tmp_path / "datasets",
        worlds_dir=tmp_path / "worlds",
    )
    config = MinecraftRuntimeConfig(max_episode_steps=8, run_id="unit_minecraft_phase_a", paths=paths)

    summary = TrainingRunner(config).dry_run(steps=3)
    assert summary.steps == 3
    assert (tmp_path / "checkpoints" / "unit_minecraft_phase_a" / "manifest.json").exists()

    evaluation = EvaluationRunner(config).run_phase_a_smoke(steps=3)
    assert evaluation.passed
    assert evaluation.connector == "null"
    assert evaluation.steps == 3


def test_debug_viewer_writes_observation(tmp_path: Path) -> None:
    connector = NullMinecraftConnector()
    obs = ObservationBuilder().build(connector.reset())

    path = DebugViewer(tmp_path).write_observation(obs)
    assert path.exists()
    assert "minecraft:oak_log" in path.read_text(encoding="utf-8")


def test_observation_builder_accepts_mineflayer_snapshot_shape() -> None:
    raw = {
        "tick": 12,
        "hp": 18.0,
        "hunger": 19.0,
        "position": [10.5, 64.0, -2.0],
        "yaw": 1.5,
        "pitch": -0.1,
        "selected_slot": 2,
        "item_in_hand": "minecraft:oak_log",
        "inventory": [{"item_id": "minecraft:oak_log", "count": 4, "slot": 36}],
        "nearby_blocks": [{"block_id": "minecraft:dirt", "x": 10, "y": 63, "z": -2, "distance": 1.0}],
        "nearby_entities": [{"entity_id": "7", "kind": "zombie", "x": 12, "y": 64, "z": -2, "distance": 2, "hostile": True}],
        "nearby_players": [{"username": "Valera", "entity_id": "42", "x": 9, "y": 64, "z": -1, "distance": 1.5}],
        "connection_state": "spawned",
        "events": ["observe"],
    }

    obs = ObservationBuilder().build(raw)
    assert obs.tick == 12
    assert obs.status.item_in_hand == "minecraft:oak_log"
    assert obs.inventory[0].count == 4
    assert obs.nearby_entities[0].hostile
    assert obs.nearby_players[0].username == "Valera"
