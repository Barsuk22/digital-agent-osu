from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.skills.minecraft.actions import BodyConnector, look_delta, observation_preview
from src.skills.minecraft.actions.body_primitives import finite_position


@dataclass(frozen=True, slots=True)
class TargetPoint:
    x: float
    y: float
    z: float
    label: str = "target"


@dataclass(frozen=True, slots=True)
class LookAtResult:
    ok: bool
    verdict: str
    target: TargetPoint
    start: dict
    end: dict
    yaw_error_degrees: float | None
    pitch_error_degrees: float | None
    steps: list[dict] = field(default_factory=list)


def target_from_coords(x: float, y: float, z: float, label: str = "coords") -> TargetPoint:
    return TargetPoint(float(x), float(y), float(z), label=label)


def pick_target_from_observation(raw: dict, mode: str = "nearest_player") -> TargetPoint:
    if mode == "nearest_player":
        players = raw.get("nearby_players", [])
        if not players:
            raise ValueError("No nearby players in observation.")
        player = min(players, key=lambda item: float(item.get("distance", 0.0)))
        return TargetPoint(float(player["x"]), float(player["y"]) + 1.5, float(player["z"]), label=f"player:{player.get('username', '')}")

    if mode == "nearest_block":
        blocks = raw.get("nearby_blocks", [])
        if not blocks:
            raise ValueError("No nearby blocks in observation.")
        block = min(blocks, key=lambda item: float(item.get("distance", 0.0)))
        return TargetPoint(float(block["x"]) + 0.5, float(block["y"]) + 0.5, float(block["z"]) + 0.5, label=str(block.get("block_id", "block")))

    if mode == "nearest_entity":
        entities = raw.get("nearby_entities", [])
        if not entities:
            raise ValueError("No nearby entities in observation.")
        entity = min(entities, key=lambda item: float(item.get("distance", 0.0)))
        return TargetPoint(float(entity["x"]), float(entity["y"]) + 1.0, float(entity["z"]), label=str(entity.get("kind", "entity")))

    raise ValueError(f"Unsupported target mode: {mode}")


def compute_look_delta(raw: dict, target: TargetPoint) -> tuple[float, float]:
    position = finite_position(raw)
    if position is None:
        raise ValueError("Observation position is unavailable.")
    yaw = raw.get("yaw")
    pitch = raw.get("pitch")
    if not isinstance(yaw, int | float) or not isinstance(pitch, int | float):
        raise ValueError("Observation yaw/pitch is unavailable.")

    px, py, pz = position
    eye_y = py + 1.62
    dx = target.x - px
    dy = target.y - eye_y
    dz = target.z - pz
    horizontal = math.hypot(dx, dz)
    desired_yaw = math.atan2(-dx, -dz)
    desired_pitch = -math.atan2(dy, horizontal)
    return angle_delta_radians(float(yaw), desired_yaw), angle_delta_radians(float(pitch), desired_pitch)


def angle_delta_radians(current: float, target: float) -> float:
    return (target - current + math.pi) % (2.0 * math.pi) - math.pi


def radians_to_degrees(value: float) -> float:
    return value * 180.0 / math.pi


def clamp_degrees(value: float, max_abs: float) -> float:
    return max(-max_abs, min(max_abs, value))


def look_at_target(
    connector: BodyConnector,
    target: TargetPoint,
    max_steps: int = 4,
    tolerance_degrees: float = 3.0,
    max_step_degrees: float = 30.0,
    settle_ms: int = 120,
) -> LookAtResult:
    start_raw = connector.observe()
    steps: list[dict] = []
    current_raw = start_raw
    yaw_error = None
    pitch_error = None

    for index in range(max(1, int(max_steps))):
        yaw_delta, pitch_delta = compute_look_delta(current_raw, target)
        yaw_error = radians_to_degrees(yaw_delta)
        pitch_error = radians_to_degrees(pitch_delta)
        if abs(yaw_error) <= tolerance_degrees and abs(pitch_error) <= tolerance_degrees:
            break

        action_result = look_delta(
            connector,
            yaw_degrees=clamp_degrees(yaw_error, max_step_degrees),
            pitch_degrees=clamp_degrees(pitch_error, max_step_degrees),
            settle_ms=settle_ms,
        )
        current_raw = connector.observe()
        steps.append(
            {
                "index": index,
                "requested_yaw_degrees": clamp_degrees(yaw_error, max_step_degrees),
                "requested_pitch_degrees": clamp_degrees(pitch_error, max_step_degrees),
                "action": action_result.action,
                "after": observation_preview(current_raw),
            }
        )

    final_yaw_delta, final_pitch_delta = compute_look_delta(current_raw, target)
    yaw_error = radians_to_degrees(final_yaw_delta)
    pitch_error = radians_to_degrees(final_pitch_delta)
    ok = abs(yaw_error) <= tolerance_degrees and abs(pitch_error) <= tolerance_degrees

    return LookAtResult(
        ok=ok,
        verdict="look_at_target_ok" if ok else "look_at_target_not_aligned",
        target=target,
        start=observation_preview(start_raw),
        end=observation_preview(current_raw),
        yaw_error_degrees=yaw_error,
        pitch_error_degrees=pitch_error,
        steps=steps,
    )
