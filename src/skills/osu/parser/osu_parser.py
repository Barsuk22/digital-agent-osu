from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.skills.osu.domain.models import (
    CircleObject,
    DifficultySettings,
    HitObject,
    HitObjectType,
    ParsedBeatmap,
    SliderObject,
    SpinnerObject,
    TimingPoint,
)

TYPE_CIRCLE = 1
TYPE_SLIDER = 2
TYPE_NEW_COMBO = 4
TYPE_SPINNER = 8


def parse_key_value_section(lines: List[str]) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for line in lines:
        if not line or line.startswith("//"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def split_sections(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current is not None:
                sections[current].append("")
            continue

        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            sections[current] = []
            continue

        if current is not None:
            sections[current].append(line)

    return sections


def parse_timing_points(lines: List[str]) -> List[TimingPoint]:
    result: List[TimingPoint] = []
    for line in lines:
        if not line or line.startswith("//"):
            continue
        parts = line.split(",")
        if len(parts) < 8:
            continue

        result.append(
            TimingPoint(
                time_ms=float(parts[0]),
                beat_length=float(parts[1]),
                meter=int(parts[2]),
                sample_set=int(parts[3]),
                sample_index=int(parts[4]),
                volume=int(parts[5]),
                uninherited=parts[6] == "1",
                effects=int(parts[7]),
            )
        )

    result.sort(key=lambda tp: tp.time_ms)
    return result


def parse_slider_path(raw: str) -> Tuple[str, List[Tuple[float, float]]]:
    parts = raw.split("|")
    curve_type = parts[0]
    control_points: List[Tuple[float, float]] = []
    for point_raw in parts[1:]:
        px, py = point_raw.split(":")
        control_points.append((float(px), float(py)))
    return curve_type, control_points


def parse_hit_objects(lines: List[str]) -> List[HitObject]:
    result: List[HitObject] = []

    combo_index = 0
    combo_number = 0
    first_object = True

    for line in lines:
        if not line or line.startswith("//"):
            continue

        parts = line.split(",")
        if len(parts) < 5:
            continue

        x = float(parts[0])
        y = float(parts[1])
        time_ms = float(parts[2])
        object_type = int(parts[3])
        hitsound = int(parts[4])

        is_new_combo = first_object or bool(object_type & TYPE_NEW_COMBO)

        if is_new_combo:
            if not first_object:
                combo_skip = (object_type >> 4) & 0b111
                combo_index += 1 + combo_skip
            combo_number = 1
        else:
            combo_number += 1

        if object_type & TYPE_CIRCLE:
            result.append(
                HitObject(
                    kind=HitObjectType.CIRCLE,
                    circle=CircleObject(
                        x=x,
                        y=y,
                        time_ms=time_ms,
                        combo_index=combo_index,
                        combo_number=combo_number,
                        hitsound=hitsound,
                    ),
                )
            )
            first_object = False
            continue

        if object_type & TYPE_SLIDER:
            curve_raw = parts[5]
            repeats = int(parts[6])
            pixel_length = float(parts[7])
            edge_sounds = list(map(int, parts[8].split("|"))) if len(parts) > 8 and parts[8] else []
            edge_sets = parts[9].split("|") if len(parts) > 9 and parts[9] else []

            curve_type, control_points = parse_slider_path(curve_raw)

            result.append(
                HitObject(
                    kind=HitObjectType.SLIDER,
                    slider=SliderObject(
                        x=x,
                        y=y,
                        time_ms=time_ms,
                        combo_index=combo_index,
                        combo_number=combo_number,
                        hitsound=hitsound,
                        curve_type=curve_type,
                        control_points=control_points,
                        repeats=repeats,
                        pixel_length=pixel_length,
                        edge_sounds=edge_sounds,
                        edge_sets=edge_sets,
                    ),
                )
            )
            first_object = False
            continue

        if object_type & TYPE_SPINNER:
            end_time_ms = float(parts[5])
            result.append(
                HitObject(
                    kind=HitObjectType.SPINNER,
                    spinner=SpinnerObject(
                        x=x,
                        y=y,
                        time_ms=time_ms,
                        combo_index=combo_index,
                        combo_number=combo_number,
                        hitsound=hitsound,
                        end_time_ms=end_time_ms,
                    ),
                )
            )
            first_object = False
            continue

    return result


def parse_background_filename(events_lines: List[str]) -> Optional[str]:
    bg_pattern = re.compile(r'^\s*0\s*,\s*0\s*,\s*"([^"]+)"')
    for line in events_lines:
        if not line or line.startswith("//"):
            continue
        m = bg_pattern.match(line)
        if m:
            return m.group(1)
    return None


def parse_video_event(events_lines: List[str]) -> Tuple[Optional[str], float]:
    patterns = (
        re.compile(r'^\s*Video\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*"([^"]+)"', re.IGNORECASE),
        re.compile(r'^\s*1\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*"([^"]+)"'),
    )
    for line in events_lines:
        if not line or line.startswith("//"):
            continue
        for pattern in patterns:
            match = pattern.match(line)
            if match:
                return match.group(2), float(match.group(1))
    return None, 0.0


def resolve_audio_path(beatmap_dir: Path, audio_filename: str) -> Optional[Path]:
    if audio_filename:
        candidate = beatmap_dir / audio_filename
        if candidate.exists():
            return candidate

    fallback_names = ["audio.mp3", "audio.ogg", "audio.wav"]
    for name in fallback_names:
        candidate = beatmap_dir / name
        if candidate.exists():
            return candidate

    return None


def resolve_video_path(beatmap_dir: Path, video_filename: Optional[str]) -> Optional[Path]:
    if video_filename:
        candidate = beatmap_dir / video_filename
        if candidate.exists():
            return candidate

    for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov", "*.wmv"):
        matches = list(beatmap_dir.glob(ext))
        if matches:
            return matches[0]

    return None


def resolve_background_path(beatmap_dir: Path, background_filename: Optional[str]) -> Optional[Path]:
    if background_filename:
        candidate = beatmap_dir / background_filename
        if candidate.exists():
            return candidate

    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        matches = list(beatmap_dir.glob(ext))
        if matches:
            return matches[0]

    return None


def parse_beatmap(path: str | Path) -> ParsedBeatmap:
    beatmap_path = Path(path)
    beatmap_dir = beatmap_path.parent

    text = beatmap_path.read_text(encoding="utf-8")
    sections = split_sections(text)

    general = parse_key_value_section(sections.get("General", []))
    metadata = parse_key_value_section(sections.get("Metadata", []))
    difficulty_raw = parse_key_value_section(sections.get("Difficulty", []))

    difficulty = DifficultySettings(
        hp=float(difficulty_raw.get("HPDrainRate", 5)),
        cs=float(difficulty_raw.get("CircleSize", 5)),
        od=float(difficulty_raw.get("OverallDifficulty", 5)),
        ar=float(difficulty_raw.get("ApproachRate", difficulty_raw.get("OverallDifficulty", 5))),
        slider_multiplier=float(difficulty_raw.get("SliderMultiplier", 1.4)),
        slider_tick_rate=float(difficulty_raw.get("SliderTickRate", 1.0)),
    )

    audio_filename = general.get("AudioFilename", "")
    events_lines = sections.get("Events", [])
    background_filename = parse_background_filename(events_lines)
    video_filename, video_start_time_ms = parse_video_event(events_lines)

    return ParsedBeatmap(
        beatmap_path=beatmap_path,
        beatmap_dir=beatmap_dir,
        audio_filename=audio_filename,
        audio_path=resolve_audio_path(beatmap_dir, audio_filename),
        background_filename=background_filename,
        background_path=resolve_background_path(beatmap_dir, background_filename),
        video_filename=video_filename,
        video_path=resolve_video_path(beatmap_dir, video_filename),
        video_start_time_ms=video_start_time_ms,
        title=metadata.get("Title", ""),
        artist=metadata.get("Artist", ""),
        version=metadata.get("Version", ""),
        difficulty=difficulty,
        timing_points=parse_timing_points(sections.get("TimingPoints", [])),
        hit_objects=parse_hit_objects(sections.get("HitObjects", [])),
    )
