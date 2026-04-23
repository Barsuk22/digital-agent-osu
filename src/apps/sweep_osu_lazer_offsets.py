from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from src.core.config.paths import PATHS


@dataclass(slots=True)
class SweepCandidate:
    name: str
    config_path: Path
    trace_path: Path | None
    analysis_path: Path | None
    score: float | None
    metrics: dict[str, Any] | None
    timing: dict[str, float]
    control: dict[str, float]


def parse_csv_floats(raw: str) -> list[float]:
    return [float(part.strip()) for part in raw.split(",") if part.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an automated osu!lazer bridge calibration sweep.")
    parser.add_argument(
        "--base-config",
        default=str(PATHS.project_root / "external" / "osu_lazer_controller" / "configs" / "runtime.live_probe.json"),
    )
    parser.add_argument(
        "--initial-times",
        default="1800,1890,1980",
        help="Comma-separated diagnosticInitialMapTimeMs values.",
    )
    parser.add_argument(
        "--audio-offsets",
        default="0",
        help="Comma-separated audioOffsetMs values.",
    )
    parser.add_argument(
        "--input-delays",
        default="0",
        help="Comma-separated inputDelayMs values.",
    )
    parser.add_argument(
        "--cursor-speeds",
        default="14.0",
        help="Comma-separated cursorSpeedScale values.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PATHS.project_root / "artifacts" / "runs" / "osu_lazer_runtime_calibration"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of candidates to run. 0 means all.",
    )
    return parser.parse_args()


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def trace_logs_dir() -> Path:
    return PATHS.project_root / "external" / "osu_lazer_controller" / "bin" / "Debug" / "net8.0-windows" / "logs"


def current_trace_set() -> set[Path]:
    return set(trace_logs_dir().glob("warmup_trace_*.json"))


def newest_trace_after(previous: set[Path]) -> Path:
    candidates = [path for path in current_trace_set() if path not in previous and not path.name.endswith("_analysis.json")]
    if not candidates:
        traces = [path for path in current_trace_set() if not path.name.endswith("_analysis.json")]
        if not traces:
            raise FileNotFoundError("No trace files found after bridge run.")
        return max(traces, key=lambda path: path.stat().st_mtime)
    return max(candidates, key=lambda path: path.stat().st_mtime)


def candidate_score(metrics: dict[str, Any]) -> float:
    # Lower is better.
    return (
        float(metrics["reference_cursor_distance_px"]["mean"]) * 1.0
        + float(metrics["primary_distance_px"]["mean"]) * 0.75
        + float(metrics["edge_clamp_ratio"]) * 250.0
        - float(metrics["reference_click_match_ratio"]) * 80.0
        - float(metrics["effective_fps"]["mean"]) * 0.5
    )


def build_candidate_config(
    base_config: dict[str, Any],
    initial_time_ms: float,
    audio_offset_ms: float,
    input_delay_ms: float,
    cursor_speed_scale: float,
) -> dict[str, Any]:
    config = json.loads(json.dumps(base_config))
    config["timing"]["diagnosticInitialMapTimeMs"] = initial_time_ms
    config["timing"]["audioOffsetMs"] = audio_offset_ms
    config["timing"]["inputDelayMs"] = input_delay_ms
    config["control"]["cursorSpeedScale"] = cursor_speed_scale
    return config


def run_bridge(config_path: Path) -> Path:
    previous = current_trace_set()
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PATHS.project_root / "external" / "osu_lazer_controller" / "start_bridge.ps1"),
        "-ConfigPath",
        str(config_path),
    ]
    subprocess.run(command, cwd=PATHS.project_root, check=True)
    return newest_trace_after(previous)


def run_analysis(trace_path: Path, analysis_path: Path) -> dict[str, Any]:
    command = [
        str(Path(sys.executable)),
        "-m",
        "src.apps.analyze_osu_lazer_runtime",
        "--live-trace",
        str(trace_path),
        "--out",
        str(analysis_path),
    ]
    subprocess.run(command, cwd=PATHS.project_root, check=True)
    return load_json(analysis_path)


