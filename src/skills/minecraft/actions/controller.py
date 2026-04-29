from __future__ import annotations

from src.skills.minecraft.env.connector import MinecraftConnector
from src.skills.minecraft.env.types import MinecraftAction


class ActionController:
    def __init__(self, connector: MinecraftConnector) -> None:
        self.connector = connector

    def send(self, action: MinecraftAction) -> dict:
        safe_action = self._sanitize(action)
        return self.connector.send_action(safe_action)

    @staticmethod
    def _sanitize(action: MinecraftAction) -> MinecraftAction:
        allowed_commands = {
            "noop",
            "move_forward",
            "move_back",
            "move_left",
            "move_right",
            "jump",
            "sneak",
            "sprint",
            "look_delta",
            "chat",
            "stop",
        }
        command = action.command if action.command in allowed_commands else "noop"
        return MinecraftAction(
            command=command,
            forward=max(-1.0, min(1.0, action.forward)),
            strafe=max(-1.0, min(1.0, action.strafe)),
            jump=bool(action.jump),
            sneak=bool(action.sneak),
            sprint=bool(action.sprint),
            attack=bool(action.attack),
            use=bool(action.use),
            drop=bool(action.drop),
            hotbar_slot=None if action.hotbar_slot is None else max(0, min(8, int(action.hotbar_slot))),
            camera_yaw_delta=max(-45.0, min(45.0, action.camera_yaw_delta)),
            camera_pitch_delta=max(-45.0, min(45.0, action.camera_pitch_delta)),
            duration_ms=max(20, min(500, int(action.duration_ms))),
            chat_message=None if action.chat_message is None else str(action.chat_message)[:240],
        )
