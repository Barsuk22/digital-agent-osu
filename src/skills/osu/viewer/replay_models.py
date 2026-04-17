from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List


@dataclass(slots=True)
class ReplayFrame:
    time_ms: float
    cursor_x: float
    cursor_y: float
    click_down: bool
    judgement: str
    combo: int
    accuracy: float
    reward: float = 0.0
    score_value: int = 0
    popup_x: float | None = None
    popup_y: float | None = None


def save_replay(frames: List[ReplayFrame], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(frame) for frame in frames]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_replay(path: str | Path) -> List[ReplayFrame]:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [ReplayFrame(**item) for item in payload]