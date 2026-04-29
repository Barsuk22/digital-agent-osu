from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.skills.minecraft.actions import default_probe_steps, run_movement_probe
from src.skills.minecraft.config import MinecraftBridgeConfig, MinecraftPaths
from src.skills.minecraft.env import TcpMinecraftConnector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a scripted Minecraft body movement probe through the Mineflayer bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4711)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--move-duration-ms", type=int, default=500)
    parser.add_argument("--look-degrees", type=float, default=15.0)
    parser.add_argument("--settle-ms", type=int, default=700)
    parser.add_argument("--min-distance", type=float, default=0.25)
    parser.add_argument("--min-yaw-delta", type=float, default=0.05)
    parser.add_argument("--write-debug", action="store_true")
    return parser.parse_args()


def write_debug(result: object) -> Path:
    paths = MinecraftPaths()
    paths.ensure()
    output = paths.debug_dir / "movement_probe.json"
    output.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return output


def main() -> int:
    args = parse_args()
    bridge = MinecraftBridgeConfig(host=args.host, port=args.port, timeout_seconds=args.timeout)
    connector = TcpMinecraftConnector(bridge)

    health = connector.health_check()
    if not health.reachable:
        print(json.dumps({"ok": False, "stage": "tcp_health", "message": health.message}, indent=2))
        return 2

    result = run_movement_probe(
        connector,
        steps=default_probe_steps(
            move_duration_ms=args.move_duration_ms,
            look_degrees=args.look_degrees,
            settle_ms=args.settle_ms,
        ),
        min_horizontal_distance=args.min_distance,
        min_abs_yaw_delta=args.min_yaw_delta,
    )
    debug_path = write_debug(result) if args.write_debug else None
    payload = {
        "ok": result.ok,
        "bridge": {"host": args.host, "port": args.port},
        "health": {"reachable": health.reachable, "message": health.message},
        "result": asdict(result),
        "debug_path": str(debug_path) if debug_path else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
