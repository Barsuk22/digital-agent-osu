from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.config.paths import PATHS
from src.skills.osu.domain.models import HitObjectType
from src.skills.osu.domain.osu_rules import slider_duration_ms
from src.skills.osu.domain.slider_path import build_slider_path
from src.skills.osu.parser.osu_parser import parse_beatmap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a parsed .osu beatmap into a bridge-friendly JSON format.")
    parser.add_argument("--map", dest="map_path", default=str(PATHS.beginner_ka_map))
    parser.add_argument("--out", dest="output_path", default=str(Path("exports") / "osu_lazer_bridge_map.json"))
    return parser.parse_args()


def export_hit_object(beatmap, obj: object, index: int) -> dict:
    if obj.kind == HitObjectType.CIRCLE:
        circle = obj.circle
        return {
            "index": index,
            "kind": "circle",
            "timeMs": circle.time_ms,
            "x": circle.x,
            "y": circle.y,
            "comboIndex": circle.combo_index,
            "comboNumber": circle.combo_number,
            "hitsound": circle.hitsound,
        }

    if obj.kind == HitObjectType.SLIDER:
        slider = obj.slider
        path = build_slider_path(slider)
        sampled_points = [{"x": x, "y": y} for x, y in path.sampled_points]
        return {
            "index": index,
            "kind": "slider",
            "timeMs": slider.time_ms,
            "x": slider.x,
            "y": slider.y,
            "comboIndex": slider.combo_index,
            "comboNumber": slider.combo_number,
            "hitsound": slider.hitsound,
            "curveType": slider.curve_type,
            "controlPoints": [{"x": x, "y": y} for x, y in slider.control_points],
            "repeats": slider.repeats,
            "pixelLength": slider.pixel_length,
            "durationMs": slider_duration_ms(beatmap, slider),
            "sampledPath": sampled_points,
            "cumulativeLengths": path.cumulative_lengths,
            "totalLength": path.total_length,
        }

    spinner = obj.spinner
    return {
        "index": index,
        "kind": "spinner",
        "timeMs": spinner.time_ms,
        "endTimeMs": spinner.end_time_ms,
        "x": spinner.x,
        "y": spinner.y,
        "comboIndex": spinner.combo_index,
        "comboNumber": spinner.combo_number,
        "hitsound": spinner.hitsound,
    }


def main() -> None:
    args = parse_args()
    beatmap = parse_beatmap(args.map_path)

    payload = {
        "schemaVersion": 1,
        "beatmapPath": str(beatmap.beatmap_path),
        "title": beatmap.title,
        "artist": beatmap.artist,
        "version": beatmap.version,
        "difficulty": {
            "hp": beatmap.difficulty.hp,
            "cs": beatmap.difficulty.cs,
            "od": beatmap.difficulty.od,
            "ar": beatmap.difficulty.ar,
            "sliderMultiplier": beatmap.difficulty.slider_multiplier,
            "sliderTickRate": beatmap.difficulty.slider_tick_rate,
        },
        "timingPoints": [
            {
                "timeMs": tp.time_ms,
                "beatLength": tp.beat_length,
                "meter": tp.meter,
                "sampleSet": tp.sample_set,
                "sampleIndex": tp.sample_index,
                "volume": tp.volume,
                "uninherited": tp.uninherited,
                "effects": tp.effects,
            }
            for tp in beatmap.timing_points
        ],
        "hitObjects": [
            export_hit_object(beatmap, obj, index)
            for index, obj in enumerate(beatmap.hit_objects)
        ],
    }

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "event": "bridge_map_exported",
                "output": str(output_path),
                "objects": len(payload["hitObjects"]),
                "timingPoints": len(payload["timingPoints"]),
                "beatmap": f"{beatmap.artist} - {beatmap.title} [{beatmap.version}]",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
