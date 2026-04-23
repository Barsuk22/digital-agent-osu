from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from src.skills.osu.domain.math_utils import distance, osu_circle_radius
from src.skills.osu.domain.models import HitObjectType, ParsedBeatmap
from src.skills.osu.domain.osu_rules import slider_duration_ms
from src.skills.osu.domain.slider_path import (
    build_slider_path,
    slider_local_progress,
    slider_progress_at_time,
)
from src.skills.osu.parser.osu_parser import parse_beatmap


OBS_DIM = 59
UPCOMING_COUNT = 5
SPINNER_CENTER_X = 256.0
SPINNER_CENTER_Y = 192.0
SPINNER_TARGET_RADIUS = 76.0
SPINNER_CLEAR_MIN_SPINS = 2.0
VISIBLE_PAST_WINDOW_MS = 220.0


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def object_anchor(obj) -> tuple[float, float]:
    if obj.kind == HitObjectType.CIRCLE:
        return obj.circle.x, obj.circle.y
    if obj.kind == HitObjectType.SLIDER:
        return obj.slider.x, obj.slider.y
    return obj.spinner.x, obj.spinner.y


def object_time_ms(obj) -> float:
    if obj.kind == HitObjectType.CIRCLE:
        return float(obj.circle.time_ms)
    if obj.kind == HitObjectType.SLIDER:
        return float(obj.slider.time_ms)
    return float(obj.spinner.time_ms)


def object_end_time_ms(beatmap: ParsedBeatmap, obj) -> float:
    if obj.kind == HitObjectType.CIRCLE:
        return float(obj.circle.time_ms)
    if obj.kind == HitObjectType.SLIDER:
        return float(obj.slider.time_ms + slider_duration_ms(beatmap, obj.slider))
    return float(obj.spinner.end_time_ms)


def kind_to_id(kind: HitObjectType) -> int:
    if kind == HitObjectType.CIRCLE:
        return 0
    if kind == HitObjectType.SLIDER:
        return 1
    if kind == HitObjectType.SPINNER:
        return 2
    return -1


def is_object_active_envish(beatmap: ParsedBeatmap, obj, current_time_ms: float) -> bool:
    t = object_time_ms(obj)
    if obj.kind == HitObjectType.CIRCLE:
        return abs(t - current_time_ms) <= 80.0
    return t <= current_time_ms <= object_end_time_ms(beatmap, obj)


def get_upcoming_objects_envish(
    beatmap: ParsedBeatmap,
    current_time_ms: float,
    count: int,
) -> list:
    result = []
    for obj in beatmap.hit_objects:
        end_time = object_end_time_ms(beatmap, obj)

        if current_time_ms > end_time + VISIBLE_PAST_WINDOW_MS:
            continue

        if (
            object_time_ms(obj) >= current_time_ms - VISIBLE_PAST_WINDOW_MS
            or is_object_active_envish(beatmap, obj, current_time_ms)
        ):
            result.append(obj)

    result.sort(key=object_time_ms)
    return result[:count]


def build_slider_bridge_cache(beatmap: ParsedBeatmap) -> dict[int, dict[str, Any]]:
    cache: dict[int, dict[str, Any]] = {}
    for idx, obj in enumerate(beatmap.hit_objects):
        if obj.kind != HitObjectType.SLIDER:
            continue

        path = build_slider_path(obj.slider)
        duration_ms = slider_duration_ms(beatmap, obj.slider)

        cache[idx] = {
            "path": path,
            "start_time_ms": float(obj.slider.time_ms),
            "end_time_ms": float(obj.slider.time_ms + duration_ms),
            "repeats": int(obj.slider.repeats),
            "head_x": float(obj.slider.x),
            "head_y": float(obj.slider.y),
        }
    return cache


