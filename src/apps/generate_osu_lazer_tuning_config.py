from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a candidate osu!lazer runtime config from analysis output.")
    parser.add_argument("--analysis", required=True, help="Path to *_analysis.json")
    parser.add_argument("--base-config", required=True, help="Base runtime config json")
    parser.add_argument("--out", dest="output_path", default=None, help="Output runtime config path")
    return parser.parse_args()


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_candidate(base_config: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(base_config))

    metrics = analysis["metrics"]
    control = result["control"]
    timing = result["timing"]

    edge_clamp_ratio = float(metrics["edge_clamp_ratio"])
    primary_mean = float(metrics["primary_distance_px"]["mean"])
    reference_mean = float(metrics["reference_cursor_distance_px"]["mean"])
    fps_mean = float(metrics["effective_fps"]["mean"])

    if edge_clamp_ratio >= 0.25:
        control["cursorSpeedScale"] = round(clamp(float(control["cursorSpeedScale"]) * 0.78, 6.0, 14.0), 2)
    elif primary_mean >= 90.0:
        control["cursorSpeedScale"] = round(clamp(float(control["cursorSpeedScale"]) * 0.88, 6.0, 14.0), 2)

    if reference_mean >= 220.0:
        timing["diagnosticInitialMapTimeMs"] = round(float(timing.get("diagnosticInitialMapTimeMs", 0.0)) + 180.0, 1)
    elif reference_mean >= 140.0:
        timing["diagnosticInitialMapTimeMs"] = round(float(timing.get("diagnosticInitialMapTimeMs", 0.0)) + 90.0, 1)

    if fps_mean < 50.0:
        timing["tickRateHz"] = round(clamp(float(timing["tickRateHz"]) - 5.0, 50.0, 60.0), 1)

    return result


def default_output_path(base_config_path: Path) -> Path:
    return base_config_path.with_name(f"{base_config_path.stem}.candidate.json")


def main() -> None:
    args = parse_args()
    analysis_path = Path(args.analysis)
    base_config_path = Path(args.base_config)
    analysis = load_json(analysis_path)
    base_config = load_json(base_config_path)
    candidate = build_candidate(base_config, analysis)
    output_path = Path(args.output_path) if args.output_path else default_output_path(base_config_path)
    output_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[candidate config] {output_path}")
    print(
        "[candidate values] "
        f"tickRateHz={candidate['timing']['tickRateHz']} "
        f"diagnosticInitialMapTimeMs={candidate['timing']['diagnosticInitialMapTimeMs']} "
        f"cursorSpeedScale={candidate['control']['cursorSpeedScale']}"
    )


if __name__ == "__main__":
    main()
