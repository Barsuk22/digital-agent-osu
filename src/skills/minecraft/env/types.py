from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class InventoryItem:
    item_id: str
    count: int
    slot: int | None = None


@dataclass(slots=True)
class BlockView:
    block_id: str
    x: int
    y: int
    z: int
    distance: float


@dataclass(slots=True)
class EntityView:
    entity_id: str
    kind: str
    x: float
    y: float
    z: float
    distance: float
    hostile: bool = False


@dataclass(slots=True)
class PlayerView:
    username: str
    entity_id: str
    x: float
    y: float
    z: float
    distance: float


@dataclass(slots=True)
class MinecraftStatus:
    hp: float = 20.0
    hunger: float = 20.0
    armor: float = 0.0
    air: float = 300.0
    selected_slot: int = 0
    item_in_hand: str = "minecraft:air"
    biome: str = "unknown"
    time_of_day: int = 0


@dataclass(slots=True)
class MinecraftObservation:
    tick: int
    status: MinecraftStatus
    position: tuple[float, float, float]
    yaw: float
    pitch: float
    inventory: list[InventoryItem] = field(default_factory=list)
    nearby_blocks: list[BlockView] = field(default_factory=list)
    nearby_entities: list[EntityView] = field(default_factory=list)
    nearby_players: list[PlayerView] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    screen_frame: Any | None = None
    frame_stack: tuple[Any, ...] = ()


@dataclass(slots=True)
class MinecraftAction:
    command: str = "noop"
    forward: float = 0.0
    strafe: float = 0.0
    jump: bool = False
    sneak: bool = False
    sprint: bool = False
    attack: bool = False
    use: bool = False
    drop: bool = False
    hotbar_slot: int | None = None
    camera_yaw_delta: float = 0.0
    camera_pitch_delta: float = 0.0
    duration_ms: int = 120
    chat_message: str | None = None


@dataclass(slots=True)
class EnvStepResult:
    observation: MinecraftObservation
    reward: float
    done: bool
    info: dict[str, Any]
