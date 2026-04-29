from __future__ import annotations

import json
import socket
import threading
from typing import Any

import pytest

from src.skills.minecraft.config import MinecraftBridgeConfig, MinecraftRuntimeConfig
from src.skills.minecraft.env import TcpMinecraftConnector, make_minecraft_connector
from src.skills.minecraft.env.bridge_protocol import BridgeProtocolError, decode_response, encode_request
from src.skills.minecraft.env.bridge_protocol import action_payload
from src.skills.minecraft.env.types import MinecraftAction


def observation_payload(tick: int = 0) -> dict[str, Any]:
    return {
        "tick": tick,
        "hp": 20.0,
        "hunger": 20.0,
        "armor": 0.0,
        "air": 300.0,
        "position": [0.0, 64.0, 0.0],
        "yaw": 0.0,
        "pitch": 0.0,
        "selected_slot": 0,
        "item_in_hand": "minecraft:air",
        "biome": "plains",
        "time_of_day": 1000,
        "inventory": [],
        "nearby_blocks": [],
        "nearby_entities": [],
        "nearby_players": [
            {
                "username": "Valera",
                "entity_id": "42",
                "x": 1.0,
                "y": 64.0,
                "z": 2.0,
                "distance": 3.0,
            }
        ],
        "events": ["mock"],
    }


class MockBridgeServer:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen()
        self.port = self._socket.getsockname()[1]
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._closed.set()
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                pass
        except OSError:
            pass
        self._thread.join(timeout=1.0)
        self._socket.close()

    def _serve(self) -> None:
        while not self._closed.is_set():
            try:
                conn, _ = self._socket.accept()
            except OSError:
                return
            with conn:
                raw = self._read_line(conn)
                if not raw:
                    continue
                request = json.loads(raw.decode("utf-8"))
                self.requests.append(request)
                response = self._response_for(request)
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))

    @staticmethod
    def _read_line(conn: socket.socket) -> bytes:
        chunks: list[bytes] = []
        while True:
            chunk = conn.recv(1)
            if chunk in {b"", b"\n"}:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _response_for(request: dict[str, Any]) -> dict[str, Any]:
        kind = request.get("type")
        if kind == "ping":
            return {"ok": True, "payload": {"message": "ok"}}
        if kind == "action":
            return {"ok": True, "payload": observation_payload(tick=2)}
        if kind in {"reset", "observe", "close"}:
            return {"ok": True, "payload": observation_payload(tick=1)}
        return {"ok": False, "error": f"unsupported request: {kind}"}


def test_protocol_encode_decode_roundtrip() -> None:
    raw = encode_request("ping")
    assert raw.endswith(b"\n")
    assert json.loads(raw.decode("utf-8")) == {"type": "ping", "payload": {}}

    payload = decode_response(b'{"ok":true,"payload":{"message":"ok"}}')
    assert payload == {"message": "ok"}

    with pytest.raises(BridgeProtocolError):
        decode_response(b'{"ok":false,"error":"boom"}')


def test_action_payload_includes_low_level_command_fields() -> None:
    payload = action_payload(
        MinecraftAction(
            command="look_delta",
            camera_yaw_delta=12.0,
            camera_pitch_delta=-3.0,
            duration_ms=90,
            chat_message="hello",
        )
    )
    assert payload["command"] == "look_delta"
    assert payload["camera_yaw_delta"] == 12.0
    assert payload["camera_pitch_delta"] == -3.0
    assert payload["duration_ms"] == 90
    assert payload["chat_message"] == "hello"


def test_tcp_connector_talks_to_mock_bridge() -> None:
    server = MockBridgeServer()
    server.start()
    try:
        connector = TcpMinecraftConnector(MinecraftBridgeConfig(port=server.port, timeout_seconds=1.0))
        health = connector.health_check()
        assert health.reachable
        assert health.message == "ok"

        obs = connector.reset()
        assert obs["tick"] == 1

        next_obs = connector.send_action(MinecraftAction(command="move_forward", forward=1.0))
        assert next_obs["tick"] == 2
        assert server.requests[-1]["type"] == "action"
        assert server.requests[-1]["payload"]["command"] == "move_forward"
        assert server.requests[-1]["payload"]["forward"] == 1.0
    finally:
        server.close()


def test_connector_factory_selects_tcp() -> None:
    config = MinecraftRuntimeConfig(connector="tcp", bridge=MinecraftBridgeConfig(port=12345))
    connector = make_minecraft_connector(config)
    assert isinstance(connector, TcpMinecraftConnector)

    with pytest.raises(ValueError):
        make_minecraft_connector(MinecraftRuntimeConfig(connector="unknown"))
