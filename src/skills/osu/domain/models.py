from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple


Vec2 = Tuple[float, float]


class HitObjectType(str, Enum):
    CIRCLE = "circle"
    SLIDER = "slider"
    SPINNER = "spinner"


@dataclass(slots=True)
class TimingPoint:
    time_ms: float
    beat_length: float
    meter: int
    sample_set: int
    sample_index: int
    volume: int
    uninherited: bool
    effects: int

    @property
    def slider_velocity_multiplier(self) -> float:
        if self.uninherited:
            return 1.0
        if self.beat_length == 0:
            return 1.0
        return max(0.1, -100.0 / self.beat_length)


@dataclass(slots=True)
class DifficultySettings:
    hp: float
    cs: float
    od: float
    ar: float
    slider_multiplier: float
    slider_tick_rate: float


@dataclass(slots=True)
class CircleObject:
    x: float
    y: float
    time_ms: float
    combo_index: int
    combo_number: int
    hitsound: int


@dataclass(slots=True)
class SliderObject:
    x: float
    y: float
    time_ms: float
    combo_index: int
    combo_number: int
    hitsound: int
    curve_type: str
    control_points: List[Vec2]
    repeats: int
    pixel_length: float
    edge_sounds: List[int] = field(default_factory=list)
    edge_sets: List[str] = field(default_factory=list)


@dataclass(slots=True)
class SpinnerObject:
    x: float
    y: float
    time_ms: float
    combo_index: int
    combo_number: int
    hitsound: int
    end_time_ms: float


@dataclass(slots=True)
class HitObject:
    kind: HitObjectType
    circle: Optional[CircleObject] = None
    slider: Optional[SliderObject] = None
    spinner: Optional[SpinnerObject] = None

    @property
    def time_ms(self) -> float:
        if self.kind == HitObjectType.CIRCLE:
            return self.circle.time_ms
        if self.kind == HitObjectType.SLIDER:
            return self.slider.time_ms
        return self.spinner.time_ms


@dataclass(slots=True)
class ParsedBeatmap:
    beatmap_path: Path
    beatmap_dir: Path
    audio_filename: str
    audio_path: Optional[Path]
    background_filename: Optional[str]
    background_path: Optional[Path]
    video_filename: Optional[str]
    video_path: Optional[Path]
    video_start_time_ms: float
    title: str
    artist: str
    version: str
    difficulty: DifficultySettings
    timing_points: List[TimingPoint]
    hit_objects: List[HitObject]
