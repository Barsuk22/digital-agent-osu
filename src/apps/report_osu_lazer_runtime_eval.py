from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.config.paths import PATHS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize bridge runtime calibration/eval reports.")
    parser.add_argument(
        "--summary",
        default=str(PATHS.project_root / "artifacts" / "runs" / "osu_lazer_runtime_calibration" / "sweep_summary.json"),
    )
    parser.add_argument("--top", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary_path = Path(args.summary)
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    candidates = sorted(payload.get("candidates", []), key=lambda item: float(item.get("score", 1e18)))

    print(f"[runtime eval summary] {summary_path}")
    for index, item in enumerate(candidates[: max(1, args.top)], start=1):
        metrics = item["metrics"]
        print(
            f"[top {index}] {item['name']} "
            f"score={item['score']:.2f} "
            f"ref={metrics['reference_cursor_distance_px']['mean']:.1f}px "
            f"primary={metrics['primary_distance_px']['mean']:.1f}px "
            f"edge={metrics['edge_clamp_ratio']:.3f} "
            f"click={metrics['reference_click_match_ratio']:.3f} "
            f"fps={metrics['effective_fps']['mean']:.1f}"
        )

    best = payload.get("best")
    if best:
        print(
            f"[best config] {best['config_path']} "
            f"t={best['timing']['diagnosticInitialMapTimeMs']:.1f} "
            f"a={best['timing']['audioOffsetMs']:.1f} "
            f"i={best['timing']['inputDelayMs']:.1f} "
            f"s={best['control']['cursorSpeedScale']:.2f}"
        )


if __name__ == "__main__":
    main()