def build_spinner_runtime_from_dump(
    observations: list[dict[str, Any]],
    case_index: int,
    current_time_ms: float,
    cursor_x: float,
    cursor_y: float,
    synthetic_mouse_down: bool,
) -> dict[str, float]:
    start_index = case_index
    while start_index > 0:
        prev = observations[start_index - 1]
        prev_obs = prev["obs"]
        if float(prev_obs[46]) <= 0.5:
            break
        start_index -= 1

    spin_progress = 0.0
    last_angle: float | None = None
    last_angular_velocity = 0.0

    for i in range(start_index, case_index + 1):
        item = observations[i]
        t = float(item["time_ms"])
        x = float(item["cursor_x"])
        y = float(item["cursor_y"])
        down = bool(item.get("synthetic_mouse_down", False))

        dx = x - SPINNER_CENTER_X
        dy = y - SPINNER_CENTER_Y
        radius = math.hypot(dx, dy)
        angle = math.atan2(dy, dx) if radius > 1e-6 else 0.0

        valid_radius = 42.0 <= radius <= 125.0

        if last_angle is not None:
            delta = angle - last_angle
            while delta > math.pi:
                delta -= 2.0 * math.pi
            while delta < -math.pi:
                delta += 2.0 * math.pi

            delta_abs = abs(delta)

            prev_t = float(observations[i - 1]["time_ms"])
            dt_ms = max(1e-6, t - prev_t)
            last_angular_velocity = delta_abs / max(1e-6, dt_ms / 1000.0)

            too_fast = delta_abs > 0.50
            if down and valid_radius and not too_fast and delta_abs >= 0.025:
                spin_progress += min(delta_abs, 0.50)

        last_angle = angle

    return {
        "spins": spin_progress / (2.0 * math.pi),
        "angular_velocity": last_angular_velocity,
    }


