from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from src.skills.minecraft.env.types import MinecraftAction


class BridgeProtocolError(RuntimeError):
    pass


def encode_request(kind: str, payload: dict[str, Any] | None = None) -> bytes:
    message = {"type": kind, "payload": payload or {}}
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def decode_response(raw: bytes) -> dict[str, Any]:
    try:
        message = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeProtocolError(f"Invalid bridge response: {exc}") from exc

    if not isinstance(message, dict):
        raise BridgeProtocolError("Bridge response must be a JSON object.")
    if message.get("ok") is False:
        error = message.get("error", "unknown bridge error")
        raise BridgeProtocolError(str(error))

    payload = message.get("payload", message)
    if not isinstance(payload, dict):
        raise BridgeProtocolError("Bridge payload must be a JSON object.")
    return payload


def action_payload(action: MinecraftAction) -> dict[str, Any]:
    return asdict(action)
