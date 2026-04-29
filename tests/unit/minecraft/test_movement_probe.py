from __future__ import annotations

from src.skills.minecraft.actions import default_probe_steps, run_movement_probe
from src.skills.minecraft.env.types import MinecraftAction


class FakeProbeConnector:
    def __init__(self) -> None:
        self.index = 0
        self.actions: list[MinecraftAction] = []
        self.observations = [
            self._obs(x=0.0, z=0.0, yaw=0.0, event="start"),
            self._obs(x=0.0, z=0.0, yaw=0.3, event="after_look"),
            self._obs(x=0.8, z=0.2, yaw=0.3, event="after_move"),
            self._obs(x=0.8, z=0.2, yaw=0.3, event="after_stop"),
            self._obs(x=0.8, z=0.2, yaw=0.3, event="end"),
        ]

    def observe(self) -> dict:
        obs = self.observations[min(self.index, len(self.observations) - 1)]
        self.index += 1
        return obs

    def send_action(self, action: MinecraftAction) -> dict:
        self.actions.append(action)
        return self._obs(x=0.0, z=0.0, yaw=0.0, event=f"action:{action.command}")

    @staticmethod
    def _obs(x: float, z: float, yaw: float, event: str) -> dict:
        return {
            "connection_state": "spawned",
            "username": "AgentGirl",
            "position": [x, 71.0, z],
            "position_valid": True,
            "velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
            "yaw": yaw,
            "pitch": 0.0,
            "on_ground": True,
            "physics_enabled": True,
            "control_state": {},
            "hp": 20.0,
            "hunger": 20.0,
            "nearby_entities": [],
            "nearby_players": [],
            "nearby_blocks": [],
            "events": [event],
        }


def test_default_probe_steps_are_safe_and_short() -> None:
    steps = default_probe_steps(move_duration_ms=400, look_degrees=10.0, settle_ms=600)
    assert [step.name for step in steps] == ["look_right", "move_forward", "stop"]
    assert steps[0].action.command == "look_delta"
    assert steps[1].action.command == "move_forward"
    assert steps[1].action.duration_ms == 400
    assert steps[2].action.command == "stop"


def test_run_movement_probe_returns_success_verdict() -> None:
    connector = FakeProbeConnector()
    result = run_movement_probe(connector, min_horizontal_distance=0.25, min_abs_yaw_delta=0.05)
    assert result.ok
    assert result.verdict == "body_controls_ok"
    assert result.horizontal_distance is not None
    assert result.horizontal_distance > 0.25
    assert result.yaw_delta is not None
    assert result.yaw_delta > 0.05
    assert [action.command for action in connector.actions] == ["look_delta", "move_forward", "stop"]
