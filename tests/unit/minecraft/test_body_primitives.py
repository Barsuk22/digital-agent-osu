from __future__ import annotations

import pytest

from src.skills.minecraft.actions import (
    finite_position,
    look_delta,
    measure_delta,
    move_impulse,
    step_forward_and_measure,
    stop_all,
    turn_and_step,
)
from src.skills.minecraft.env.types import MinecraftAction


class FakeBodyConnector:
    def __init__(self) -> None:
        self.index = 0
        self.actions: list[MinecraftAction] = []
        self.observations = [
            self._obs(0.0, 0.0, 0.0),
            self._obs(0.0, 0.0, 0.2),
            self._obs(0.5, 0.1, 0.2),
            self._obs(0.5, 0.1, 0.2),
            self._obs(0.5, 0.1, 0.2),
            self._obs(0.5, 0.1, 0.2),
            self._obs(1.0, 0.2, 0.2),
            self._obs(1.0, 0.2, 0.2),
        ]

    def observe(self) -> dict:
        obs = self.observations[min(self.index, len(self.observations) - 1)]
        self.index += 1
        return obs

    def send_action(self, action: MinecraftAction) -> dict:
        self.actions.append(action)
        return self._obs(0.0, 0.0, 0.0)

    @staticmethod
    def _obs(x: float, z: float, yaw: float) -> dict:
        return {
            "position": [x, 71.0, z],
            "position_valid": True,
            "yaw": yaw,
            "pitch": 0.0,
            "nearby_entities": [],
            "nearby_players": [],
            "nearby_blocks": [],
            "events": [],
        }


def test_measure_delta_helpers() -> None:
    before = {"position": [1.0, 2.0, 3.0], "yaw": 0.1, "pitch": 0.0}
    after = {"position": [2.0, 2.0, 5.0], "yaw": 0.3, "pitch": -0.1}
    assert finite_position(before) == (1.0, 2.0, 3.0)
    measured = measure_delta(before, after)
    assert measured["position_delta"] == [1.0, 0.0, 2.0]
    assert measured["horizontal_distance"] == pytest.approx(2.236, rel=0.01)
    assert measured["yaw_delta"] == pytest.approx(0.2)
    assert measured["pitch_delta"] == pytest.approx(-0.1)


def test_body_primitives_send_expected_actions() -> None:
    connector = FakeBodyConnector()
    look = look_delta(connector, yaw_degrees=10.0, settle_ms=0)
    move = step_forward_and_measure(connector, duration_ms=250, settle_ms=0)
    stop = stop_all(connector, settle_ms=0)

    assert look.action["command"] == "look_delta"
    assert look.yaw_delta == pytest.approx(0.2)
    assert move.action["command"] == "move_forward"
    assert move.horizontal_distance is not None
    assert stop.action["command"] == "stop"
    assert [action.command for action in connector.actions] == ["look_delta", "move_forward", "stop"]


def test_turn_and_step_composes_primitives() -> None:
    connector = FakeBodyConnector()
    results = turn_and_step(connector, yaw_degrees=15.0, move_duration_ms=300, look_settle_ms=0, move_settle_ms=0)
    assert len(results) == 3
    assert [item.action["command"] for item in results] == ["look_delta", "move_forward", "stop"]


def test_move_impulse_rejects_unknown_command() -> None:
    with pytest.raises(ValueError):
        move_impulse(FakeBodyConnector(), command="fly")
