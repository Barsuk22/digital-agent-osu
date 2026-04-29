from __future__ import annotations

from dataclasses import dataclass

from src.skills.minecraft.env.types import MinecraftAction


@dataclass(frozen=True, slots=True)
class ManualActionSpec:
    name: str
    action: MinecraftAction
    description: str


def manual_action_specs(duration_ms: int = 120, look_degrees: float = 12.0, chat_message: str | None = None) -> dict[str, ManualActionSpec]:
    duration = max(20, min(500, int(duration_ms)))
    look = max(1.0, min(45.0, float(look_degrees)))
    message = chat_message or "AgentGirl online."

    specs = [
        ManualActionSpec("noop", MinecraftAction(command="noop", duration_ms=duration), "Do nothing and read observation."),
        ManualActionSpec(
            "move_forward",
            MinecraftAction(command="move_forward", forward=1.0, duration_ms=duration),
            "Move forward briefly.",
        ),
        ManualActionSpec(
            "move_back",
            MinecraftAction(command="move_back", forward=-1.0, duration_ms=duration),
            "Move backward briefly.",
        ),
        ManualActionSpec(
            "move_left",
            MinecraftAction(command="move_left", strafe=-1.0, duration_ms=duration),
            "Strafe left briefly.",
        ),
        ManualActionSpec(
            "move_right",
            MinecraftAction(command="move_right", strafe=1.0, duration_ms=duration),
            "Strafe right briefly.",
        ),
        ManualActionSpec("jump", MinecraftAction(command="jump", jump=True, duration_ms=duration), "Jump briefly."),
        ManualActionSpec("sneak", MinecraftAction(command="sneak", sneak=True, duration_ms=duration), "Sneak briefly."),
        ManualActionSpec("sprint", MinecraftAction(command="sprint", sprint=True, forward=1.0, duration_ms=duration), "Sprint forward briefly."),
        ManualActionSpec(
            "look_left",
            MinecraftAction(command="look_delta", camera_yaw_delta=-look, duration_ms=duration),
            "Look left by a small delta.",
        ),
        ManualActionSpec(
            "look_right",
            MinecraftAction(command="look_delta", camera_yaw_delta=look, duration_ms=duration),
            "Look right by a small delta.",
        ),
        ManualActionSpec(
            "look_up",
            MinecraftAction(command="look_delta", camera_pitch_delta=-look, duration_ms=duration),
            "Look up by a small delta.",
        ),
        ManualActionSpec(
            "look_down",
            MinecraftAction(command="look_delta", camera_pitch_delta=look, duration_ms=duration),
            "Look down by a small delta.",
        ),
        ManualActionSpec(
            "chat",
            MinecraftAction(command="chat", chat_message=message, duration_ms=duration),
            "Send a short chat message.",
        ),
        ManualActionSpec("stop", MinecraftAction(command="stop", duration_ms=duration), "Release all controls."),
    ]
    return {spec.name: spec for spec in specs}


def build_manual_action(name: str, duration_ms: int = 120, look_degrees: float = 12.0, chat_message: str | None = None) -> MinecraftAction:
    specs = manual_action_specs(duration_ms=duration_ms, look_degrees=look_degrees, chat_message=chat_message)
    if name not in specs:
        allowed = ", ".join(sorted(specs))
        raise ValueError(f"Unknown manual Minecraft action '{name}'. Allowed: {allowed}")
    return specs[name].action
