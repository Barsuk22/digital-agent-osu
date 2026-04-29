from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.skills.minecraft.actions import look_delta, move_impulse, observe, step_forward_and_measure, stop_all, turn_and_step
from src.skills.minecraft.config import MinecraftBridgeConfig, MinecraftPaths
from src.skills.minecraft.env import TcpMinecraftConnector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test reusable Minecraft body primitives.")
    parser.add_argument("--primitive", choices=["observe", "stop", "look", "move", "step_forward", "turn_and_step"], default="turn_and_step")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4711)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--command", default="move_forward")
    parser.add_argument("--duration-ms", type=int, default=500)
    parser.add_argument("--settle-ms", type=int, default=700)
    parser.add_argument("--yaw-degrees", type=float, default=15.0)
    parser.add_argument("--pitch-degrees", type=float, default=0.0)
    parser.add_argument("--write-debug", action="store_true")
    return parser.parse_args()


def write_debug(name: str, payload: dict) -> Path:
    paths = MinecraftPaths()
    paths.ensure()
    output = paths.debug_dir / f"body_primitive_{name}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return output


def main() -> int:
    args = parse_args()
    bridge = MinecraftBridgeConfig(host=args.host, port=args.port, timeout_seconds=args.timeout)
    connector = TcpMinecraftConnector(bridge)
    health = connector.health_check()
    if not health.reachable:
        print(json.dumps({"ok": False, "stage": "tcp_health", "message": health.message}, indent=2))
        return 2

    if args.primitive == "observe":
        result: object = observe(connector)
    elif args.primitive == "stop":
        result = stop_all(connector, settle_ms=120)
    elif args.primitive == "look":
        result = look_delta(connector, yaw_degrees=args.yaw_degrees, pitch_degrees=args.pitch_degrees, settle_ms=args.settle_ms)
    elif args.primitive == "move":
        result = move_impulse(connector, command=args.command, duration_ms=args.duration_ms, settle_ms=args.settle_ms)
    elif args.primitive == "step_forward":
        result = step_forward_and_measure(connector, duration_ms=args.duration_ms, settle_ms=args.settle_ms)
    else:
        result = turn_and_step(
            connector,
            yaw_degrees=args.yaw_degrees,
            move_duration_ms=args.duration_ms,
            move_settle_ms=args.settle_ms,
        )

    result_payload = asdict(result) if hasattr(result, "__dataclass_fields__") else result
    if isinstance(result, list):
        result_payload = [asdict(item) for item in result]

    payload = {
        "ok": True,
        "primitive": args.primitive,
        "bridge": {"host": args.host, "port": args.port},
        "health": {"reachable": health.reachable, "message": health.message},
        "result": result_payload,
        "debug_path": None,
    }
    if args.write_debug:
        payload["debug_path"] = str(write_debug(args.primitive, payload))
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
