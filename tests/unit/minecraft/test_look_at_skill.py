from __future__ import annotations

import math

import pytest

from src.skills.minecraft.env.types import MinecraftAction
from src.skills.minecraft.skills import (
    TargetPoint,
    angle_delta_radians,
    compute_look_delta,
    look_at_target,
    pick_target_from_observation,
)


def obs(yaw: float = 0.0, pitch: float = 0.0) -> dict:
    return {
        "position": [0.0, 64.0, 0.0],
        "position_valid": True,
        "yaw": yaw,
        "pitch": pitch,
        "nearby_players": [{"username": "Valera", "x": 0.0, "y": 64.0, "z": -4.0, "distance": 4.0}],
        "nearby_blocks": [{"block_id": "minecraft:oak_log", "x": 2, "y": 64, "z": -2, "distance": 3.0}],
        "nearby_entities": [],
        "events": [],
    }


class FakeLookConnector:
    def __init__(self) -> None:
        self.current_yaw = 0.0
        self.current_pitch = 0.0
        self.actions: list[MinecraftAction] = []

    def observe(self) -> dict:
        return obs(yaw=self.current_yaw, pitch=self.current_pitch)

    def send_action(self, action: MinecraftAction) -> dict:
        self.actions.append(action)
        self.current_yaw += math.radians(action.camera_yaw_delta)
        self.current_pitch += math.radians(action.camera_pitch_delta)
        return self.observe()


def test_angle_delta_wraps_short_way() -> None:
    assert angle_delta_radians(math.radians(179), math.radians(-179)) == pytest.approx(math.radians(2))
    assert angle_delta_radians(math.radians(-179), math.radians(179)) == pytest.approx(math.radians(-2))


def test_compute_look_delta_to_front_target_is_small_yaw() -> None:
    yaw_delta, _ = compute_look_delta(obs(yaw=0.0), TargetPoint(0.0, 65.62, -4.0))
    assert yaw_delta == pytest.approx(0.0)


def test_pick_target_from_observation() -> None:
    player = pick_target_from_observation(obs(), "nearest_player")
    block = pick_target_from_observation(obs(), "nearest_block")
    assert player.label == "player:Valera"
    assert block.label == "minecraft:oak_log"
    assert block.x == pytest.approx(2.5)


def test_look_at_target_turns_until_aligned() -> None:
    connector = FakeLookConnector()
    target = TargetPoint(-4.0, 65.62, 0.0)
    result = look_at_target(connector, target, max_steps=4, tolerance_degrees=1.0, max_step_degrees=45.0, settle_ms=0)
    assert result.ok
    assert result.verdict == "look_at_target_ok"
    assert result.yaw_error_degrees is not None
    assert abs(result.yaw_error_degrees) <= 1.0
    assert connector.actions
