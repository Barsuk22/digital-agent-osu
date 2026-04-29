from __future__ import annotations

from collections import deque
from typing import Any

from src.skills.minecraft.env.types import (
    BlockView,
    EntityView,
    InventoryItem,
    MinecraftObservation,
    MinecraftStatus,
    PlayerView,
)


class ObservationBuilder:
    def __init__(self, frame_stack_size: int = 4) -> None:
        self.frame_stack_size = max(1, int(frame_stack_size))
        self._frames: deque[Any] = deque(maxlen=self.frame_stack_size)

    def reset(self) -> None:
        self._frames.clear()

    def build(self, raw: dict[str, Any]) -> MinecraftObservation:
        frame = raw.get("screen_frame")
        if frame is not None:
            self._frames.append(frame)

        status = MinecraftStatus(
            hp=float(raw.get("hp", 20.0)),
            hunger=float(raw.get("hunger", 20.0)),
            armor=float(raw.get("armor", 0.0)),
            air=float(raw.get("air", 300.0)),
            selected_slot=int(raw.get("selected_slot", 0)),
            item_in_hand=str(raw.get("item_in_hand", "minecraft:air")),
            biome=str(raw.get("biome", "unknown")),
            time_of_day=int(raw.get("time_of_day", 0)),
        )

        return MinecraftObservation(
            tick=int(raw.get("tick", 0)),
            status=status,
            position=tuple(raw.get("position", (0.0, 0.0, 0.0))),  # type: ignore[arg-type]
            yaw=float(raw.get("yaw", 0.0)),
            pitch=float(raw.get("pitch", 0.0)),
            inventory=[self._inventory_item(item) for item in raw.get("inventory", [])],
            nearby_blocks=[self._block_view(item) for item in raw.get("nearby_blocks", [])],
            nearby_entities=[self._entity_view(item) for item in raw.get("nearby_entities", [])],
            nearby_players=[self._player_view(item) for item in raw.get("nearby_players", [])],
            events=[str(item) for item in raw.get("events", [])],
            screen_frame=frame,
            frame_stack=tuple(self._frames),
        )

    @staticmethod
    def _inventory_item(raw: dict[str, Any]) -> InventoryItem:
        return InventoryItem(
            item_id=str(raw.get("item_id", "minecraft:air")),
            count=int(raw.get("count", 0)),
            slot=raw.get("slot"),
        )

    @staticmethod
    def _block_view(raw: dict[str, Any]) -> BlockView:
        return BlockView(
            block_id=str(raw.get("block_id", "minecraft:air")),
            x=int(raw.get("x", 0)),
            y=int(raw.get("y", 0)),
            z=int(raw.get("z", 0)),
            distance=float(raw.get("distance", 0.0)),
        )

    @staticmethod
    def _entity_view(raw: dict[str, Any]) -> EntityView:
        return EntityView(
            entity_id=str(raw.get("entity_id", "")),
            kind=str(raw.get("kind", "unknown")),
            x=float(raw.get("x", 0.0)),
            y=float(raw.get("y", 0.0)),
            z=float(raw.get("z", 0.0)),
            distance=float(raw.get("distance", 0.0)),
            hostile=bool(raw.get("hostile", False)),
        )

    @staticmethod
    def _player_view(raw: dict[str, Any]) -> PlayerView:
        return PlayerView(
            username=str(raw.get("username", "")),
            entity_id=str(raw.get("entity_id", "")),
            x=float(raw.get("x", 0.0)),
            y=float(raw.get("y", 0.0)),
            z=float(raw.get("z", 0.0)),
            distance=float(raw.get("distance", 0.0)),
        )
