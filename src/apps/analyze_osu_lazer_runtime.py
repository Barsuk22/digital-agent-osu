from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.core.config.paths import PATHS
from src.skills.osu.viewer.replay_models import ReplayFrame, load_replay


@dataclass(slots=True)
class SummaryStats:
    count: int
    mean: float
    median: float
    p95: float
    minimum: float
    maximum: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze osu!lazer bridge runtime traces against offline replay.")
    parser.add_argument("--live-trace", dest="live_trace", default=None)
    parser.add_argument("--reference-replay", dest="reference_replay", default=str(PATHS.phase8_easy_best_eval_replay))
    parser.add_argument("--bridge-map", dest="bridge_map", default=str(PATHS.project_root / "exports" / "osu_lazer_bridge_map.json"))
    parser.add_argument("--out", dest="output_path", default=None)
    return parser.parse_args()


def summarize(values: list[float]) -> SummaryStats:
    if not values:
        return SummaryStats(count=0, mean=0.0, median=0.0, p95=0.0, minimum=0.0, maximum=0.0)

    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.95) - 1))
    return SummaryStats(
        count=len(values),
        mean=float(statistics.fmean(values)),
        median=float(statistics.median(values)),
        p95=float(ordered[p95_index]),
        minimum=float(ordered[0]),
        maximum=float(ordered[-1]),
    )