def generate_candidates(args: argparse.Namespace, base_config: dict[str, Any], output_dir: Path) -> list[SweepCandidate]:
    candidates: list[SweepCandidate] = []
    limit = max(0, int(args.limit))
    index = 0
    for initial_time_ms in parse_csv_floats(args.initial_times):
        for audio_offset_ms in parse_csv_floats(args.audio_offsets):
            for input_delay_ms in parse_csv_floats(args.input_delays):
                for cursor_speed_scale in parse_csv_floats(args.cursor_speeds):
                    index += 1
                    if limit and len(candidates) >= limit:
                        return candidates

                    name = (
                        f"t{int(round(initial_time_ms))}"
                        f"_a{int(round(audio_offset_ms))}"
                        f"_i{int(round(input_delay_ms))}"
                        f"_s{cursor_speed_scale:.2f}".replace(".", "_")
                    )
                    config = build_candidate_config(
                        base_config=base_config,
                        initial_time_ms=initial_time_ms,
                        audio_offset_ms=audio_offset_ms,
                        input_delay_ms=input_delay_ms,
                        cursor_speed_scale=cursor_speed_scale,
                    )
                    config_path = output_dir / "configs" / f"{name}.json"
                    save_json(config_path, config)
                    candidates.append(
                        SweepCandidate(
                            name=name,
                            config_path=config_path,
                            trace_path=None,
                            analysis_path=None,
                            score=None,
                            metrics=None,
                            timing={
                                "diagnosticInitialMapTimeMs": initial_time_ms,
                                "audioOffsetMs": audio_offset_ms,
                                "inputDelayMs": input_delay_ms,
                            },
                            control={"cursorSpeedScale": cursor_speed_scale},
                        )
                    )
    return candidates


def main() -> None:
    args = parse_args()
    base_config = load_json(args.base_config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = generate_candidates(args, base_config, output_dir)
    results: list[dict[str, Any]] = []
    best: SweepCandidate | None = None

    for idx, candidate in enumerate(candidates, start=1):
        print(
            f"[sweep] {idx}/{len(candidates)} "
            f"{candidate.name} "
            f"t={candidate.timing['diagnosticInitialMapTimeMs']:.1f} "
            f"a={candidate.timing['audioOffsetMs']:.1f} "
            f"i={candidate.timing['inputDelayMs']:.1f} "
            f"s={candidate.control['cursorSpeedScale']:.2f}"
        )
        trace_path = run_bridge(candidate.config_path)
        analysis_path = output_dir / "analysis" / f"{candidate.name}_analysis.json"
        analysis = run_analysis(trace_path, analysis_path)
        metrics = analysis["metrics"]
        score = candidate_score(metrics)

        candidate.trace_path = trace_path
        candidate.analysis_path = analysis_path
        candidate.metrics = metrics
        candidate.score = score

        results.append(
            {
                "name": candidate.name,
                "score": score,
                "config_path": str(candidate.config_path),
                "trace_path": str(trace_path),
                "analysis_path": str(analysis_path),
                "timing": candidate.timing,
                "control": candidate.control,
                "metrics": metrics,
            }
        )

        if best is None or (candidate.score is not None and candidate.score < (best.score or float("inf"))):
            best = candidate

        print(
            "[sweep result] "
            f"score={score:.2f} "
            f"ref={metrics['reference_cursor_distance_px']['mean']:.1f}px "
            f"primary={metrics['primary_distance_px']['mean']:.1f}px "
            f"edge={metrics['edge_clamp_ratio']:.3f} "
            f"click={metrics['reference_click_match_ratio']:.3f}"
        )

    summary = {
        "base_config": str(Path(args.base_config).resolve()),
        "candidates": results,
        "best": None if best is None else {
            "name": best.name,
            "score": best.score,
            "config_path": str(best.config_path),
            "trace_path": str(best.trace_path) if best.trace_path else None,
            "analysis_path": str(best.analysis_path) if best.analysis_path else None,
            "timing": best.timing,
            "control": best.control,
        },
    }

    summary_path = output_dir / "sweep_summary.json"
    save_json(summary_path, summary)
    print(f"[sweep summary] {summary_path}")
    if best is not None:
        print(
            "[best] "
            f"{best.name} score={best.score:.2f} "
            f"config={best.config_path}"
        )


if __name__ == "__main__":
    main()
