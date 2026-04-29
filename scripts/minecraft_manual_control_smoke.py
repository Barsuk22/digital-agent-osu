from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.skills.minecraft.actions import build_manual_action, manual_action_specs
from src.skills.minecraft.config import MinecraftBridgeConfig, MinecraftPaths
from src.skills.minecraft.env import ObservationBuilder, TcpMinecraftConnector


def parse_args() -> argparse.Namespace:
    available = sorted(manual_action_specs())
    parser = argparse.ArgumentParser(description="Send one safe manual action to the Minecraft Mineflayer bridge.")
    parser.add_argument("--action", choices=available, default="noop")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4711)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--duration-ms", type=int, default=120)
    parser.add_argument("--look-degrees", type=float, default=12.0)
    parser.add_argument("--chat-message", default=None)
    parser.add_argument("--settle-ms", type=int, default=180)
    parser.add_argument("--write-debug", action="store_true")
    return parser.parse_args()


def preview(raw: dict) -> dict:
    return {
        "connection_state": raw.get("connection_state"),
        "username": raw.get("username"),
        "position": raw.get("position"),
        "position_valid": raw.get("position_valid"),
        "velocity": raw.get("velocity"),
        "yaw": raw.get("yaw"),
        "pitch": raw.get("pitch"),
        "on_ground": raw.get("on_ground"),
        "physics_enabled": raw.get("physics_enabled"),
        "control_state": raw.get("control_state"),
        "hp": raw.get("hp"),
        "hunger": raw.get("hunger", raw.get("food")),
        "selected_slot": raw.get("selected_slot"),
        "item_in_hand": raw.get("item_in_hand"),
        "nearby_entities": len(raw.get("nearby_entities", [])),
        "nearby_players": len(raw.get("nearby_players", [])),
        "nearby_blocks": len(raw.get("nearby_blocks", [])),
        "events": raw.get("events", []),
    }


def finite_position(raw: dict) -> tuple[float, float, float] | None:
    position = raw.get("position")
    if not isinstance(position, list | tuple) or len(position) != 3:
        return None
    if not all(isinstance(value, int | float) for value in position):
        return None
    return float(position[0]), float(position[1]), float(position[2])


def delta_summary(before: dict, after: dict) -> dict:
    before_pos = finite_position(before)
    after_pos = finite_position(after)
    before_yaw = before.get("yaw")
    after_yaw = after.get("yaw")
    before_pitch = before.get("pitch")
    after_pitch = after.get("pitch")
    position_delta = None
    if before_pos is not None and after_pos is not None:
        position_delta = [after_pos[index] - before_pos[index] for index in range(3)]

    return {
        "position_delta": position_delta,
        "yaw_delta": after_yaw - before_yaw if isinstance(before_yaw, int | float) and isinstance(after_yaw, int | float) else None,
        "pitch_delta": after_pitch - before_pitch if isinstance(before_pitch, int | float) and isinstance(after_pitch, int | float) else None,
    }


def write_debug(action_name: str, before: dict, action: object, after: dict) -> Path:
    paths = MinecraftPaths()
    paths.ensure()
    output = paths.debug_dir / f"manual_control_{action_name}.json"
    builder = ObservationBuilder()
    before_obs = builder.build(before)
    after_obs = builder.build(after)
    payload = {
        "action": action_name,
        "sent_action": asdict(action),
        "before": asdict(before_obs),
        "after": asdict(after_obs),
        "before_raw": before,
        "after_raw": after,
    }
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

    before = connector.observe()
    action = build_manual_action(
        args.action,
        duration_ms=args.duration_ms,
        look_degrees=args.look_degrees,
        chat_message=args.chat_message,
    )
    action_response = connector.send_action(action)

    if args.settle_ms > 0:
        time.sleep(args.settle_ms / 1000.0)
    after = connector.observe()

    debug_path = None
    if args.write_debug:
        debug_path = write_debug(args.action, before, action, after)

    print(
        json.dumps(
            {
                "ok": True,
                "bridge": {"host": args.host, "port": args.port},
                "health": {"reachable": health.reachable, "message": health.message},
                "action": args.action,
                "sent_action": asdict(action),
                "action_response": preview(action_response),
                "before": preview(before),
                "after": preview(after),
                "delta": delta_summary(before, after),
                "debug_path": str(debug_path) if debug_path else None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
