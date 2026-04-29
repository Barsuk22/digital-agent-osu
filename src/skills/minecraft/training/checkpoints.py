from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CheckpointManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        path = self.root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_manifest(self, run_id: str, payload: dict[str, Any]) -> Path:
        path = self.run_dir(run_id) / "manifest.json"
        manifest = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": self._json_ready(payload),
        }
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _json_ready(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if is_dataclass(value):
            return CheckpointManager._json_ready(asdict(value))
        if isinstance(value, dict):
            return {str(key): CheckpointManager._json_ready(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [CheckpointManager._json_ready(item) for item in value]
        return value
