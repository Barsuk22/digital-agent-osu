from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from src.skills.minecraft.env.types import MinecraftAction


@dataclass(slots=True)
class ConnectorState:
    tick: int = 0
    hp: float = 20.0
    hunger: float = 20.0
    armor: float = 0.0
    air: float = 300.0
    position: tuple[float, float, float] = (0.0, 64.0, 0.0)
    yaw: float = 0.0
    pitch: float = 0.0
    selected_slot: int = 0
    item_in_hand: str = "minecraft:air"
    biome: str = "plains"
    time_of_day: int = 1000
    inventory: list[dict[str, Any]] = field(default_factory=list)
    nearby_blocks: list[dict[str, Any]] = field(default_factory=list)
    nearby_entities: list[dict[str, Any]] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    screen_frame: Any | None = None


class MinecraftConnector(Protocol):
    def reset(self) -> dict[str, Any]:
        ...

    def observe(self) -> dict[str, Any]:
        ...

    def send_action(self, action: MinecraftAction) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


class NullMinecraftConnector:
    """Deterministic dry-run connector used until a real Minecraft transport exists."""

    def __init__(self) -> None:
        self.state = ConnectorState()
        self.last_action = MinecraftAction()

    def reset(self) -> dict[str, Any]:
        self.state = ConnectorState(
            nearby_blocks=[
                {"block_id": "minecraft:oak_log", "x": 4, "y": 64, "z": 3, "distance": 5.0},
                {"block_id": "minecraft:dirt", "x": 0, "y": 63, "z": 0, "distance": 1.0},
            ],
            events=["reset"],
        )
        self.last_action = MinecraftAction()
        return self.observe()

    def observe(self) -> dict[str, Any]:
        return {
            "tick": self.state.tick,
            "hp": self.state.hp,
            "hunger": self.state.hunger,
            "armor": self.state.armor,
            "air": self.state.air,
            "position": self.state.position,
            "yaw": self.state.yaw,
            "pitch": self.state.pitch,
            "selected_slot": self.state.selected_slot,
            "item_in_hand": self.state.item_in_hand,
            "biome": self.state.biome,
            "time_of_day": self.state.time_of_day,
            "inventory": list(self.state.inventory),
            "nearby_blocks": list(self.state.nearby_blocks),
            "nearby_entities": list(self.state.nearby_entities),
            "events": list(self.state.events),
            "screen_frame": self.state.screen_frame,
        }

    def send_action(self, action: MinecraftAction) -> dict[str, Any]:
        self.last_action = action
        x, y, z = self.state.position
        self.state.tick += 1
        self.state.yaw += action.camera_yaw_delta
        self.state.pitch = max(-90.0, min(90.0, self.state.pitch + action.camera_pitch_delta))
        self.state.position = (x + action.strafe * 0.1, y + (0.2 if action.jump else 0.0), z + action.forward * 0.1)
        self.state.selected_slot = action.hotbar_slot if action.hotbar_slot is not None else self.state.selected_slot
        self.state.events = ["action_applied"]
        return self.observe()

    def close(self) -> None:
        self.state.events = ["closed"]
