from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.skills.minecraft.config import MinecraftBridgeConfig, MinecraftRuntimeConfig
from src.skills.minecraft.env import TcpMinecraftConnector
from src.skills.minecraft.evaluation import EvaluationRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Minecraft Phase A smoke check.")
    parser.add_argument("--connector", choices=["null", "tcp"], default="null")
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4711)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def observation_preview(raw: dict) -> dict:
    return {
        "connection_state": raw.get("connection_state"),
        "username": raw.get("username"),
        "position": raw.get("position"),
        "hp": raw.get("hp"),
        "hunger": raw.get("hunger", raw.get("food")),
        "selected_slot": raw.get("selected_slot"),
        "item_in_hand": raw.get("item_in_hand"),
        "nearby_entities": len(raw.get("nearby_entities", [])),
        "nearby_players": len(raw.get("nearby_players", [])),
        "nearby_blocks": len(raw.get("nearby_blocks", [])),
        "events": raw.get("events", []),
    }


def main() -> int:
    args = parse_args()
    bridge = MinecraftBridgeConfig(host=args.host, port=args.port, timeout_seconds=args.timeout)
    run_id = args.run_id or f"minecraft_phase_a_{args.connector}_smoke"
    config = MinecraftRuntimeConfig(connector=args.connector, bridge=bridge, run_id=run_id)
    tcp_connector = TcpMinecraftConnector(bridge) if args.connector == "tcp" else None
    health_payload = None
    preview = None

    if args.connector == "tcp":
        health = tcp_connector.health_check()
        if not health.reachable:
            print(json.dumps({"ok": False, "stage": "tcp_health", "message": health.message}, indent=2))
            return 2
        health_payload = {"reachable": health.reachable, "message": health.message}

    summary = EvaluationRunner(config).run_phase_a_smoke(steps=args.steps)
    if tcp_connector is not None:
        preview = observation_preview(tcp_connector.observe())

    print(
        json.dumps(
            {
                "ok": summary.passed,
                "connector": args.connector,
                "bridge": {"host": args.host, "port": args.port} if args.connector == "tcp" else None,
                "health": health_payload,
                "summary": asdict(summary),
                "observation_preview": preview,
            },
            indent=2,
        )
    )
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
