from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any

from src.skills.minecraft.config import MinecraftBridgeConfig
from src.skills.minecraft.env.bridge_protocol import action_payload, decode_response, encode_request
from src.skills.minecraft.env.types import MinecraftAction


@dataclass(slots=True)
class BridgeHealth:
    reachable: bool
    message: str


class TcpMinecraftConnector:
    def __init__(self, config: MinecraftBridgeConfig) -> None:
        self.config = config

    def reset(self) -> dict[str, Any]:
        return self._request("reset")

    def observe(self) -> dict[str, Any]:
        return self._request("observe")

    def send_action(self, action: MinecraftAction) -> dict[str, Any]:
        return self._request("action", action_payload(action))

    def close(self) -> None:
        try:
            self._request("close")
        except OSError:
            return

    def health_check(self) -> BridgeHealth:
        try:
            payload = self._request("ping")
        except OSError as exc:
            return BridgeHealth(reachable=False, message=str(exc))
        return BridgeHealth(reachable=True, message=str(payload.get("message", "ok")))

    def _request(self, kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with socket.create_connection(
            (self.config.host, self.config.port),
            timeout=self.config.timeout_seconds,
        ) as sock:
            sock.settimeout(self.config.timeout_seconds)
            sock.sendall(encode_request(kind, payload))
            return decode_response(self._read_line(sock))

    @staticmethod
    def _read_line(sock: socket.socket) -> bytes:
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(1)
            if chunk == b"":
                break
            if chunk == b"\n":
                break
            chunks.append(chunk)
        return b"".join(chunks)