def choose_latest_trace() -> Path:
    logs_dir = PATHS.project_root / "external" / "osu_lazer_controller" / "bin" / "Debug" / "net8.0-windows" / "logs"
    traces = sorted(
        [path for path in logs_dir.glob("warmup_trace_*.json") if not path.name.endswith("_analysis.json")],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not traces:
        raise FileNotFoundError(f"No bridge traces found in {logs_dir}")
    return traces[0]


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def find_reference_frame(frames: list[ReplayFrame], time_ms: float) -> ReplayFrame | None:
    if not frames:
        return None

    lo = 0
    hi = len(frames) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if frames[mid].time_ms < time_ms:
            lo = mid + 1
        else:
            hi = mid

    candidates = [frames[min(lo, len(frames) - 1)]]
    if lo > 0:
        candidates.append(frames[lo - 1])
    return min(candidates, key=lambda frame: abs(frame.time_ms - time_ms))


def build_object_lookup(bridge_map: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for obj in bridge_map.get("hitObjects", []):
        kind = str(obj.get("kind", "unknown"))
        time_bucket = int(round(float(obj.get("timeMs", 0.0))))
        lookup[(kind, time_bucket)] = obj
    return lookup


def parse_primary_label(label: str) -> tuple[str, int] | None:
    if not label or label == "none" or "@" not in label:
        return None
    kind, raw_time = label.split("@", 1)
    raw_time = raw_time.replace(",", ".")
    try:
        return kind, int(round(float(raw_time)))
    except ValueError:
        return None


def metrics_from_live_trace(
    ticks: list[dict[str, Any]],
    object_lookup: dict[tuple[str, int], dict[str, Any]],
    reference_frames: list[ReplayFrame],
) -> dict[str, Any]:
    control_ticks = [tick for tick in ticks if int(tick.get("TickIndex", 0)) > 0]

    loop_times = [float(tick.get("LoopElapsedMs", 0.0)) for tick in control_ticks]
    policy_latencies = [float(tick.get("PolicyLatencyMs", 0.0)) for tick in control_ticks]
    map_times = [float(tick.get("MapTimeMs", 0.0)) for tick in control_ticks]
    dt_values = [curr - prev for prev, curr in zip(map_times, map_times[1:]) if curr >= prev]
    effective_fps = [1000.0 / dt for dt in dt_values if dt > 1e-6]

    clamp_ticks = 0
    slider_ticks = 0
    spinner_ticks = 0
    click_ticks = 0
    raw_click_ticks = 0
    slider_hold_ticks = 0
    spinner_hold_ticks = 0
    primary_distances: list[float] = []
    reference_cursor_distances: list[float] = []
    reference_click_matches = 0
    reference_click_total = 0
    reference_cursor_samples = 0

    for tick in control_ticks:
        cursor_x = float(tick.get("CursorX", 0.0))
        cursor_y = float(tick.get("CursorY", 0.0))
        if cursor_x <= 1e-6 or cursor_x >= 512.0 - 1e-6 or cursor_y <= 1e-6 or cursor_y >= 384.0 - 1e-6:
            clamp_ticks += 1

        if bool(tick.get("ActiveSlider", False)):
            slider_ticks += 1
        if bool(tick.get("ActiveSpinner", False)):
            spinner_ticks += 1
        if bool(tick.get("ClickDown", False)):
            click_ticks += 1
        if bool(tick.get("RawClickDown", False)):
            raw_click_ticks += 1
        if bool(tick.get("SliderHoldDown", False)):
            slider_hold_ticks += 1
        if bool(tick.get("SpinnerHoldDown", False)):
            spinner_hold_ticks += 1

        primary = parse_primary_label(str(tick.get("PrimaryObject", "none")))
        if primary is not None and primary in object_lookup:
            obj = object_lookup[primary]
            primary_distances.append(distance(cursor_x, cursor_y, float(obj["x"]), float(obj["y"])))

        reference = find_reference_frame(reference_frames, float(tick.get("MapTimeMs", 0.0)))
        if reference is not None:
            reference_cursor_distances.append(distance(cursor_x, cursor_y, reference.cursor_x, reference.cursor_y))
            reference_cursor_samples += 1
            reference_click_total += 1
            if bool(tick.get("ClickDown", False)) == bool(reference.click_down):
                reference_click_matches += 1

    return {
        "ticks": len(control_ticks),
        "loop_time_ms": asdict(summarize(loop_times)),
        "policy_latency_ms": asdict(summarize(policy_latencies)),
        "effective_fps": asdict(summarize(effective_fps)),
        "primary_distance_px": asdict(summarize(primary_distances)),
        "reference_cursor_distance_px": asdict(summarize(reference_cursor_distances)),
        "edge_clamp_ratio": 0.0 if not control_ticks else clamp_ticks / len(control_ticks),
        "active_slider_ratio": 0.0 if not control_ticks else slider_ticks / len(control_ticks),
        "active_spinner_ratio": 0.0 if not control_ticks else spinner_ticks / len(control_ticks),
        "click_ratio": 0.0 if not control_ticks else click_ticks / len(control_ticks),
        "raw_click_ratio": 0.0 if not control_ticks else raw_click_ticks / len(control_ticks),
        "slider_hold_ratio": 0.0 if not control_ticks else slider_hold_ticks / len(control_ticks),
        "spinner_hold_ratio": 0.0 if not control_ticks else spinner_hold_ticks / len(control_ticks),
        "reference_click_match_ratio": 0.0 if reference_click_total <= 0 else reference_click_matches / reference_click_total,
        "reference_cursor_samples": reference_cursor_samples,
    }


def make_recommendations(metrics: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []

    edge_clamp_ratio = float(metrics["edge_clamp_ratio"])
    ref_cursor_mean = float(metrics["reference_cursor_distance_px"]["mean"])
    primary_distance_mean = float(metrics["primary_distance_px"]["mean"])
    fps_mean = float(metrics["effective_fps"]["mean"])
    policy_p95 = float(metrics["policy_latency_ms"]["p95"])
    click_match = float(metrics["reference_click_match_ratio"])

    if edge_clamp_ratio >= 0.20:
        recommendations.append(
            "Высокий edge-clamp ratio: сначала уменьшить `cursorSpeedScale` и проверить coordinate mapping/playfield bounds."
        )
    if ref_cursor_mean >= 80.0:
        recommendations.append(
            "Большое расхождение с offline replay: подбирать `audioOffsetMs` и `inputDelayMs`, затем сравнить live trace ещё раз."
        )
    if primary_distance_mean >= 90.0:
        recommendations.append(
            "Курсор слишком далеко от primary target: проверить стартовый offset карты и не завышен ли `cursorSpeedScale`."
        )
    if click_match <= 0.70:
        recommendations.append(
            "Слабое совпадение click-state с reference replay: подстроить `clickThreshold`, `sliderHoldThreshold` и `spinnerHoldThreshold`."
        )
    if fps_mean < 50.0:
        recommendations.append(
            "Control loop проседает ниже 50 FPS: смотреть `PolicyLatencyMs`, захват окна и лишние фоновые процессы."
        )
    if policy_p95 > 10.0:
        recommendations.append(
            "Высокий p95 policy latency: перед живыми тестами стоит оптимизировать bridge или перейти к ONNX позже."
        )
    if not recommendations:
        recommendations.append("Критичных runtime-аномалий не найдено, можно переходить к более точной калибровке по offset и mapping.")

    return recommendations


def build_report(
    live_trace_path: Path,
    reference_replay_path: Path,
    bridge_map_path: Path,
) -> dict[str, Any]:
    ticks = load_json(live_trace_path)
    bridge_map = load_json(bridge_map_path)
    reference_frames = load_replay(reference_replay_path)

    object_lookup = build_object_lookup(bridge_map)
    metrics = metrics_from_live_trace(ticks, object_lookup, reference_frames)

    return {
        "inputs": {
            "live_trace": str(live_trace_path),
            "reference_replay": str(reference_replay_path),
            "bridge_map": str(bridge_map_path),
        },
        "map": {
            "artist": bridge_map.get("artist"),
            "title": bridge_map.get("title"),
            "version": bridge_map.get("version"),
            "objects": len(bridge_map.get("hitObjects", [])),
        },
        "metrics": metrics,
        "recommendations": make_recommendations(metrics),
    }


def default_output_path(live_trace_path: Path) -> Path:
    return live_trace_path.with_name(f"{live_trace_path.stem}_analysis.json")


def main() -> None:
    args = parse_args()
    live_trace_path = Path(args.live_trace) if args.live_trace else choose_latest_trace()
    reference_replay_path = Path(args.reference_replay)
    bridge_map_path = Path(args.bridge_map)

    report = build_report(live_trace_path, reference_replay_path, bridge_map_path)
    output_path = Path(args.output_path) if args.output_path else default_output_path(live_trace_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = report["metrics"]
    print(f"[lazer analysis] {output_path}")
    print(
        "[runtime] "
        f"ticks={metrics['ticks']} "
        f"fps_mean={metrics['effective_fps']['mean']:.1f} "
        f"loop_p95={metrics['loop_time_ms']['p95']:.2f}ms "
        f"policy_p95={metrics['policy_latency_ms']['p95']:.2f}ms"
    )
    print(
        "[alignment] "
        f"primary_mean={metrics['primary_distance_px']['mean']:.1f}px "
        f"reference_mean={metrics['reference_cursor_distance_px']['mean']:.1f}px "
        f"edge_clamp={metrics['edge_clamp_ratio']:.3f} "
        f"click_match={metrics['reference_click_match_ratio']:.3f}"
    )
    for item in report["recommendations"]:
        print(f"[recommend] {item}")


if __name__ == "__main__":
    main()
