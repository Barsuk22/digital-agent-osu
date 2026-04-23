from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


OBS_DIM = 59
UPCOMING_COUNT = 5
SPINNER_CENTER_X = 256.0
SPINNER_CENTER_Y = 192.0
SPINNER_TARGET_RADIUS = 76.0
SPINNER_CLEAR_MIN_SPINS = 2.0


def kind_to_id(kind: str) -> int:
    kind_normalized = kind.lower()
    if kind_normalized == "circle":
        return 0
    if kind_normalized == "slider":
        return 1
    if kind_normalized == "spinner":
        return 2
    return -1


def object_end_time(obj: dict[str, Any]) -> float:
    time_ms = float(obj.get("time_ms", 0.0))
    end_time_ms = float(obj.get("end_time_ms", time_ms))
    if end_time_ms > time_ms:
        return end_time_ms

    slider = obj.get("slider")
    if isinstance(slider, dict):
        duration_ms = float(slider.get("duration_ms", 0.0))
        if duration_ms > 0.0:
            return time_ms + duration_ms

    spinner = obj.get("spinner")
    if isinstance(spinner, dict):
        spinner_end = float(spinner.get("end_time_ms", time_ms))
        if spinner_end > time_ms:
            return spinner_end

    return time_ms


def is_object_active(obj: dict[str, Any], current_time_ms: float) -> bool:
    time_ms = float(obj["time_ms"])
    kind = obj["kind"].lower()
    if kind == "circle":
        return abs(time_ms - current_time_ms) <= 80.0
    return time_ms <= current_time_ms <= object_end_time(obj)


def get_upcoming_objects(objects: list[dict[str, Any]], current_time_ms: float) -> list[dict[str, Any]]:
    visible_past_window_ms = 220.0
    result = [
        obj
        for obj in objects
        if current_time_ms <= object_end_time(obj) + visible_past_window_ms
        and (
            float(obj["time_ms"]) >= current_time_ms - visible_past_window_ms
            or is_object_active(obj, current_time_ms)
        )
    ]
    result.sort(key=lambda obj: float(obj["time_ms"]))
    return result[:UPCOMING_COUNT]


def osu_circle_radius(cs: float) -> float:
    return 54.4 - 4.48 * cs


def slider_progress_at_time(start_time_ms: float, end_time_ms: float, current_time_ms: float) -> float:
    if end_time_ms <= start_time_ms:
        return 1.0
    return max(0.0, min(1.0, (current_time_ms - start_time_ms) / (end_time_ms - start_time_ms)))


def slider_local_progress(progress: float, repeats: int) -> tuple[float, int]:
    repeats = max(1, repeats)
    span_progress = max(0.0, min(1.0, progress)) * repeats
    span_index = min(repeats - 1, int(span_progress))
    local_progress = span_progress - span_index
    if span_index % 2 == 1:
        local_progress = 1.0 - local_progress
    return local_progress, span_index


def cumulative_lengths(points: list[dict[str, float]]) -> list[float]:
    result = [0.0 for _ in points]
    total = 0.0
    for idx in range(1, len(points)):
        dx = float(points[idx]["x"]) - float(points[idx - 1]["x"])
        dy = float(points[idx]["y"]) - float(points[idx - 1]["y"])
        total += math.hypot(dx, dy)
        result[idx] = total
    return result


def position_at_distance(
    points: list[dict[str, float]],
    cumulative: list[float],
    distance_value: float,
) -> tuple[float, float]:
    total = cumulative[-1]
    d = max(0.0, min(total, distance_value))

    for idx in range(1, len(cumulative)):
        prev_len = cumulative[idx - 1]
        curr_len = cumulative[idx]
        if d > curr_len:
            continue

        seg_len = curr_len - prev_len
        if seg_len <= 1e-9:
            return float(points[idx]["x"]), float(points[idx]["y"])

        t = (d - prev_len) / seg_len
        ax = float(points[idx - 1]["x"])
        ay = float(points[idx - 1]["y"])
        bx = float(points[idx]["x"])
        by = float(points[idx]["y"])
        return ax + (bx - ax) * t, ay + (by - ay) * t

    return float(points[-1]["x"]), float(points[-1]["y"])


