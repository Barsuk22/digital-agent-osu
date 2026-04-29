from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Protocol

from src.skills.minecraft.actions.body_primitives import horizontal_distance, observation_preview, position_delta
from src.skills.minecraft.actions.manual_control import build_manual_action
from src.skills.minecraft.env.types import MinecraftAction


class ActionConnector(Protocol):
    def observe(self) -> dict:
        ...

    def send_action(self, action: MinecraftAction) -> dict:
        ...


@dataclass(frozen=True, slots=True)
class ProbeStep:
    name: str
    action: MinecraftAction
    settle_ms: int


@dataclass(frozen=True, slots=True)
class ProbeStepResult:
    name: str
    sent_action: dict
    response_preview: dict
    after_preview: dict


@dataclass(frozen=True, slots=True)
class MovementProbeResult:
    ok: bool
    verdict: str
    start: dict
    end: dict
    position_delta: list[float] | None
    horizontal_distance: float | None
    yaw_delta: float | None
    steps: list[ProbeStepResult] = field(default_factory=list)


def yaw_delta(before: dict, after: dict) -> float | None:
    before_yaw = before.get("yaw")
    after_yaw = after.get("yaw")
    if not isinstance(before_yaw, int | float) or not isinstance(after_yaw, int | float):
        return None
    return float(after_yaw) - float(before_yaw)


def default_probe_steps(move_duration_ms: int = 500, look_degrees: float = 15.0, settle_ms: int = 700) -> list[ProbeStep]:
    return [
        ProbeStep("look_right", build_manual_action("look_right", look_degrees=look_degrees), settle_ms=150),
        ProbeStep("move_forward", build_manual_action("move_forward", duration_ms=move_duration_ms), settle_ms=settle_ms),
        ProbeStep("stop", build_manual_action("stop"), settle_ms=150),
    ]


def run_movement_probe(
    connector: ActionConnector,
    steps: list[ProbeStep] | None = None,
    min_horizontal_distance: float = 0.25,
    min_abs_yaw_delta: float = 0.05,
) -> MovementProbeResult:
    probe_steps = steps or default_probe_steps()
    start = connector.observe()
    step_results: list[ProbeStepResult] = []

    for step in probe_steps:
        response = connector.send_action(step.action)
        if step.settle_ms > 0:
            time.sleep(step.settle_ms / 1000.0)
        after = connector.observe()
        step_results.append(
            ProbeStepResult(
                name=step.name,
                sent_action=asdict(step.action),
                response_preview=observation_preview(response),
                after_preview=observation_preview(after),
            )
        )

    end = connector.observe()
    delta = position_delta(start, end)
    distance = horizontal_distance(delta)
    yaw = yaw_delta(start, end)

    if start.get("position_valid") is False or end.get("position_valid") is False:
        ok = False
        verdict = "position_invalid"
    elif distance is None:
        ok = False
        verdict = "position_unavailable"
    elif yaw is None:
        ok = False
        verdict = "yaw_unavailable"
    elif distance < min_horizontal_distance:
        ok = False
        verdict = "movement_too_small"
    elif abs(yaw) < min_abs_yaw_delta:
        ok = False
        verdict = "look_delta_too_small"
    else:
        ok = True
        verdict = "body_controls_ok"

    return MovementProbeResult(
        ok=ok,
        verdict=verdict,
        start=observation_preview(start),
        end=observation_preview(end),
        position_delta=delta,
        horizontal_distance=distance,
        yaw_delta=yaw,
        steps=step_results,
    )
