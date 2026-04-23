from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two osu!lazer runtime analysis reports.")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    return parser.parse_args()


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    baseline = load(args.baseline)
    candidate = load(args.candidate)
    b = baseline["metrics"]
    c = candidate["metrics"]

    comparisons = [
        ("reference_cursor_distance_px.mean", b["reference_cursor_distance_px"]["mean"], c["reference_cursor_distance_px"]["mean"], "lower"),
        ("primary_distance_px.mean", b["primary_distance_px"]["mean"], c["primary_distance_px"]["mean"], "lower"),
        ("edge_clamp_ratio", b["edge_clamp_ratio"], c["edge_clamp_ratio"], "lower"),
        ("reference_click_match_ratio", b["reference_click_match_ratio"], c["reference_click_match_ratio"], "higher"),
        ("effective_fps.mean", b["effective_fps"]["mean"], c["effective_fps"]["mean"], "higher"),
    ]

    print("[analysis compare]")
    for name, before, after, direction in comparisons:
        delta = after - before
        improved = delta < 0 if direction == "lower" else delta > 0
        marker = "better" if improved else "worse" if abs(delta) > 1e-9 else "same"
        print(f"{name}: baseline={before:.4f} candidate={after:.4f} delta={delta:+.4f} => {marker}")


if __name__ == "__main__":
    main()
