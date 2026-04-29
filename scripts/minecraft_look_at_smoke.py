from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.skills.minecraft.config import MinecraftBridgeConfig, MinecraftPaths
from src.skills.minecraft.env import TcpMinecraftConnector
from src.skills.minecraft.skills import look_at_target, pick_target_from_observation, target_from_coords


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the heuristic Minecraft LookAtTarget skeleton.")
    parser.add_argument("--target", choices=["nearest_player", "nearest_block", "nearest_entity", "coords"], default="nearest_player")
    parser.add_argument("--coords", nargs=3, type=float, metavar=("X", "Y", "Z"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4711)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--max-steps", type=int, default=4)
    parser.add_argument("--tolerance-degrees", type=float, default=3.0)
    parser.add_argument("--max-step-degrees", type=float, default=30.0)
    parser.add_argument("--settle-ms", type=int, default=120)
    parser.add_argument("--write-debug", action="store_true")
    return parser.parse_args()


def write_debug(payload: dict) -> Path:
    paths = MinecraftPaths()
    paths.ensure()
    output = paths.debug_dir / "look_at_target.json"
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

    raw = connector.observe()
    if args.target == "coords":
        if args.coords is None:
            print(json.dumps({"ok": False, "stage": "args", "message": "--coords X Y Z is required for --target coords"}, indent=2))
            return 2
        target = target_from_coords(args.coords[0], args.coords[1], args.coords[2])
    else:
        target = pick_target_from_observation(raw, mode=args.target)

    result = look_at_target(
        connector,
        target,
        max_steps=args.max_steps,
        tolerance_degrees=args.tolerance_degrees,
        max_step_degrees=args.max_step_degrees,
        settle_ms=args.settle_ms,
    )
    payload = {
        "ok": result.ok,
        "bridge": {"host": args.host, "port": args.port},
        "health": {"reachable": health.reachable, "message": health.message},
        "target_mode": args.target,
        "result": asdict(result),
        "debug_path": None,
    }
    if args.write_debug:
        payload["debug_path"] = str(write_debug(payload))
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
