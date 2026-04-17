from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from src.skills.osu.viewer.replay_models import ReplayFrame


def save_replay(frames: List[ReplayFrame], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(frame) for frame in frames]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_replay(path: str | Path) -> List[ReplayFrame]:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [ReplayFrame(**item) for item in payload]