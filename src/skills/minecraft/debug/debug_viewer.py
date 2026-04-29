from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.skills.minecraft.env.types import MinecraftObservation


class DebugViewer:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_observation(self, observation: MinecraftObservation, name: str = "observation.json") -> Path:
        path = self.output_dir / name
        path.write_text(json.dumps(asdict(observation), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path