def position_at_progress(points: list[dict[str, float]], progress: float) -> tuple[float, float]:
    if not points:
        return 0.0, 0.0
    if len(points) == 1:
        return float(points[0]["x"]), float(points[0]["y"])

    cumulative = cumulative_lengths(points)
    total = cumulative[-1]
    if total <= 1e-6:
        return float(points[0]["x"]), float(points[0]["y"])

    return position_at_distance(points, cumulative, max(0.0, min(1.0, progress)) * total)


def tangent_at_progress(points: list[dict[str, float]], progress: float) -> tuple[float, float]:
    if len(points) < 2:
        return 0.0, 0.0

    cumulative = cumulative_lengths(points)
    total = cumulative[-1]
    if total <= 1e-6:
        return 0.0, 0.0

    center_d = max(0.0, min(1.0, progress)) * total
    ax, ay = position_at_distance(points, cumulative, max(0.0, center_d - 8.0))
    bx, by = position_at_distance(points, cumulative, min(total, center_d + 8.0))
    dx = bx - ax
    dy = by - ay
    norm = math.hypot(dx, dy)
    if norm <= 1e-6:
        return 0.0, 0.0
    return dx / norm, dy / norm


def build_spinner_runtime_from_dump(
    observations: list[dict[str, Any]],
    case_index: int,
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


def build_observation(
    bridge: dict[str, Any],
    observations: list[dict[str, Any]],
    case_index: int,
) -> list[float]:
    item = observations[case_index]
    current_time_ms = float(item["time_ms"])
    cursor_x = float(item["cursor_x"])
    cursor_y = float(item["cursor_y"])
    synthetic_mouse_down = bool(item.get("synthetic_mouse_down", False))

    objects = bridge["objects"]
    upcoming = get_upcoming_objects(objects, current_time_ms)
    primary = upcoming[0] if upcoming else None
    primary_is_slider = primary is not None and primary["kind"].lower() == "slider"
    primary_is_spinner = primary is not None and primary["kind"].lower() == "spinner"

    values: list[float] = [
        current_time_ms / 10000.0,
        cursor_x / 512.0,
        cursor_y / 384.0,
    ]

    for item_obj in upcoming:
        dx = float(item_obj["x"]) - cursor_x
        dy = float(item_obj["y"]) - cursor_y
        dist = math.hypot(dx, dy)
        values.extend(
            [
                float(kind_to_id(item_obj["kind"])),
                float(item_obj["x"]) / 512.0,
                float(item_obj["y"]) / 384.0,
                (float(item_obj["time_ms"]) - current_time_ms) / 1000.0,
                dist / 512.0,
                1.0 if is_object_active(item_obj, current_time_ms) else 0.0,
            ]
        )

    while (len(values) - 3) // 6 < UPCOMING_COUNT:
        values.extend([-1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    values.extend(
        build_slider_state(
            bridge,
            current_time_ms,
            cursor_x,
            cursor_y,
            synthetic_mouse_down,
            primary_is_slider,
        )
    )
    values.extend(
        build_spinner_state(
            bridge,
            observations,
            case_index,
            current_time_ms,
            cursor_x,
            cursor_y,
            primary_is_spinner,
        )
    )

    if len(values) != OBS_DIM:
        raise ValueError(f"observation length must be {OBS_DIM}, got {len(values)}")

    return values


def build_slider_state(
    bridge: dict[str, Any],
    current_time_ms: float,
    cursor_x: float,
    cursor_y: float,
    synthetic_mouse_down: bool,
    primary_is_slider: bool,
) -> list[float]:
    follow_radius = osu_circle_radius(float(bridge["beatmap"]["cs"])) * 1.65
    head_radius = osu_circle_radius(float(bridge["beatmap"]["cs"]))

    active = next(
        (
            obj
            for obj in bridge["objects"]
            if obj["kind"].lower() == "slider"
            and isinstance(obj.get("slider"), dict)
            and float(obj["time_ms"]) <= current_time_ms <= object_end_time(obj)
        ),
        None,
    )

    if active is None:
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

    slider = active["slider"]
    end_time = object_end_time(active)
    progress = slider_progress_at_time(float(active["time_ms"]), end_time, current_time_ms)
    local_progress, span_index = slider_local_progress(progress, int(slider["repeats"]))
    target_x, target_y = position_at_progress(slider["sampled_points"], local_progress)
    tangent_x, tangent_y = tangent_at_progress(slider["sampled_points"], local_progress)

    if span_index % 2 == 1:
        tangent_x = -tangent_x
        tangent_y = -tangent_y

    dist = math.hypot(target_x - cursor_x, target_y - cursor_y)
    head_dist = math.hypot(float(active["x"]) - cursor_x, float(active["y"]) - cursor_y)

    head_hit = (
        current_time_ms >= float(active["time_ms"])
        and synthetic_mouse_down
        and head_dist <= head_radius
    )
    inside_follow = synthetic_mouse_down and dist <= follow_radius

    return [
        1.0,
        1.0 if primary_is_slider else 0.0,
        progress,
        target_x / 512.0,
        target_y / 384.0,
        dist / 512.0,
        dist / 512.0,
        1.0 if inside_follow else 0.0,
        1.0 if head_hit else 0.0,
        max(0.0, end_time - current_time_ms) / 1000.0,
        tangent_x,
        tangent_y,
        follow_radius / 512.0,
    ]


def build_spinner_state(
    bridge: dict[str, Any],
    observations: list[dict[str, Any]],
    case_index: int,
    current_time_ms: float,
    cursor_x: float,
    cursor_y: float,
    primary_is_spinner: bool,
) -> list[float]:
    active = next(
        (
            obj
            for obj in bridge["objects"]
            if obj["kind"].lower() == "spinner"
            and isinstance(obj.get("spinner"), dict)
            and float(obj["time_ms"]) <= current_time_ms <= object_end_time(obj)
        ),
        None,
    )

    dx = cursor_x - SPINNER_CENTER_X
    dy = cursor_y - SPINNER_CENTER_Y
    dist = math.hypot(dx, dy)
    angle = math.atan2(dy, dx) if dist > 1e-6 else 0.0
    radius_error = abs(dist - SPINNER_TARGET_RADIUS)

    if active is None:
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

    end_time = object_end_time(active)
    duration = max(1.0, end_time - float(active["time_ms"]))
    progress = max(0.0, min(1.0, (current_time_ms - float(active["time_ms"])) / duration))
    runtime = build_spinner_runtime_from_dump(observations, case_index)

    return [
        1.0,
        1.0 if primary_is_spinner else 0.0,
        progress,
        float(runtime["spins"]),
        SPINNER_CLEAR_MIN_SPINS / 8.0,
        max(0.0, end_time - current_time_ms) / 1000.0,
        SPINNER_CENTER_X / 512.0,
        SPINNER_CENTER_Y / 384.0,
        dist / 256.0,
        radius_error / 256.0,
        math.sin(angle),
        math.cos(angle),
        float(runtime["angular_velocity"]),
    ]


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare C# osu!lazer bridge observation dump.")
    parser.add_argument("--bridge", required=True, help="Path to bridge_map.json")
    parser.add_argument("--dump", required=True, help="Path to C# observation dump JSON")
    parser.add_argument("--tolerance", type=float, default=1e-5, help="Max allowed absolute difference")
    args = parser.parse_args()

    bridge = load_json(args.bridge)
    dump = load_json(args.dump)
    observations = dump.get("observations", [])

    if not observations:
        raise SystemExit("dump contains no observations")

    worst_diff = 0.0
    worst_case: tuple[int, int, float, float, float] | None = None

    for case_index, item in enumerate(observations):
        expected = build_observation(
            bridge=bridge,
            observations=observations,
            case_index=case_index,
        )
        actual = [float(v) for v in item["obs"]]

        if len(actual) != OBS_DIM:
            raise SystemExit(f"case {case_index}: actual observation length is {len(actual)}, expected {OBS_DIM}")

        for obs_index, (a, e) in enumerate(zip(actual, expected)):
            diff = abs(a - e)
            if diff > worst_diff:
                worst_diff = diff
                worst_case = (case_index, obs_index, a, e, diff)

    print(f"[parity] observations={len(observations)} max_abs_diff={worst_diff:.8f}")
    if worst_case is not None:
        case_index, obs_index, actual, expected, diff = worst_case
        print(
            "[parity] worst "
            f"case={case_index} obs_index={obs_index} "
            f"actual={actual:.8f} expected={expected:.8f} diff={diff:.8f}"
        )

    if worst_diff > args.tolerance:
        raise SystemExit(f"[parity] FAILED: max diff {worst_diff:.8f} > tolerance {args.tolerance:.8f}")

    print("[parity] OK")


if __name__ == "__main__":
    main()