def build_expected_observation_from_dump_case(
    beatmap: ParsedBeatmap,
    slider_cache: dict[int, dict[str, Any]],
    observations: list[dict[str, Any]],
    case_index: int,
) -> list[float]:
    item = observations[case_index]
    current_time_ms = float(item["time_ms"])
    cursor_x = float(item["cursor_x"])
    cursor_y = float(item["cursor_y"])
    synthetic_mouse_down = bool(item.get("synthetic_mouse_down", False))

    upcoming = get_upcoming_objects_envish(beatmap, current_time_ms, UPCOMING_COUNT)
    primary = upcoming[0] if upcoming else None
    primary_is_slider = primary is not None and primary.kind == HitObjectType.SLIDER
    primary_is_spinner = primary is not None and primary.kind == HitObjectType.SPINNER

    values: list[float] = [
        current_time_ms / 10000.0,
        cursor_x / 512.0,
        cursor_y / 384.0,
    ]

    for obj in upcoming:
        x, y = object_anchor(obj)
        dx = x - cursor_x
        dy = y - cursor_y
        dist = math.hypot(dx, dy)
        values.extend(
            [
                float(kind_to_id(obj.kind)),
                float(x) / 512.0,
                float(y) / 384.0,
                (object_time_ms(obj) - current_time_ms) / 1000.0,
                dist / 512.0,
                1.0 if is_object_active_envish(beatmap, obj, current_time_ms) else 0.0,
            ]
        )

    while (len(values) - 3) // 6 < UPCOMING_COUNT:
        values.extend([-1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    values.extend(
        build_slider_state_envish(
            beatmap=beatmap,
            slider_cache=slider_cache,
            current_time_ms=current_time_ms,
            cursor_x=cursor_x,
            cursor_y=cursor_y,
            synthetic_mouse_down=synthetic_mouse_down,
            primary_is_slider=primary_is_slider,
        )
    )

    values.extend(
        build_spinner_state_envish(
            beatmap=beatmap,
            observations=observations,
            case_index=case_index,
            current_time_ms=current_time_ms,
            cursor_x=cursor_x,
            cursor_y=cursor_y,
            primary_is_spinner=primary_is_spinner,
        )
    )

    if len(values) != OBS_DIM:
        raise ValueError(f"observation length must be {OBS_DIM}, got {len(values)}")

    return values


def build_slider_state_envish(
    beatmap: ParsedBeatmap,
    slider_cache: dict[int, dict[str, Any]],
    current_time_ms: float,
    cursor_x: float,
    cursor_y: float,
    synthetic_mouse_down: bool,
    primary_is_slider: bool,
) -> list[float]:
    follow_radius = osu_circle_radius(float(beatmap.difficulty.cs)) * 1.65

    active_idx = None
    active_obj = None
    for idx, obj in enumerate(beatmap.hit_objects):
        if obj.kind != HitObjectType.SLIDER:
            continue
        start_t = float(obj.slider.time_ms)
        end_t = object_end_time_ms(beatmap, obj)
        if start_t <= current_time_ms <= end_t:
            active_idx = idx
            active_obj = obj
            break

    if active_obj is None or active_idx is None:
        return [
            0.0,
            1.0 if primary_is_slider else 0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            follow_radius / 512.0,
        ]

    cached = slider_cache[active_idx]
    path = cached["path"]
    start_time_ms = cached["start_time_ms"]
    end_time_ms = cached["end_time_ms"]
    repeats = cached["repeats"]

    progress = slider_progress_at_time(start_time_ms, end_time_ms, current_time_ms)
    local_progress, span_index = slider_local_progress(progress, repeats)

    target_x, target_y = path.position_at_progress(local_progress)
    tangent_x, tangent_y = path.tangent_at_progress(local_progress)

    if span_index % 2 == 1:
        tangent_x = -tangent_x
        tangent_y = -tangent_y

    dist = distance(cursor_x, cursor_y, target_x, target_y)

    head_dist = distance(cursor_x, cursor_y, cached["head_x"], cached["head_y"])
    head_hit = (
        current_time_ms >= start_time_ms
        and synthetic_mouse_down
        and head_dist <= osu_circle_radius(float(beatmap.difficulty.cs))
    )

    inside_follow = synthetic_mouse_down and dist <= follow_radius

    return [
        1.0,
        1.0 if primary_is_slider else 0.0,
        float(progress),
        float(target_x) / 512.0,
        float(target_y) / 384.0,
        float(dist) / 512.0,
        float(dist) / 512.0,
        1.0 if inside_follow else 0.0,
        1.0 if head_hit else 0.0,
        max(0.0, end_time_ms - current_time_ms) / 1000.0,
        float(tangent_x),
        float(tangent_y),
        follow_radius / 512.0,
    ]


def build_spinner_state_envish(
    beatmap: ParsedBeatmap,
    observations: list[dict[str, Any]],
    case_index: int,
    current_time_ms: float,
    cursor_x: float,
    cursor_y: float,
    primary_is_spinner: bool,
) -> list[float]:
    active_obj = None
    for obj in beatmap.hit_objects:
        if obj.kind != HitObjectType.SPINNER:
            continue
        start_t = float(obj.spinner.time_ms)
        end_t = float(obj.spinner.end_time_ms)
        if start_t <= current_time_ms <= end_t:
            active_obj = obj
            break

    dx = cursor_x - SPINNER_CENTER_X
    dy = cursor_y - SPINNER_CENTER_Y
    dist = math.hypot(dx, dy)
    angle = math.atan2(dy, dx) if dist > 1e-6 else 0.0
    radius_error = abs(dist - SPINNER_TARGET_RADIUS)

    if active_obj is None:
        return [
            0.0,
            1.0 if primary_is_spinner else 0.0,
            0.0,
            0.0,
            SPINNER_CLEAR_MIN_SPINS / 8.0,
            0.0,
            SPINNER_CENTER_X / 512.0,
            SPINNER_CENTER_Y / 384.0,
            dist / 256.0,
            radius_error / 256.0,
            math.sin(angle),
            math.cos(angle),
            0.0,
        ]

    start_t = float(active_obj.spinner.time_ms)
    end_t = float(active_obj.spinner.end_time_ms)
    duration = max(1.0, end_t - start_t)
    progress = max(0.0, min(1.0, (current_time_ms - start_t) / duration))

    runtime = build_spinner_runtime_from_dump(
        observations=observations,
        case_index=case_index,
        current_time_ms=current_time_ms,
        cursor_x=cursor_x,
        cursor_y=cursor_y,
        synthetic_mouse_down=bool(observations[case_index].get("synthetic_mouse_down", False)),
    )

    return [
        1.0,
        1.0 if primary_is_spinner else 0.0,
        progress,
        float(runtime["spins"]),
        SPINNER_CLEAR_MIN_SPINS / 8.0,
        max(0.0, end_t - current_time_ms) / 1000.0,
        SPINNER_CENTER_X / 512.0,
        SPINNER_CENTER_Y / 384.0,
        dist / 256.0,
        radius_error / 256.0,
        math.sin(angle),
        math.cos(angle),
        float(runtime["angular_velocity"]),
    ]


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare C# observation dump against env/judge-aware expectation.")
    parser.add_argument("--beatmap", required=True, help="Path to .osu file")
    parser.add_argument("--dump", required=True, help="Path to C# observation dump JSON")
    parser.add_argument("--tolerance", type=float, default=1e-5, help="Max allowed absolute difference")
    parser.add_argument("--top", type=int, default=20, help="How many worst diffs to print")
    args = parser.parse_args()

    beatmap = parse_beatmap(args.beatmap)
    dump = load_json(args.dump)
    observations = dump.get("observations", [])

    if not observations:
        raise SystemExit("dump contains no observations")

    slider_cache = build_slider_bridge_cache(beatmap)

    worst_diff = 0.0
    worst_case: tuple[int, int, float, float, float] | None = None
    all_diffs: list[tuple[float, int, int, float, float]] = []

    for case_index, item in enumerate(observations):
        expected = build_expected_observation_from_dump_case(
            beatmap=beatmap,
            slider_cache=slider_cache,
            observations=observations,
            case_index=case_index,
        )
        actual = [float(v) for v in item["obs"]]

        if len(actual) != OBS_DIM:
            raise SystemExit(f"case {case_index}: actual observation length is {len(actual)}, expected {OBS_DIM}")

        for obs_index, (a, e) in enumerate(zip(actual, expected)):
            diff = abs(a - e)
            all_diffs.append((diff, case_index, obs_index, a, e))
            if diff > worst_diff:
                worst_diff = diff
                worst_case = (case_index, obs_index, a, e, diff)

    print(f"[env-parity] observations={len(observations)} max_abs_diff={worst_diff:.8f}")

    if worst_case is not None:
        case_index, obs_index, actual, expected, diff = worst_case
        print(
            "[env-parity] worst "
            f"case={case_index} "
            f"obs_index={obs_index} "
            f"name={obs_index_name(obs_index)} "
            f"actual={actual:.8f} "
            f"expected={expected:.8f} "
            f"diff={diff:.8f}"
        )

    print("[env-parity] top mismatches:")
    for diff, case_index, obs_index, actual, expected in sorted(all_diffs, reverse=True)[: args.top]:
        if diff <= 0.0:
            break
        print(
            f"  case={case_index:03d} "
            f"idx={obs_index:02d} "
            f"name={obs_index_name(obs_index)} "
            f"actual={actual:.8f} "
            f"expected={expected:.8f} "
            f"diff={diff:.8f}"
        )

    if worst_diff > args.tolerance:
        raise SystemExit(
            f"[env-parity] FAILED: max diff {worst_diff:.8f} > tolerance {args.tolerance:.8f}"
        )

    print("[env-parity] OK")


if __name__ == "__main__":
    main()