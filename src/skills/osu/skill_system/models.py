from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SkillType(str, Enum):
    SLIDER_FOLLOW = "slider_follow"
    REVERSE_SLIDER = "reverse_slider"
    SHORT_CHAIN = "short_chain"
    SPINNER_CONTROL = "spinner_control"
    SIMPLE_JUMP = "simple_jump"
    SIMPLE_DOUBLE = "simple_double"
    BURST = "burst"
    TRIPLETS = "triplets"
    KICK_SLIDERS = "kick_sliders"
    SLIDER_AIM = "slider_aim"


@dataclass(slots=True)
class SkillCreationSource:
    map_id: str
    replay_id: str
    checkpoint_id: str
    frame_start: int
    frame_end: int
    object_start: int
    object_end: int


@dataclass(slots=True)
class SkillContextSignature:
    object_sequence: tuple[str, ...]
    local_density_bucket: str
    bpm_bucket: str
    spacing_bucket: str
    angle_bucket: str
    slider_length_bucket: str
    reverse_count: int
    approach_difficulty_bucket: str
    timing_pressure_bucket: str
    previous_relation_bucket: str
    next_relation_bucket: str

    def stable_key(self) -> str:
        return "|".join(
            [
                ",".join(self.object_sequence),
                self.local_density_bucket,
                self.bpm_bucket,
                self.spacing_bucket,
                self.angle_bucket,
                self.slider_length_bucket,
                str(self.reverse_count),
                self.approach_difficulty_bucket,
                self.timing_pressure_bucket,
                self.previous_relation_bucket,
                self.next_relation_bucket,
            ]
        )


@dataclass(slots=True)
class SkillSuccessStats:
    uses: int = 0
    successful_uses: int = 0
    failed_uses: int = 0
    avg_gain_vs_baseline: float = 0.0
    avg_hit_delta: float = 0.0
    avg_slider_quality_delta: float = 0.0
    avg_timing_delta: float = 0.0
    avg_confidence_after_use: float = 0.0

    @property
    def success_rate(self) -> float:
        return 0.0 if self.uses <= 0 else self.successful_uses / self.uses

    def update(self, record: SkillUsageRecord) -> None:
        self.uses += 1
        if record.success:
            self.successful_uses += 1
        else:
            self.failed_uses += 1

        n = float(self.uses)
        self.avg_gain_vs_baseline += (record.gain_vs_baseline - self.avg_gain_vs_baseline) / n
        self.avg_hit_delta += (record.hit_delta - self.avg_hit_delta) / n
        self.avg_slider_quality_delta += (record.slider_quality_delta - self.avg_slider_quality_delta) / n
        self.avg_timing_delta += (record.timing_delta - self.avg_timing_delta) / n
        self.avg_confidence_after_use += (record.confidence_after_use - self.avg_confidence_after_use) / n


@dataclass(slots=True)
class SkillFailureStats:
    aborts: int = 0
    harmful_uses: int = 0
    false_matches: int = 0
    last_failure_reason: str = ""


@dataclass(slots=True)
class SkillUsageRecord:
    skill_id: str
    skill_type: str
    map_id: str
    started_at_ms: float
    ended_at_ms: float
    success: bool
    gain_vs_baseline: float
    hit_delta: float
    slider_quality_delta: float
    timing_delta: float
    confidence_before_use: float
    confidence_after_use: float
    fallback_used: bool
    reason: str


@dataclass(slots=True)
class SkillEntry:
    skill_id: str
    skill_type: str
    creation_source: SkillCreationSource
    context_signature: SkillContextSignature
    pattern_features: dict[str, float | int | str]
    action_summary: dict[str, float | int | str]
    applicability_conditions: dict[str, float | int | str | bool]
    success_stats: SkillSuccessStats = field(default_factory=SkillSuccessStats)
    failure_stats: SkillFailureStats = field(default_factory=SkillFailureStats)
    confidence: float = 0.0
    support_count: int = 1
    last_used_at: str = ""
    last_updated_at: str = field(default_factory=utc_now_iso)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.skill_id:
            raise ValueError("skill_id is required")
        if self.skill_type not in {item.value for item in SkillType}:
            raise ValueError(f"unsupported skill_type: {self.skill_type}")
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        self.support_count = max(1, int(self.support_count))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SkillEntry:
        return cls(
            skill_id=str(payload["skill_id"]),
            skill_type=str(payload["skill_type"]),
            creation_source=SkillCreationSource(**payload["creation_source"]),
            context_signature=SkillContextSignature(
                object_sequence=tuple(payload["context_signature"]["object_sequence"]),
                local_density_bucket=payload["context_signature"]["local_density_bucket"],
                bpm_bucket=payload["context_signature"]["bpm_bucket"],
                spacing_bucket=payload["context_signature"]["spacing_bucket"],
                angle_bucket=payload["context_signature"]["angle_bucket"],
                slider_length_bucket=payload["context_signature"]["slider_length_bucket"],
                reverse_count=int(payload["context_signature"]["reverse_count"]),
                approach_difficulty_bucket=payload["context_signature"]["approach_difficulty_bucket"],
                timing_pressure_bucket=payload["context_signature"]["timing_pressure_bucket"],
                previous_relation_bucket=payload["context_signature"]["previous_relation_bucket"],
                next_relation_bucket=payload["context_signature"]["next_relation_bucket"],
            ),
            pattern_features=dict(payload.get("pattern_features", {})),
            action_summary=dict(payload.get("action_summary", {})),
            applicability_conditions=dict(payload.get("applicability_conditions", {})),
            success_stats=SkillSuccessStats(**payload.get("success_stats", {})),
            failure_stats=SkillFailureStats(**payload.get("failure_stats", {})),
            confidence=float(payload.get("confidence", 0.0)),
            support_count=int(payload.get("support_count", 1)),
            last_used_at=str(payload.get("last_used_at", "")),
            last_updated_at=str(payload.get("last_updated_at", utc_now_iso())),
            tags=list(payload.get("tags", [])),
        )


@dataclass(slots=True)
class SkillExtractionCandidate:
    skill_type: str
    creation_source: SkillCreationSource
    context_signature: SkillContextSignature
    pattern_features: dict[str, float | int | str]
    action_summary: dict[str, float | int | str]
    applicability_conditions: dict[str, float | int | str | bool]
    extraction_score: float
    stability_score: float
    transfer_potential_score: float
    noise_penalty: float
    reject_reason: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        raw = (
            0.45 * self.extraction_score
            + 0.35 * self.stability_score
            + 0.20 * self.transfer_potential_score
            - self.noise_penalty
        )
        return max(0.0, min(1.0, raw))

    def to_entry(self, skill_id: str) -> SkillEntry:
        return SkillEntry(
            skill_id=skill_id,
            skill_type=self.skill_type,
            creation_source=self.creation_source,
            context_signature=self.context_signature,
            pattern_features=self.pattern_features,
            action_summary=self.action_summary,
            applicability_conditions=self.applicability_conditions,
            confidence=self.confidence,
            support_count=1,
            tags=self.tags,
        )


@dataclass(slots=True)
class SkillMemoryFile:
    schema_version: int
    generated_at: str
    skills: list[SkillEntry]

    def to_json(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "skills": [skill.to_dict() for skill in self.skills],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> SkillMemoryFile:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        version = int(payload.get("schema_version", 0))
        if version != SCHEMA_VERSION:
            raise ValueError(f"unsupported skill memory schema version: {version}")
        return cls(
            schema_version=version,
            generated_at=str(payload.get("generated_at", "")),
            skills=[SkillEntry.from_dict(item) for item in payload.get("skills", [])],
        )
