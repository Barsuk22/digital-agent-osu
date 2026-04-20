from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SkillExtractionConfig:
    min_extraction_score: float = 0.62
    min_confidence: float = 0.55
    slider_min_inside_ratio: float = 0.88
    slider_max_dpx: float = 42.0
    slider_min_finish_rate: float = 0.72
    reverse_min_follow_ratio: float = 0.70
    chain_max_timing_median_ms: float = 72.0
    chain_max_mean_click_distance_px: float = 70.0
    spinner_min_hold_ratio: float = 0.94
    spinner_min_step_ratio: float = 0.90
    jump_max_timing_median_ms: float = 80.0
    dedup_similarity_threshold: float = 0.86


@dataclass(slots=True)
class SkillSelectorConfig:
    min_similarity: float = 0.60
    min_confidence: float = 0.56
    max_risk: float = 0.70
    cooldown_ms: float = 220.0
    max_active_window_ms: float = 720.0
    overuse_window_ms: float = 3200.0
    max_recent_uses_per_type: int = 3
    enable_post_use_adaptation: bool = True
    enable_confidence_gate: bool = True
    enable_ranker: bool = True
    enable_fallback: bool = True


@dataclass(slots=True)
class SkillExecutorConfig:
    mode: str = "assist_bias"
    action_bias_strength: float = 0.32
    slider_bias_strength: float = 0.38
    spinner_bias_strength: float = 0.26
    jump_bias_strength: float = 0.28
    click_bias_strength: float = 0.18
    abort_far_distance_px: float = 150.0
    abort_bad_slider_distance_px: float = 115.0
    end_progress: float = 0.98
    min_window_ms: float = 80.0


@dataclass(slots=True)
class SkillSystemConfig:
    enable_skill_system: bool = False
    skill_memory_path: str = ""
    log_runtime: bool = False
    log_rejections: bool = False
    extraction: SkillExtractionConfig = field(default_factory=SkillExtractionConfig)
    selector: SkillSelectorConfig = field(default_factory=SkillSelectorConfig)
    executor: SkillExecutorConfig = field(default_factory=SkillExecutorConfig)
