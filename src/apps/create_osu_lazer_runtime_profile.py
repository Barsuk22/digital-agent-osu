from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.config.paths import PATHS
from src.skills.osu.runtime import resolve_map_alias


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a bridge runtime config for a selected osu! map.")
    parser.add_argument("--map", dest="map_value", required=True, help="Map alias or absolute .osu path.")
    parser.add_argument(
        "--mode",
        choices=["diagnostic", "live_probe", "live_click_probe", "live_move", "live_play"],
        default="diagnostic",
    )
    parser.add_argument("--policy-runtime", choices=["zeromq", "onnx"], default="zeromq")
    parser.add_argument("--out", dest="output_path", default=None)
    parser.add_argument("--diagnostic-time", dest="diagnostic_time_ms", type=float, default=None)
    parser.add_argument("--audio-offset", dest="audio_offset_ms", type=float, default=None)
    parser.add_argument("--input-delay", dest="input_delay_ms", type=float, default=None)
    parser.add_argument("--cursor-speed", dest="cursor_speed_scale", type=float, default=None)
    return parser.parse_args()


def base_config() -> dict:
    return {
        "policyBridge": {
            "mode": "zeromq",
            "address": "tcp://127.0.0.1:5555",
            "modelPath": str(PATHS.artifacts_dir / "exports" / "onnx" / "best_easy_generalization.onnx"),
            "observationSize": 59,
            "timeoutMs": 1000,
        },
        "timing": {
            "tickRateHz": 60.0,
            "startupDelayMs": 1200.0,
            "diagnosticTicks": 30,
            "diagnosticInitialMapTimeMs": 1800.0,
            "startTriggerMode": "delay",
            "startHotkey": "F8",
            "audioOffsetMs": 0.0,
            "inputDelayMs": 0.0,
            "captureDelayMs": 0.0,
        },
        "window": {
            "titleHint": "osu!",
            "processName": "osu!",
            "requireForeground": True,
            "executablePath": r"C:\Users\valer\AppData\Local\osulazer\current\osu!.exe",
        },
        "beatmap": {
            "sourceOsuPath": "",
            "exportJsonPath": str(PATHS.project_root / "exports" / "osu_lazer_bridge_map.json"),
        },
        "control": {
            "enableMouseMovement": False,
            "enableMouseClicks": False,
            "recenterCursorOnStart": False,
            "useLiveCursorTracking": False,
            "playfieldPadX": 80.0,
            "playfieldPadY": 60.0,
            "cursorSpeedScale": 12.0,
            "aimAssistStrength": 0.0,
            "aimAssistMaxDistance": 160.0,
            "aimAssistDeadzone": 18.0,
            "clickThreshold": 0.75,
            "sliderHoldThreshold": 0.45,
            "spinnerHoldThreshold": 0.45,
        },
        "logging": {
            "enabled": True,
            "directory": "logs",
            "saveJsonTrace": True,
        },
    }


def apply_mode(config: dict, mode: str) -> None:
    timing = config["timing"]
    control = config["control"]

    if mode == "diagnostic":
        control["enableMouseMovement"] = False
        control["enableMouseClicks"] = False
        timing["diagnosticTicks"] = 12
        return

    if mode == "live_probe":
        control["enableMouseMovement"] = True
        control["enableMouseClicks"] = False
        control["recenterCursorOnStart"] = True
        control["aimAssistStrength"] = 0.2
        timing["diagnosticTicks"] = 30
        return

    if mode == "live_click_probe":
        control["enableMouseMovement"] = True
        control["enableMouseClicks"] = True
        control["recenterCursorOnStart"] = True
        control["aimAssistStrength"] = 0.25
        timing["diagnosticTicks"] = 14
        return

    if mode == "live_move":
        control["enableMouseMovement"] = True
        control["enableMouseClicks"] = False
        control["recenterCursorOnStart"] = True
        control["aimAssistStrength"] = 0.3
        timing["startTriggerMode"] = "hotkey"
        timing["startupDelayMs"] = 0.0
        timing["diagnosticTicks"] = 180
        timing["diagnosticInitialMapTimeMs"] = 0.0
        return

    if mode == "live_play":
        control["enableMouseMovement"] = True
        control["enableMouseClicks"] = True
        control["recenterCursorOnStart"] = True
        control["aimAssistStrength"] = 0.35
        timing["startTriggerMode"] = "hotkey"
        timing["startupDelayMs"] = 0.0
        timing["diagnosticTicks"] = 180
        timing["diagnosticInitialMapTimeMs"] = 0.0


def default_output_path(map_path: Path, mode: str, policy_runtime: str) -> Path:
    safe_name = map_path.stem.replace(" ", "_").replace("(", "").replace(")", "").replace("[", "").replace("]", "")
    return (
        PATHS.project_root
        / "external"
        / "osu_lazer_controller"
        / "configs"
        / "profiles"
        / f"{safe_name}.{policy_runtime}.{mode}.json"
    )


def main() -> None:
    args = parse_args()
    map_path = resolve_map_alias(args.map_value).resolve()
    config = base_config()
    config["policyBridge"]["mode"] = args.policy_runtime
    config["beatmap"]["sourceOsuPath"] = str(map_path)
    apply_mode(config, args.mode)

    if args.diagnostic_time_ms is not None:
        config["timing"]["diagnosticInitialMapTimeMs"] = args.diagnostic_time_ms
    if args.audio_offset_ms is not None:
        config["timing"]["audioOffsetMs"] = args.audio_offset_ms
    if args.input_delay_ms is not None:
        config["timing"]["inputDelayMs"] = args.input_delay_ms
    if args.cursor_speed_scale is not None:
        config["control"]["cursorSpeedScale"] = args.cursor_speed_scale

    output_path = Path(args.output_path) if args.output_path else default_output_path(map_path, args.mode, args.policy_runtime)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "event": "runtime_profile_created",
                "output": str(output_path),
                "map": str(map_path),
                "mode": args.mode,
                "policyRuntime": config["policyBridge"]["mode"],
                "diagnosticInitialMapTimeMs": config["timing"]["diagnosticInitialMapTimeMs"],
                "audioOffsetMs": config["timing"]["audioOffsetMs"],
                "inputDelayMs": config["timing"]["inputDelayMs"],
                "cursorSpeedScale": config["control"]["cursorSpeedScale"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
