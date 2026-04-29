from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from typing import Protocol

from src.skills.minecraft.env.types import MinecraftAction


class BodyConnector(Protocol):
    def observe(self) -> dict:
        ...

    def send_action(self, action: MinecraftAction) -> dict:
        ...


@dataclass(frozen=True, slots=True)
class ActionResult:
    action: dict
    response: dict
    before: dict
    after: dict
    position_delta: list[float] | None
    horizontal_distance: float | None
    yaw_delta: float | None
    pitch_delta: float | None


def observation_preview(raw: dict) -> dict:
    return {
        "connection_state": raw.get("connection_state"),
        "username": raw.get("username"),
        "position": raw.get("position"),
        "position_valid": raw.get("position_valid"),
        "velocity": raw.get("velocity"),
        "yaw": raw.get("yaw"),
        "pitch": raw.get("pitch"),
        "on_ground": raw.get("on_ground"),
        "physics_enabled": raw.get("physics_enabled"),
        "control_state": raw.get("control_state"),
        "hp": raw.get("hp"),
        "hunger": raw.get("hunger", raw.get("food")),
        "selected_slot": raw.get("selected_slot"),
        "item_in_hand": raw.get("item_in_hand"),
        "nearby_entities": len(raw.get("nearby_entities", [])),
        "nearby_players": len(raw.get("nearby_players", [])),
        "nearby_blocks": len(raw.get("nearby_blocks", [])),
        "events": raw.get("events", []),
    }


def finite_position(raw: dict) -> tuple[float, float, float] | None:
    position = raw.get("position")
    if not isinstance(position, list | tuple) or len(position) != 3:
        return None
    if not all(isinstance(value, int | float) for value in position):
        return None
    return float(position[0]), float(position[1]), float(position[2])


def position_delta(before: dict, after: dict) -> list[float] | None:
    before_pos = finite_position(before)
    after_pos = finite_position(after)
    if before_pos is None or after_pos is None:
        return None
    return [after_pos[index] - before_pos[index] for index in range(3)]


def horizontal_distance(delta: list[float] | None) -> float | None:
    if delta is None:
        return None
    return math.hypot(delta[0], delta[2])


def numeric_delta(before: dict, after: dict, key: str) -> float | None:
    before_value = before.get(key)
    after_value = after.get(key)
    if not isinstance(before_value, int | float) or not isinstance(after_value, int | float):
        return None
    return float(after_value) - float(before_value)


def measure_delta(before: dict, after: dict) -> dict:
    delta = position_delta(before, after)
    return {
        "position_delta": delta,
        "horizontal_distance": horizontal_distance(delta),
        "yaw_delta": numeric_delta(before, after, "yaw"),
        "pitch_delta": numeric_delta(before, after, "pitch"),
    }


def observe(connector: BodyConnector) -> dict:
    return connector.observe()


def stop_all(connector: BodyConnector, settle_ms: int = 120) -> ActionResult:
    return send_and_measure(connector, MinecraftAction(command="stop"), settle_ms=settle_ms)


def look_delta(connector: BodyConnector, yaw_degrees: float = 0.0, pitch_degrees: float = 0.0, settle_ms: int = 120) -> ActionResult:
    action = MinecraftAction(
        command="look_delta",
        camera_yaw_delta=max(-45.0, min(45.0, float(yaw_degrees))),
        camera_pitch_delta=max(-45.0, min(45.0, float(pitch_degrees))),
    )
    return send_and_measure(connector, action, settle_ms=settle_ms)


def move_impulse(
    connector: BodyConnector,
    command: str = "move_forward",
    duration_ms: int = 300,
    settle_ms: int = 300,
) -> ActionResult:
    if command not in {"move_forward", "move_back", "move_left", "move_right", "jump", "sneak", "sprint"}:
        raise ValueError(f"Unsupported movement command: {command}")
    action = _movement_action(command, duration_ms=duration_ms)
    return send_and_measure(connector, action, settle_ms=settle_ms)


def step_forward_and_measure(connector: BodyConnector, duration_ms: int = 500, settle_ms: int = 700) -> ActionResult:
    return move_impulse(connector, command="move_forward", duration_ms=duration_ms, settle_ms=settle_ms)


def turn_and_step(
    connector: BodyConnector,
    yaw_degrees: float = 15.0,
    move_duration_ms: int = 500,
    look_settle_ms: int = 150,
    move_settle_ms: int = 700,
) -> list[ActionResult]:
    return [
        look_delta(connector, yaw_degrees=yaw_degrees, settle_ms=look_settle_ms),
        step_forward_and_measure(connector, duration_ms=move_duration_ms, settle_ms=move_settle_ms),
        stop_all(connector, settle_ms=150),
    ]


def send_and_measure(connector: BodyConnector, action: MinecraftAction, settle_ms: int = 120) -> ActionResult:
    before = connector.observe()
    response = connector.send_action(action)
    if settle_ms > 0:
        time.sleep(settle_ms / 1000.0)
    after = connector.observe()
    measured = measure_delta(before, after)
    return ActionResult(
        action=asdict(action),
        response=observation_preview(response),
        before=observation_preview(before),
        after=observation_preview(after),
        position_delta=measured["position_delta"],
        horizontal_distance=measured["horizontal_distance"],
        yaw_delta=measured["yaw_delta"],
        pitch_delta=measured["pitch_delta"],
    )


def _movement_action(command: str, duration_ms: int) -> MinecraftAction:
    duration = max(20, min(500, int(duration_ms)))
    if command == "move_forward":
        return MinecraftAction(command=command, forward=1.0, duration_ms=duration)
    if command == "move_back":
        return MinecraftAction(command=command, forward=-1.0, duration_ms=duration)
    if command == "move_left":
        return MinecraftAction(command=command, strafe=-1.0, duration_ms=duration)
    if command == "move_right":
        return MinecraftAction(command=command, strafe=1.0, duration_ms=duration)
    if command == "jump":
        return MinecraftAction(command=command, jump=True, duration_ms=duration)
    if command == "sneak":
        return MinecraftAction(command=command, sneak=True, duration_ms=duration)
    if command == "sprint":
        return MinecraftAction(command=command, sprint=True, forward=1.0, duration_ms=duration)
    raise ValueError(f"Unsupported movement command: {command}")
