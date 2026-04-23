from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.skills.osu.env.osu_env import OsuEnv
from src.skills.osu.parser.osu_parser import parse_beatmap
from src.skills.osu.policy.runtime import obs_to_numpy


OBS_DIM = 59


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def obs_index_name(idx: int) -> str:
    names = {
        0: "time_norm",
        1: "cursor_x_norm",
        2: "cursor_y_norm",
        33: "slider_active",
        34: "primary_is_slider",
        35: "slider_progress",
        36: "slider_target_x",
        37: "slider_target_y",
        38: "slider_distance_to_target",
        39: "slider_distance_to_ball",
        40: "slider_inside_follow",
        41: "slider_head_hit",
        42: "slider_time_to_end",
        43: "slider_tangent_x",
        44: "slider_tangent_y",
        45: "slider_follow_radius",
        46: "spinner_active",
        47: "primary_is_spinner",
        48: "spinner_progress",
        49: "spinner_spins",
        50: "spinner_target_spins",
        51: "spinner_time_to_end",
        52: "spinner_center_x",
        53: "spinner_center_y",
        54: "spinner_distance_to_center",
        55: "spinner_radius_error",
        56: "spinner_angle_sin",
        57: "spinner_angle_cos",
        58: "spinner_angular_velocity",
    }
    if idx in names:
        return names[idx]

    if 3 <= idx < 33:
        rel = idx - 3
        obj_slot = rel // 6
        field = rel % 6
        field_names = [
            "kind_id",
            "x",
            "y",
            "time_to_hit",
            "distance_to_cursor",
            "is_active",
        ]
        return f"upcoming[{obj_slot}].{field_names[field]}"

    return f"obs[{idx}]"


def load_trace_cases(trace_path: str | Path) -> list[dict]:
    trace = load_json(trace_path)
    cases: list[dict] = []
    for tick in trace:
        obs = tick.get("Observation")
        if tick.get("PrimaryObject") == "warmup":
            continue
        if not isinstance(obs, list) or len(obs) != OBS_DIM:
            continue

        cases.append(
            {
                "time_ms": float(tick["MapTimeMs"]),
                "cursor_x": float(tick["CursorX"]),
                "cursor_y": float(tick["CursorY"]),
                "applied_cursor_x": float(tick.get("AppliedCursorX", tick["CursorX"])),
                "applied_cursor_y": float(tick.get("AppliedCursorY", tick["CursorY"])),
                "tracked_cursor_valid": bool(tick.get("TrackedCursorValid", False)),
                "tracked_cursor_x": float(tick.get("TrackedCursorX", tick.get("AppliedCursorX", tick["CursorX"]))),
                "tracked_cursor_y": float(tick.get("TrackedCursorY", tick.get("AppliedCursorY", tick["CursorY"]))),
                "raw_click_down": bool(tick.get("RawClickDown", False)),
                "click_down": bool(tick.get("ClickDown", False)),
                "obs": [float(v) for v in obs],
                "primary_object": tick.get("PrimaryObject", "none"),
            }
        )
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare live trace observations against true env rollout semantics.")
    parser.add_argument("--beatmap", required=True, help="Path to .osu file")
    parser.add_argument("--trace", required=True, help="Path to warmup_trace_*.json")
    parser.add_argument("--top", type=int, default=30, help="How many worst diffs to print")
    parser.add_argument("--tolerance", type=float, default=1e-5, help="Max allowed absolute difference")
    args = parser.parse_args()

    beatmap = parse_beatmap(args.beatmap)
    cases = load_trace_cases(args.trace)
    if not cases:
        raise SystemExit("trace contains no comparable observation cases")

    env = OsuEnv(
        beatmap=beatmap,
        dt_ms=16.6667,
        upcoming_count=5,
        cursor_start_x=256.0,
        cursor_start_y=192.0,
        click_threshold=0.75,
        slider_hold_threshold=0.45,
        spinner_hold_threshold=0.45,
        cursor_speed_scale=14.0,
    )
    env.reset()

    all_diffs: list[tuple[float, int, int, float, float]] = []
    worst = (0.0, -1, -1, 0.0, 0.0)
    prev_raw_click = False
    previous_time_ms: float | None = None

    for case_index, case in enumerate(cases):
        env.time_ms = float(case["time_ms"])
        env.cursor_x = float(case["cursor_x"])
        env.cursor_y = float(case["cursor_y"])

        expected_obs = env._build_observation()
        expected = [float(v) for v in obs_to_numpy(expected_obs)]
        actual = [float(v) for v in case["obs"]]

        if len(actual) != OBS_DIM:
            raise SystemExit(f"case {case_index}: actual observation length is {len(actual)}, expected {OBS_DIM}")

        for obs_index, (a, e) in enumerate(zip(actual, expected)):
            diff = abs(a - e)
            all_diffs.append((diff, case_index, obs_index, a, e))
            if diff > worst[0]:
                worst = (diff, case_index, obs_index, a, e)

        dt_ms = 16.6667 if previous_time_ms is None else max(1.0, float(case["time_ms"]) - previous_time_ms)
        just_pressed = bool(case["raw_click_down"]) and not prev_raw_click
        judge_cursor_x = float(case["tracked_cursor_x"] if case["tracked_cursor_valid"] else case["applied_cursor_x"])
        judge_cursor_y = float(case["tracked_cursor_y"] if case["tracked_cursor_valid"] else case["applied_cursor_y"])

        env.judge.update(
            time_ms=float(case["time_ms"]),
            cursor_x=judge_cursor_x,
            cursor_y=judge_cursor_y,
            just_pressed=just_pressed,
            click_down=bool(case["click_down"]),
            dt_ms=dt_ms,
        )

        prev_raw_click = bool(case["raw_click_down"])
        previous_time_ms = float(case["time_ms"])

    worst_diff, case_index, obs_index, actual, expected = worst
    print(f"[trace-parity] observations={len(cases)} max_abs_diff={worst_diff:.8f}")
    if case_index >= 0:
        print(
            "[trace-parity] worst "
            f"case={case_index} idx={obs_index} name={obs_index_name(obs_index)} "
            f"actual={actual:.8f} expected={expected:.8f} diff={worst_diff:.8f}"
        )

    print("[trace-parity] top mismatches:")
    for diff, case_index, obs_index, actual, expected in sorted(all_diffs, reverse=True)[: args.top]:
        if diff <= 0.0:
            break
        print(
            f"  case={case_index:03d} idx={obs_index:02d} name={obs_index_name(obs_index)} "
            f"actual={actual:.8f} expected={expected:.8f} diff={diff:.8f}"
        )

    if worst_diff > args.tolerance:
        raise SystemExit(f"[trace-parity] FAILED: max diff {worst_diff:.8f} > tolerance {args.tolerance:.8f}")

    print("[trace-parity] OK")


if __name__ == "__main__":
    main()
