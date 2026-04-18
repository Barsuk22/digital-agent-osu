from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal

from src.core.config.paths import PATHS
from src.skills.osu.env.osu_env import OsuEnv
from src.skills.osu.env.types import OsuAction, OsuObservation, UpcomingObjectView
from src.skills.osu.parser.osu_parser import parse_beatmap


@dataclass(slots=True)
class TrainConfig:
    beatmap_path: str = str(PATHS.active_map)
    phase_name: str = "phase5_slider_control"

    seed: int = 42
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    updates: int = 200
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_ratio: float = 0.10

    # Чуть сильнее держим исследование, чтобы не схлопывалась политика
    entropy_coef: float = 0.003
    value_coef: float = 0.5
    learning_rate: float = 5e-5
    epochs_per_update: int = 3
    minibatch_size: int = 256
    hidden_dim: int = 256

    dt_ms: float = 16.6667
    upcoming_count: int = 5
    cursor_speed_scale: float = 11.0
    click_threshold: float = 0.75
    slider_hold_threshold: float = 0.45

    source_checkpoint_path: str = str(PATHS.phase4_slider_best_checkpoint)
    run_dir: str = str(PATHS.osu_phase5_slider_control_run_dir)
    checkpoint_dir: str = str(PATHS.phase5_slider_checkpoints_dir)
    logs_dir: str = str(PATHS.phase5_slider_logs_dir)
    metrics_dir: str = str(PATHS.phase5_slider_metrics_dir)
    replays_dir: str = str(PATHS.phase5_slider_replays_dir)
    eval_dir: str = str(PATHS.phase5_slider_eval_dir)
    latest_ckpt_name: str = "latest_slider_control.pt"
    best_ckpt_name: str = "best_slider_control.pt"
    save_every: int = 10

    # ------------------------------------------------------------
    # Outcome shaping
    # ------------------------------------------------------------
    hit_bonus: float = 0.30
    great_bonus_extra: float = 0.10
    good_bonus_extra: float = 0.04
    miss_penalty: float = 0.12

    empty_click_penalty: float = 0.07
    far_click_penalty: float = 0.05
    off_window_click_penalty: float = 0.04

    # ------------------------------------------------------------
    # Phase 2: timing refinement
    # ------------------------------------------------------------
    timing_good_window_ms: float = 55.0
    timing_ok_window_ms: float = 105.0
    timing_focus_window_ms: float = 165.0
    timing_good_bonus: float = 0.030
    timing_ok_bonus: float = 0.012
    timing_near_miss_penalty: float = 0.012
    timing_early_penalty_scale: float = 0.00012
    timing_late_penalty_scale: float = 0.00012
    timing_off_window_penalty: float = 0.035

    # ------------------------------------------------------------
    # Approach shaping
    # ------------------------------------------------------------
    primary_approach_scale: float = 0.14
    secondary_approach_scale: float = 0.05
    approach_delta_norm_px: float = 42.0
    approach_clip_abs: float = 0.18

    approach_direction_bonus: float = 0.020
    approach_direction_wrong_penalty: float = 0.010

    purposeful_move_bonus: float = 0.008

    # ------------------------------------------------------------
    # Motion quality (ослаблено!)
    # ------------------------------------------------------------
    jerk_penalty_scale: float = 0.006
    jerk_deadzone: float = 0.22

    overspeed_penalty_scale: float = 0.006
    speed_soft_cap_urgent: float = 1.20
    speed_soft_cap_relaxed: float = 0.92

    # ------------------------------------------------------------
    # Idle / drift control
    # ------------------------------------------------------------
    urgent_time_window_ms: float = 240.0
    soon_time_window_ms: float = 420.0
    far_time_window_ms: float = 700.0

    urgent_idle_penalty: float = 0.008
    urgent_idle_threshold: float = 0.08

    useless_motion_penalty_scale: float = 0.008
    calm_bonus: float = 0.0015

    # ------------------------------------------------------------
    # Positioning / flow
    # ------------------------------------------------------------
    prehit_time_window_ms: float = 150.0
    prehit_distance_px: float = 56.0
    prehit_position_bonus: float = 0.020
    hold_near_target_bonus: float = 0.010
    prehit_stable_distance_px: float = 46.0
    prehit_settled_speed: float = 0.22
    prehit_flythrough_speed: float = 0.82
    prehit_flythrough_penalty: float = 0.012
    micro_stability_bonus: float = 0.006
    micro_jitter_penalty_scale: float = 0.010

    post_hit_flow_bonus: float = 0.060
    post_hit_bad_exit_penalty: float = 0.020
    post_hit_good_direction_bonus: float = 0.020
    post_hit_excellent_exit_bonus: float = 0.018
    post_hit_break_penalty: float = 0.018

    # ------------------------------------------------------------
    # Click discipline
    # ------------------------------------------------------------
    click_focus_time_window_ms: float = 160.0
    click_focus_distance_px: float = 72.0
    click_near_distance_px: float = 58.0
    click_far_distance_px: float = 110.0
    click_settled_speed: float = 0.36
    click_unstable_speed: float = 0.92
    near_click_bonus: float = 0.014
    settled_click_bonus: float = 0.012
    unstable_click_penalty: float = 0.018

    # ------------------------------------------------------------
    # Anti-recoil fine-tune
    # ------------------------------------------------------------
    recoil_window_steps: int = 6
    recoil_distance_penalty_scale: float = 0.003
    recoil_direction_penalty_scale: float = 0.006
    recoil_soft_distance_px: float = 44.0
    recoil_jerk_penalty_scale: float = 0.006
    recoil_good_exit_bonus: float = 0.010

    # ------------------------------------------------------------
    # Phase 3.5: post-hit motion smoothing
    # ------------------------------------------------------------
    recoil_hard_distance_px: float = 88.0
    recoil_bad_step_penalty: float = 0.020
    smooth_exit_bonus: float = 0.014
    smooth_hold_bonus: float = 0.004
    smooth_exit_min_speed: float = 0.08
    smooth_exit_max_speed: float = 0.72

    # ------------------------------------------------------------
    # Phase 5: slider control
    # ------------------------------------------------------------
    slider_follow_hold_bonus: float = 0.020
    slider_follow_close_bonus: float = 0.014
    slider_path_delta_scale: float = 0.060
    slider_path_negative_scale: float = 0.008
    slider_progress_scale: float = 0.035
    slider_acquire_bonus: float = 0.010
    slider_hold_click_bonus: float = 0.006
    slider_early_hold_bonus: float = 0.022
    slider_lost_follow_penalty: float = 0.006
    slider_escape_penalty: float = 0.004
    slider_jerk_penalty_scale: float = 0.002
    slider_click_release_penalty: float = 0.010
    slider_early_release_penalty: float = 0.018
    slider_post_head_hold_window_steps: int = 24
    slider_near_hold_bonus: float = 0.012
    slider_target_direction_bonus: float = 0.030
    slider_target_wrong_direction_penalty: float = 0.010
    slider_track_good_gain_threshold: float = 0.020
    slider_track_good_alignment: float = 0.35
    slider_stall_gain_threshold: float = 0.004
    slider_stall_speed_threshold: float = 0.10
    slider_far_hold_radius_mult: float = 2.6
    slider_far_hold_penalty: float = 0.012
    slider_stall_penalty: float = 0.010
    slider_wrong_dir_hold_penalty: float = 0.010
    slider_inside_sustain_bonus: float = 0.010
    slider_head_deemphasis_penalty: float = 0.080
    slider_tick_consistency_bonus: float = 0.045
    slider_finish_control_bonus: float = 0.280
    slider_drop_control_penalty: float = 0.035
    slider_long_chain_bonus: float = 0.018
    slider_tangent_direction_bonus: float = 0.022
    slider_tangent_wrong_penalty: float = 0.014
    slider_curve_control_bonus: float = 0.016
    slider_curve_loss_penalty: float = 0.012
    slider_reverse_window_steps: int = 18
    slider_reverse_detect_dot: float = -0.35
    slider_reverse_follow_bonus: float = 0.030
    slider_reverse_wrong_penalty: float = 0.018

@dataclass(slots=True)
class EpisodeStats:
    reward_total: float = 0.0
    env_reward_total: float = 0.0
    shaping_reward_total: float = 0.0

    hit_count: int = 0
    miss_count: int = 0
    useful_clicks: int = 0
    total_clicks: int = 0

    idle_steps: int = 0
    steps: int = 0

    jerk_penalty_total: float = 0.0
    overspeed_penalty_total: float = 0.0
    useless_motion_penalty_total: float = 0.0
    flow_reward_total: float = 0.0
    approach_reward_total: float = 0.0
    timing_bonus_total: float = 0.0
    timing_penalty_total: float = 0.0
    aim_reward_total: float = 0.0
    post_hit_exit_reward_total: float = 0.0
    smoothing_reward_total: float = 0.0
    recoil_distance_total_px: float = 0.0
    recoil_samples: int = 0
    recoil_bad_steps: int = 0
    smooth_exit_steps: int = 0
    post_hit_jerk_total: float = 0.0
    slider_reward_total: float = 0.0
    slider_head_hits: int = 0
    slider_drops: int = 0
    slider_finishes: int = 0
    slider_tick_hits: int = 0
    slider_tick_misses: int = 0
    slider_active_steps: int = 0
    slider_inside_steps: int = 0
    slider_follow_dist_total: float = 0.0
    slider_lost_follow_count: int = 0
    slider_follow_gain_total: float = 0.0
    slider_progress_gain_total: float = 0.0
    slider_click_hold_steps: int = 0
    slider_click_release_count: int = 0
    slider_click_released_steps: int = 0
    slider_post_head_steps: int = 0
    slider_geom_inside_steps: int = 0
    slider_time_to_first_inside_total: int = 0
    slider_time_to_first_inside_count: int = 0
    slider_time_to_first_inside_missed: int = 0
    slider_target_alignment_total: float = 0.0
    slider_target_alignment_samples: int = 0
    slider_post_head_segments: int = 0
    slider_head_to_hold_successes: int = 0
    slider_first_hold_delay_total: int = 0
    slider_first_hold_delay_count: int = 0
    slider_first_hold_delay_missed: int = 0
    slider_near_hold_steps: int = 0
    slider_near_released_steps: int = 0
    slider_track_good_steps: int = 0
    slider_track_bad_steps: int = 0
    slider_stall_steps: int = 0
    slider_wrong_dir_steps: int = 0
    slider_good_follow_chain_total: int = 0
    slider_good_follow_chain_count: int = 0
    slider_good_follow_chain_max: int = 0
    slider_progress_while_hold_total: float = 0.0
    slider_progress_while_inside_total: float = 0.0
    slider_dist_when_hold_total: float = 0.0
    slider_dist_when_hold_samples: int = 0
    slider_dist_when_inside_total: float = 0.0
    slider_dist_when_inside_samples: int = 0
    slider_full_control_segments: int = 0
    slider_partial_control_segments: int = 0
    slider_segment_quality_total: float = 0.0
    slider_segment_quality_count: int = 0
    slider_reverse_events: int = 0
    slider_reverse_follow_steps: int = 0
    slider_reverse_drop_steps: int = 0
    slider_curve_steps: int = 0
    slider_curve_good_steps: int = 0

    timing_errors_ms: list[float] = field(default_factory=list)
    click_distances_px: list[float] = field(default_factory=list)
    early_clicks: int = 0
    late_clicks: int = 0
    off_window_clicks: int = 0
    good_window_clicks: int = 0
    near_clicks: int = 0
    far_clicks: int = 0
    stable_prehit_steps: int = 0
    prehit_steps: int = 0
    post_hit_good_exits: int = 0
    post_hit_breaks: int = 0

    @property
    def hit_rate(self) -> float:
        denom = self.hit_count + self.miss_count
        return 0.0 if denom <= 0 else self.hit_count / denom

    @property
    def useful_click_ratio(self) -> float:
        return 0.0 if self.total_clicks <= 0 else self.useful_clicks / self.total_clicks

    @property
    def idle_ratio(self) -> float:
        return 0.0 if self.steps <= 0 else self.idle_steps / self.steps

    @property
    def timing_error_mean_ms(self) -> float:
        return 0.0 if not self.timing_errors_ms else float(np.mean([abs(v) for v in self.timing_errors_ms]))

    @property
    def timing_error_median_ms(self) -> float:
        return 0.0 if not self.timing_errors_ms else float(np.median([abs(v) for v in self.timing_errors_ms]))

    @property
    def good_timing_ratio(self) -> float:
        return 0.0 if self.total_clicks <= 0 else self.good_window_clicks / self.total_clicks

    @property
    def distance_at_click_mean_px(self) -> float:
        return 0.0 if not self.click_distances_px else float(np.mean(self.click_distances_px))

    @property
    def near_click_ratio(self) -> float:
        return 0.0 if self.total_clicks <= 0 else self.near_clicks / self.total_clicks

    @property
    def far_click_ratio(self) -> float:
        return 0.0 if self.total_clicks <= 0 else self.far_clicks / self.total_clicks

    @property
    def stable_prehit_ratio(self) -> float:
        return 0.0 if self.prehit_steps <= 0 else self.stable_prehit_steps / self.prehit_steps

    @property
    def post_hit_good_exit_ratio(self) -> float:
        denom = self.post_hit_good_exits + self.post_hit_breaks
        return 0.0 if denom <= 0 else self.post_hit_good_exits / denom

    @property
    def recoil_distance_mean_px(self) -> float:
        return 0.0 if self.recoil_samples <= 0 else self.recoil_distance_total_px / self.recoil_samples

    @property
    def bad_recoil_ratio(self) -> float:
        return 0.0 if self.recoil_samples <= 0 else self.recoil_bad_steps / self.recoil_samples

    @property
    def smooth_exit_ratio(self) -> float:
        return 0.0 if self.recoil_samples <= 0 else self.smooth_exit_steps / self.recoil_samples

    @property
    def post_hit_jerk_mean(self) -> float:
        return 0.0 if self.recoil_samples <= 0 else self.post_hit_jerk_total / self.recoil_samples

    @property
    def slider_inside_ratio(self) -> float:
        return 0.0 if self.slider_active_steps <= 0 else self.slider_inside_steps / self.slider_active_steps

    @property
    def slider_follow_distance_mean_px(self) -> float:
        return 0.0 if self.slider_active_steps <= 0 else self.slider_follow_dist_total / self.slider_active_steps

    @property
    def slider_finish_rate(self) -> float:
        denom = self.slider_finishes + self.slider_drops
        return 0.0 if denom <= 0 else self.slider_finishes / denom

    @property
    def slider_tick_hit_rate(self) -> float:
        denom = self.slider_tick_hits + self.slider_tick_misses
        return 0.0 if denom <= 0 else self.slider_tick_hits / denom

    @property
    def slider_post_head_hold_ratio(self) -> float:
        return 0.0 if self.slider_post_head_steps <= 0 else self.slider_click_hold_steps / self.slider_post_head_steps

    @property
    def slider_click_released_ratio(self) -> float:
        return 0.0 if self.slider_post_head_steps <= 0 else self.slider_click_released_steps / self.slider_post_head_steps

    @property
    def slider_geom_inside_ratio(self) -> float:
        return 0.0 if self.slider_active_steps <= 0 else self.slider_geom_inside_steps / self.slider_active_steps

    @property
    def slider_time_to_first_inside_mean(self) -> float:
        if self.slider_time_to_first_inside_count <= 0:
            return -1.0
        return self.slider_time_to_first_inside_total / self.slider_time_to_first_inside_count

    @property
    def slider_target_alignment_mean(self) -> float:
        if self.slider_target_alignment_samples <= 0:
            return 0.0
        return self.slider_target_alignment_total / self.slider_target_alignment_samples

    @property
    def slider_head_to_hold_success_rate(self) -> float:
        if self.slider_post_head_segments <= 0:
            return 0.0
        return self.slider_head_to_hold_successes / self.slider_post_head_segments

    @property
    def slider_release_after_head_ratio(self) -> float:
        if self.slider_post_head_steps <= 0:
            return 0.0
        return self.slider_click_release_count / self.slider_post_head_steps

    @property
    def slider_hold_steps_after_head_mean(self) -> float:
        if self.slider_post_head_segments <= 0:
            return 0.0
        return self.slider_click_hold_steps / self.slider_post_head_segments

    @property
    def slider_first_hold_delay_mean(self) -> float:
        if self.slider_first_hold_delay_count <= 0:
            return -1.0
        return self.slider_first_hold_delay_total / self.slider_first_hold_delay_count

    @property
    def slider_near_hold_ratio(self) -> float:
        denom = self.slider_near_hold_steps + self.slider_near_released_steps
        return 0.0 if denom <= 0 else self.slider_near_hold_steps / denom

    @property
    def slider_near_but_released_ratio(self) -> float:
        denom = self.slider_near_hold_steps + self.slider_near_released_steps
        return 0.0 if denom <= 0 else self.slider_near_released_steps / denom

    @property
    def slider_good_follow_chain_mean(self) -> float:
        if self.slider_good_follow_chain_count <= 0:
            return 0.0
        return self.slider_good_follow_chain_total / self.slider_good_follow_chain_count

    @property
    def slider_progress_while_hold(self) -> float:
        return self.slider_progress_while_hold_total

    @property
    def slider_progress_while_inside(self) -> float:
        return self.slider_progress_while_inside_total

    @property
    def slider_dist_when_hold_mean_px(self) -> float:
        if self.slider_dist_when_hold_samples <= 0:
            return 0.0
        return self.slider_dist_when_hold_total / self.slider_dist_when_hold_samples

    @property
    def slider_dist_when_inside_mean_px(self) -> float:
        if self.slider_dist_when_inside_samples <= 0:
            return 0.0
        return self.slider_dist_when_inside_total / self.slider_dist_when_inside_samples

    @property
    def slider_segment_quality_mean(self) -> float:
        if self.slider_segment_quality_count <= 0:
            return 0.0
        return self.slider_segment_quality_total / self.slider_segment_quality_count

    @property
    def slider_reverse_follow_ratio(self) -> float:
        denom = self.slider_reverse_follow_steps + self.slider_reverse_drop_steps
        return 0.0 if denom <= 0 else self.slider_reverse_follow_steps / denom

    @property
    def slider_curve_good_ratio(self) -> float:
        return 0.0 if self.slider_curve_steps <= 0 else self.slider_curve_good_steps / self.slider_curve_steps


@dataclass(slots=True)
class RewardBreakdown:
    total: float = 0.0
    approach: float = 0.0
    prehit: float = 0.0
    timing_bonus: float = 0.0
    timing_penalty: float = 0.0
    aim: float = 0.0
    flow: float = 0.0
    post_hit_exit: float = 0.0
    smoothing: float = 0.0
    click: float = 0.0
    outcome: float = 0.0
    calm: float = 0.0
    jerk_penalty: float = 0.0
    overspeed_penalty: float = 0.0
    idle_penalty: float = 0.0
    useless_motion_penalty: float = 0.0
    recoil_distance_px: float = 0.0
    recoil_sample: int = 0
    bad_recoil_step: int = 0
    smooth_exit_step: int = 0
    post_hit_jerk: float = 0.0
    slider: float = 0.0
    slider_follow_gain: float = 0.0
    slider_progress_gain: float = 0.0
    slider_lost_follow: int = 0
    slider_click_hold_step: int = 0
    slider_click_release_step: int = 0
    slider_target_alignment: float = 0.0
    slider_target_alignment_sample: int = 0
    slider_track_good_step: int = 0
    slider_track_bad_step: int = 0
    slider_stall_step: int = 0
    slider_wrong_dir_step: int = 0
    slider_progress_while_hold: float = 0.0
    slider_progress_while_inside: float = 0.0
    slider_dist_when_hold: float = 0.0
    slider_dist_when_inside: float = 0.0
    slider_hold_sample: int = 0
    slider_inside_sample: int = 0
    slider_reverse_event: int = 0
    slider_reverse_follow_step: int = 0
    slider_reverse_drop_step: int = 0
    slider_curve_step: int = 0
    slider_curve_good_step: int = 0


@dataclass(slots=True)
class MotionState:
    prev_dx: float = 0.0
    prev_dy: float = 0.0

    recoil_steps_left: int = 0
    recoil_anchor_x: float = 0.0
    recoil_anchor_y: float = 0.0
    slider_active_steps: int = 0
    slider_inside_chain: int = 0
    prev_slider_tangent_x: float = 0.0
    prev_slider_tangent_y: float = 0.0
    slider_reverse_steps_left: int = 0


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def obs_to_numpy(obs: OsuObservation) -> np.ndarray:
    values: list[float] = [
        obs.time_ms / 10000.0,
        obs.cursor_x / 512.0,
        obs.cursor_y / 384.0,
    ]

    for item in obs.upcoming:
        values.extend(
            [
                float(item.kind_id),
                item.x / 512.0,
                item.y / 384.0,
                item.time_to_hit_ms / 1000.0,
                item.distance_to_cursor / 512.0,
                item.is_active,
            ]
        )

    values.extend(
        [
            obs.slider.active_slider,
            obs.slider.primary_is_slider,
            obs.slider.progress,
            obs.slider.target_x / 512.0,
            obs.slider.target_y / 384.0,
            obs.slider.distance_to_target / 512.0,
            obs.slider.distance_to_ball / 512.0,
            obs.slider.inside_follow,
            obs.slider.head_hit,
            obs.slider.time_to_end_ms / 1000.0,
            obs.slider.tangent_x,
            obs.slider.tangent_y,
            obs.slider.follow_radius / 512.0,
        ]
    )

    return np.asarray(values, dtype=np.float32)


def build_env(cfg: TrainConfig) -> OsuEnv:
    beatmap = parse_beatmap(cfg.beatmap_path)
    env = OsuEnv(
        beatmap=beatmap,
        dt_ms=cfg.dt_ms,
        upcoming_count=cfg.upcoming_count,
        cursor_speed_scale=cfg.cursor_speed_scale,
        click_threshold=cfg.click_threshold,
        slider_hold_threshold=cfg.slider_hold_threshold,
    )
    return env


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def movement_magnitude(action: OsuAction) -> float:
    return math.hypot(action.dx, action.dy)


def find_circle_targets(obs: OsuObservation) -> tuple[UpcomingObjectView | None, UpcomingObjectView | None]:
    circles = [item for item in obs.upcoming if item.kind_id == 0]
    primary = circles[0] if len(circles) >= 1 else None
    secondary = circles[1] if len(circles) >= 2 else None
    return primary, secondary


def find_hit_targets(obs: OsuObservation) -> tuple[UpcomingObjectView | None, UpcomingObjectView | None]:
    targets = [item for item in obs.upcoming if item.kind_id in (0, 1)]
    primary = targets[0] if len(targets) >= 1 else None
    secondary = targets[1] if len(targets) >= 2 else None
    return primary, secondary


def normalized_vec_to_target(obs: OsuObservation, target: UpcomingObjectView | None) -> tuple[float, float]:
    if target is None:
        return 0.0, 0.0

    dx = target.x - obs.cursor_x
    dy = target.y - obs.cursor_y
    norm = math.hypot(dx, dy)
    if norm <= 1e-6:
        return 0.0, 0.0
    return dx / norm, dy / norm


def action_unit_vector(action: OsuAction) -> tuple[float, float]:
    norm = math.hypot(action.dx, action.dy)
    if norm <= 1e-6:
        return 0.0, 0.0
    return action.dx / norm, action.dy / norm


def compute_urgency(cfg: TrainConfig, target: UpcomingObjectView | None) -> float:
    if target is None:
        return 0.0

    t = abs(target.time_to_hit_ms)
    if t <= cfg.prehit_time_window_ms:
        return 1.0
    if t <= cfg.urgent_time_window_ms:
        return 0.88
    if t <= cfg.soon_time_window_ms:
        return 0.62
    if t <= cfg.far_time_window_ms:
        return 0.32
    return 0.12

def distance_xy(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)

def scaled_distance_delta(
    cfg: TrainConfig,
    prev_target: UpcomingObjectView | None,
    next_target: UpcomingObjectView | None,
) -> float:
    if prev_target is None or next_target is None:
        return 0.0

    delta = prev_target.distance_to_cursor - next_target.distance_to_cursor
    scaled = delta / cfg.approach_delta_norm_px
    return clamp(scaled, -cfg.approach_clip_abs, cfg.approach_clip_abs)


def timing_error_ms(target: UpcomingObjectView | None) -> float | None:
    if target is None:
        return None
    return target.time_to_hit_ms


def is_near_click(cfg: TrainConfig, target: UpcomingObjectView | None) -> bool:
    return target is not None and target.distance_to_cursor <= cfg.click_near_distance_px


def is_far_click(cfg: TrainConfig, target: UpcomingObjectView | None) -> bool:
    return target is None or target.distance_to_cursor >= cfg.click_far_distance_px


class ActorCritic(nn.Module):
    def __init__(self, obs_dim: int, hidden_dim: int = 256, action_dim: int = 3) -> None:
        super().__init__()

        self.backbone = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
        )

        self.actor_mean = nn.Linear(hidden_dim, action_dim)
        self.critic = nn.Linear(hidden_dim, 1)

        self.log_std = nn.Parameter(torch.full((action_dim,), -0.35))

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        features = self.backbone(obs)
        mean = self.actor_mean(features)
        value = self.critic(features).squeeze(-1)

        # Не даём std схлопнуться в мёртвую точку
        clamped_log_std = torch.clamp(self.log_std, min=-0.9, max=0.45)
        log_std = clamped_log_std.expand_as(mean)

        return mean, log_std, value

    def get_dist_and_value(self, obs: torch.Tensor) -> tuple[Normal, torch.Tensor]:
        mean, log_std, value = self.forward(obs)
        std = log_std.exp()
        dist = Normal(mean, std)
        return dist, value

    def sample_action(
        self,
        obs: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        dist, value = self.get_dist_and_value(obs)
        raw_action = dist.rsample()
        squashed = torch.tanh(raw_action)
        log_prob = dist.log_prob(raw_action).sum(dim=-1)
        return squashed, log_prob, value

    def deterministic_action(self, obs: torch.Tensor) -> torch.Tensor:
        mean, _, _ = self.forward(obs)
        return torch.tanh(mean)


class RolloutBuffer:
    def __init__(self) -> None:
        self.obs: list[np.ndarray] = []
        self.actions: list[np.ndarray] = []
        self.log_probs: list[float] = []
        self.rewards: list[float] = []
        self.values: list[float] = []
        self.dones: list[float] = []

    def add(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        log_prob: float,
        reward: float,
        value: float,
        done: bool,
    ) -> None:
        self.obs.append(obs)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.values.append(value)
        self.dones.append(float(done))

    def __len__(self) -> int:
        return len(self.obs)


def compute_gae(
    rewards: list[float],
    values: list[float],
    dones: list[float],
    gamma: float,
    gae_lambda: float,
) -> tuple[np.ndarray, np.ndarray]:
    advantages = np.zeros(len(rewards), dtype=np.float32)
    returns = np.zeros(len(rewards), dtype=np.float32)

    last_gae = 0.0
    next_value = 0.0

    for t in reversed(range(len(rewards))):
        mask = 1.0 - dones[t]
        delta = rewards[t] + gamma * next_value * mask - values[t]
        last_gae = delta + gamma * gae_lambda * mask * last_gae
        advantages[t] = last_gae
        returns[t] = advantages[t] + values[t]
        next_value = values[t]

    return advantages, returns


def phase23_shaping_reward(
    cfg: TrainConfig,
    prev_obs: OsuObservation,
    next_obs: OsuObservation,
    action: OsuAction,
    info: dict,
    just_pressed: bool,
    motion_state: MotionState,
) -> tuple[float, bool, RewardBreakdown]:
    breakdown = RewardBreakdown()
    useful_click = False

    prev_primary, prev_secondary = find_hit_targets(prev_obs)
    next_primary, next_secondary = find_hit_targets(next_obs)

    move_mag = movement_magnitude(action)
    urgency = compute_urgency(cfg, prev_primary)
    click_timing_error = timing_error_ms(prev_primary)
    click_abs_timing_error = abs(click_timing_error) if click_timing_error is not None else None
    judgement = str(info.get("judgement", "none"))

    # ---------------------------------------------------------
    # 1) Approach reward
    # ---------------------------------------------------------
    primary_delta = scaled_distance_delta(cfg, prev_primary, next_primary)
    secondary_delta = scaled_distance_delta(cfg, prev_secondary, next_secondary)

    breakdown.approach += primary_delta * cfg.primary_approach_scale * (0.75 + 0.65 * urgency)
    breakdown.approach += secondary_delta * cfg.secondary_approach_scale * 0.5

    if prev_primary is not None:
        target_dir_x, target_dir_y = normalized_vec_to_target(prev_obs, prev_primary)
        act_dir_x, act_dir_y = action_unit_vector(action)
        directional_alignment = target_dir_x * act_dir_x + target_dir_y * act_dir_y

        if move_mag > 0.05:
            breakdown.approach += max(0.0, directional_alignment) * cfg.approach_direction_bonus * urgency
            breakdown.approach -= max(0.0, -directional_alignment) * cfg.approach_direction_wrong_penalty * urgency

            if directional_alignment > 0.45 and urgency >= 0.35:
                breakdown.approach += cfg.purposeful_move_bonus

    # ---------------------------------------------------------
    # 2) Pre-hit positioning
    # ---------------------------------------------------------
    if prev_primary is not None:
        abs_t = abs(prev_primary.time_to_hit_ms)
        if abs_t <= cfg.prehit_time_window_ms:
            is_stable_near = (
                prev_primary.distance_to_cursor <= cfg.prehit_stable_distance_px
                and move_mag <= cfg.prehit_settled_speed
            )
            if is_stable_near:
                breakdown.prehit += cfg.micro_stability_bonus
            elif prev_primary.distance_to_cursor <= cfg.prehit_stable_distance_px and move_mag > cfg.prehit_flythrough_speed:
                breakdown.prehit -= cfg.prehit_flythrough_penalty

        if abs_t <= cfg.prehit_time_window_ms and prev_primary.distance_to_cursor <= cfg.prehit_distance_px:
            breakdown.prehit += cfg.prehit_position_bonus
            if move_mag <= cfg.prehit_settled_speed:
                breakdown.prehit += cfg.hold_near_target_bonus
            elif move_mag > cfg.prehit_flythrough_speed:
                breakdown.prehit -= cfg.prehit_flythrough_penalty

        if abs_t <= cfg.urgent_time_window_ms and prev_primary.distance_to_cursor <= cfg.click_near_distance_px:
            jitter = max(0.0, move_mag - cfg.click_settled_speed)
            breakdown.aim -= jitter * cfg.micro_jitter_penalty_scale

    # ---------------------------------------------------------
    # 3) Phase 2: timing refinement
    # ---------------------------------------------------------
    if just_pressed and click_timing_error is not None and click_abs_timing_error is not None:
        if click_abs_timing_error <= cfg.timing_good_window_ms:
            closeness = 1.0 - (click_abs_timing_error / max(1.0, cfg.timing_good_window_ms))
            breakdown.timing_bonus += cfg.timing_good_bonus * (0.35 + 0.65 * closeness)
        elif click_abs_timing_error <= cfg.timing_ok_window_ms:
            closeness = 1.0 - (
                (click_abs_timing_error - cfg.timing_good_window_ms)
                / max(1.0, cfg.timing_ok_window_ms - cfg.timing_good_window_ms)
            )
            closeness = max(0.0, closeness)
            breakdown.timing_bonus += cfg.timing_ok_bonus * closeness
            breakdown.timing_penalty -= cfg.timing_near_miss_penalty * (1.0 - closeness)
        elif click_abs_timing_error <= cfg.timing_focus_window_ms:
            normalized = (
                (click_abs_timing_error - cfg.timing_ok_window_ms)
                / max(1.0, cfg.timing_focus_window_ms - cfg.timing_ok_window_ms)
            )
            breakdown.timing_penalty -= cfg.timing_near_miss_penalty * (0.5 + 0.5 * normalized)
        else:
            breakdown.timing_penalty -= cfg.timing_off_window_penalty

        if click_timing_error > cfg.timing_good_window_ms:
            breakdown.timing_penalty -= min(
                0.035,
                (click_timing_error - cfg.timing_good_window_ms) * cfg.timing_early_penalty_scale,
            )
        elif click_timing_error < -cfg.timing_good_window_ms:
            breakdown.timing_penalty -= min(
                0.035,
                (abs(click_timing_error) - cfg.timing_good_window_ms) * cfg.timing_late_penalty_scale,
            )

    # ---------------------------------------------------------
    # 4) Outcome shaping
    # ---------------------------------------------------------
    score_value = int(info.get("score_value", 0))
    judgement = str(info.get("judgement", "none"))

    if score_value > 0:
        breakdown.outcome += cfg.hit_bonus
        useful_click = True

        if score_value >= 300:
            breakdown.outcome += cfg.great_bonus_extra
        elif score_value >= 100:
            breakdown.outcome += cfg.good_bonus_extra

    if judgement == "miss":
        breakdown.outcome -= cfg.miss_penalty

    # ---------------------------------------------------------
    # 5) Click discipline + Phase 3 aim stability
    # ---------------------------------------------------------
    if just_pressed:
        if prev_primary is None:
            breakdown.click -= cfg.empty_click_penalty
        else:
            if abs(prev_primary.time_to_hit_ms) > cfg.click_focus_time_window_ms:
                breakdown.click -= cfg.off_window_click_penalty

            if prev_primary.distance_to_cursor > cfg.click_focus_distance_px:
                breakdown.click -= cfg.far_click_penalty

            if (
                abs(prev_primary.time_to_hit_ms) <= cfg.click_focus_time_window_ms
                and prev_primary.distance_to_cursor <= cfg.click_focus_distance_px
            ):
                useful_click = useful_click or (score_value > 0)

            if prev_primary.distance_to_cursor <= cfg.click_near_distance_px:
                breakdown.aim += cfg.near_click_bonus
                if move_mag <= cfg.click_settled_speed:
                    breakdown.aim += cfg.settled_click_bonus
                elif move_mag >= cfg.click_unstable_speed:
                    breakdown.aim -= cfg.unstable_click_penalty
            elif prev_primary.distance_to_cursor >= cfg.click_far_distance_px:
                breakdown.aim -= cfg.far_click_penalty

    # ---------------------------------------------------------
    # 6) Anti-jerk penalty
    # ---------------------------------------------------------
    jerk = abs(action.dx - motion_state.prev_dx) + abs(action.dy - motion_state.prev_dy)
    jerk_excess = max(0.0, jerk - cfg.jerk_deadzone)
    breakdown.jerk_penalty -= jerk_excess * cfg.jerk_penalty_scale

    # ---------------------------------------------------------
    # 7) Overspeed penalty
    # ---------------------------------------------------------
    speed_soft_cap = cfg.speed_soft_cap_urgent if urgency >= 0.6 else cfg.speed_soft_cap_relaxed
    speed_excess = max(0.0, move_mag - speed_soft_cap)
    breakdown.overspeed_penalty -= speed_excess * cfg.overspeed_penalty_scale

    # ---------------------------------------------------------
    # 8) Idle vs useless motion
    # ---------------------------------------------------------
    if prev_primary is not None and abs(prev_primary.time_to_hit_ms) <= cfg.urgent_time_window_ms:
        if move_mag < cfg.urgent_idle_threshold and prev_primary.distance_to_cursor > 16.0:
            breakdown.idle_penalty -= cfg.urgent_idle_penalty
    else:
        if move_mag > 0.70:
            breakdown.useless_motion_penalty -= (move_mag - 0.70) * cfg.useless_motion_penalty_scale
        elif move_mag < 0.16:
            breakdown.calm += cfg.calm_bonus

    # ---------------------------------------------------------
    # 9) Post-hit flow and exit quality
    # ---------------------------------------------------------
    if score_value > 0 and next_obs.slider.active_slider <= 0.0:
        if next_primary is not None:
            if next_primary.distance_to_cursor <= 120.0:
                breakdown.flow += cfg.post_hit_flow_bonus
            elif next_primary.distance_to_cursor >= 210.0:
                breakdown.flow -= cfg.post_hit_bad_exit_penalty
                breakdown.post_hit_exit -= cfg.post_hit_break_penalty

            next_dir_x, next_dir_y = normalized_vec_to_target(next_obs, next_primary)
            act_dir_x, act_dir_y = action_unit_vector(action)
            post_hit_alignment = next_dir_x * act_dir_x + next_dir_y * act_dir_y

            if post_hit_alignment > 0.30:
                breakdown.flow += cfg.post_hit_good_direction_bonus
                if move_mag <= cfg.speed_soft_cap_urgent:
                    breakdown.post_hit_exit += cfg.post_hit_excellent_exit_bonus
            elif post_hit_alignment < -0.25:
                breakdown.flow -= cfg.post_hit_bad_exit_penalty * 0.5
                breakdown.post_hit_exit -= cfg.post_hit_break_penalty * 0.5

    # ---------------------------------------------------------
    # 10) Anti-recoil fine-tune
    # ---------------------------------------------------------
    if motion_state.recoil_steps_left > 0:
        # расстояние от точки недавнего попадания
        recoil_dist = distance_xy(
            next_obs.cursor_x,
            next_obs.cursor_y,
            motion_state.recoil_anchor_x,
            motion_state.recoil_anchor_y,
        )
        breakdown.recoil_distance_px = recoil_dist
        breakdown.recoil_sample = 1
        recoil_excess = max(0.0, recoil_dist - cfg.recoil_soft_distance_px)
        breakdown.smoothing -= recoil_excess * cfg.recoil_distance_penalty_scale

        # штраф за резкий импульс сразу после клика/хита
        recoil_jerk = abs(action.dx - motion_state.prev_dx) + abs(action.dy - motion_state.prev_dy)
        breakdown.post_hit_jerk = recoil_jerk
        breakdown.smoothing -= recoil_jerk * cfg.recoil_jerk_penalty_scale

        if recoil_dist <= cfg.recoil_soft_distance_px and move_mag <= cfg.smooth_exit_max_speed:
            breakdown.smoothing += cfg.smooth_hold_bonus

        if recoil_dist > cfg.recoil_hard_distance_px:
            breakdown.bad_recoil_step = 1
            breakdown.smoothing -= cfg.recoil_bad_step_penalty

        # штраф, если прямо летит от точки попадания
        away_x = next_obs.cursor_x - motion_state.recoil_anchor_x
        away_y = next_obs.cursor_y - motion_state.recoil_anchor_y
        away_norm = math.hypot(away_x, away_y)
        if away_norm > 1e-6 and move_mag > 1e-6:
            away_x /= away_norm
            away_y /= away_norm
            act_dir_x, act_dir_y = action_unit_vector(action)
            away_alignment = away_x * act_dir_x + away_y * act_dir_y
            if away_alignment > 0.55:
                breakdown.smoothing -= away_alignment * cfg.recoil_direction_penalty_scale

        # маленький бонус за мягкий выход в сторону следующей ноты
        if next_primary is not None:
            next_dir_x, next_dir_y = normalized_vec_to_target(next_obs, next_primary)
            act_dir_x, act_dir_y = action_unit_vector(action)
            exit_alignment = next_dir_x * act_dir_x + next_dir_y * act_dir_y
            smooth_speed = cfg.smooth_exit_min_speed <= move_mag <= cfg.smooth_exit_max_speed
            if 0.20 < exit_alignment < 0.90 and smooth_speed:
                breakdown.smooth_exit_step = 1
                breakdown.post_hit_exit += cfg.recoil_good_exit_bonus
                breakdown.smoothing += cfg.smooth_exit_bonus * exit_alignment

    # ---------------------------------------------------------
    # 11) Phase 5 slider control
    # ---------------------------------------------------------
    if judgement == "slider_head":
        breakdown.slider -= cfg.slider_head_deemphasis_penalty
    elif judgement == "slider_tick":
        chain_factor = min(1.0, motion_state.slider_inside_chain / 8.0)
        breakdown.slider += cfg.slider_tick_consistency_bonus * (0.65 + 0.35 * chain_factor)
    elif judgement == "slider_finish":
        chain_factor = min(1.0, motion_state.slider_inside_chain / 10.0)
        breakdown.slider += cfg.slider_finish_control_bonus * (0.55 + 0.45 * chain_factor)
    elif judgement == "slider_drop":
        breakdown.slider -= cfg.slider_drop_control_penalty

    if prev_obs.slider.active_slider > 0.5 and prev_obs.slider.head_hit > 0.5:
        step_scale = 1.0
        prev_dist = prev_obs.slider.distance_to_target
        next_dist = next_obs.slider.distance_to_target
        follow_radius = max(1.0, prev_obs.slider.follow_radius)
        geom_inside = prev_obs.slider.inside_follow > 0.5
        click_held = action.click_strength >= cfg.slider_hold_threshold
        inside = geom_inside and click_held
        active_step_idx = motion_state.slider_active_steps
        in_post_head_window = active_step_idx < cfg.slider_post_head_hold_window_steps
        near_follow = prev_dist <= follow_radius * 2.0
        far_hold = prev_dist > follow_radius * cfg.slider_far_hold_radius_mult
        target_alignment = 0.0
        has_alignment = False
        tangent_alignment = 0.0
        has_tangent_alignment = False
        tangent_dot = (
            prev_obs.slider.tangent_x * motion_state.prev_slider_tangent_x
            + prev_obs.slider.tangent_y * motion_state.prev_slider_tangent_y
        )
        curved_step = motion_state.slider_active_steps > 0 and tangent_dot < 0.92
        reverse_event = motion_state.slider_active_steps > 0 and tangent_dot < cfg.slider_reverse_detect_dot
        reverse_window = motion_state.slider_reverse_steps_left > 0 or reverse_event

        if curved_step:
            breakdown.slider_curve_step = 1
        if reverse_event:
            breakdown.slider_reverse_event = 1

        if click_held:
            breakdown.slider_click_hold_step = 1
            breakdown.slider_hold_sample = 1
            breakdown.slider_dist_when_hold = prev_dist
            breakdown.slider_progress_while_hold = max(0.0, next_obs.slider.progress - prev_obs.slider.progress)
            if in_post_head_window:
                breakdown.slider += cfg.slider_early_hold_bonus * (0.35 if far_hold else 1.0)
            if near_follow:
                near_closeness = 1.0 - min(1.0, prev_dist / (follow_radius * 2.0))
                breakdown.slider += cfg.slider_near_hold_bonus * near_closeness

        breakdown.slider_follow_gain = max(-1.0, min(1.0, (prev_dist - next_dist) / follow_radius))
        breakdown.slider_progress_gain = max(0.0, next_obs.slider.progress - prev_obs.slider.progress)

        if move_mag > 0.05:
            target_dx = prev_obs.slider.target_x - prev_obs.cursor_x
            target_dy = prev_obs.slider.target_y - prev_obs.cursor_y
            target_norm = math.hypot(target_dx, target_dy)
            if target_norm > 1e-6:
                target_dx /= target_norm
                target_dy /= target_norm
                act_dir_x, act_dir_y = action_unit_vector(action)
                target_alignment = target_dx * act_dir_x + target_dy * act_dir_y
                has_alignment = True
                breakdown.slider_target_alignment = target_alignment
                breakdown.slider_target_alignment_sample = 1
                if target_alignment > 0.0:
                    breakdown.slider += target_alignment * cfg.slider_target_direction_bonus
                else:
                    breakdown.slider += target_alignment * cfg.slider_target_wrong_direction_penalty

            tangent_norm = math.hypot(prev_obs.slider.tangent_x, prev_obs.slider.tangent_y)
            if tangent_norm > 1e-6:
                tangent_x = prev_obs.slider.tangent_x / tangent_norm
                tangent_y = prev_obs.slider.tangent_y / tangent_norm
                tangent_alignment = tangent_x * act_dir_x + tangent_y * act_dir_y
                has_tangent_alignment = True
                if click_held and near_follow:
                    if tangent_alignment > 0.0:
                        breakdown.slider += tangent_alignment * cfg.slider_tangent_direction_bonus
                    else:
                        breakdown.slider += tangent_alignment * cfg.slider_tangent_wrong_penalty

        if inside:
            closeness = max(0.0, 1.0 - prev_dist / follow_radius)
            breakdown.slider += cfg.slider_follow_hold_bonus * step_scale
            breakdown.slider += cfg.slider_follow_close_bonus * closeness * step_scale
            breakdown.slider += cfg.slider_inside_sustain_bonus * min(1.0, motion_state.slider_inside_chain / 6.0)
            breakdown.slider += cfg.slider_long_chain_bonus * min(1.0, motion_state.slider_inside_chain / 12.0)
            breakdown.slider_inside_sample = 1
            breakdown.slider_dist_when_inside = prev_dist
            breakdown.slider_progress_while_inside = breakdown.slider_progress_while_hold
            if curved_step:
                breakdown.slider_curve_good_step = 1
                breakdown.slider += cfg.slider_curve_control_bonus * min(1.0, motion_state.slider_inside_chain / 8.0)
            if reverse_window:
                breakdown.slider_reverse_follow_step = 1
                breakdown.slider += cfg.slider_reverse_follow_bonus * (0.5 + 0.5 * closeness)
        else:
            if breakdown.slider_follow_gain > 0.0:
                breakdown.slider += breakdown.slider_follow_gain * cfg.slider_path_delta_scale
            elif prev_dist > follow_radius * 3.0:
                breakdown.slider += breakdown.slider_follow_gain * cfg.slider_path_negative_scale

            if near_follow:
                proximity = 1.0 - min(1.0, prev_dist / (follow_radius * 2.0))
                breakdown.slider += cfg.slider_acquire_bonus * proximity

            if click_held:
                breakdown.slider += cfg.slider_hold_click_bonus
                good_tracking = (
                    breakdown.slider_follow_gain >= cfg.slider_track_good_gain_threshold
                    or (has_alignment and target_alignment >= cfg.slider_track_good_alignment)
                )
                bad_tracking = (
                    far_hold
                    and breakdown.slider_follow_gain <= cfg.slider_stall_gain_threshold
                    and (not has_alignment or target_alignment < 0.15)
                )
                stalled = move_mag <= cfg.slider_stall_speed_threshold and not near_follow
                wrong_dir = has_alignment and target_alignment < -0.20
                tangent_wrong = has_tangent_alignment and tangent_alignment < -0.30 and near_follow

                if good_tracking:
                    breakdown.slider_track_good_step = 1
                    distance_weight = min(1.0, prev_dist / max(1.0, follow_radius * 3.0))
                    breakdown.slider += 0.010 + cfg.slider_path_delta_scale * max(0.0, breakdown.slider_follow_gain) * distance_weight
                if bad_tracking:
                    breakdown.slider_track_bad_step = 1
                    breakdown.slider -= cfg.slider_far_hold_penalty
                if stalled:
                    breakdown.slider_stall_step = 1
                    breakdown.slider -= cfg.slider_stall_penalty
                if wrong_dir:
                    breakdown.slider_wrong_dir_step = 1
                    breakdown.slider -= cfg.slider_wrong_dir_hold_penalty * min(1.0, -target_alignment)
                if tangent_wrong:
                    breakdown.slider_wrong_dir_step = 1
                    breakdown.slider -= cfg.slider_tangent_wrong_penalty * min(1.0, -tangent_alignment)
                if curved_step and (bad_tracking or tangent_wrong or not click_held):
                    breakdown.slider -= cfg.slider_curve_loss_penalty
                if reverse_window and (bad_tracking or tangent_wrong or not near_follow):
                    breakdown.slider_reverse_drop_step = 1
                    breakdown.slider -= cfg.slider_reverse_wrong_penalty
            else:
                breakdown.slider -= cfg.slider_click_release_penalty
                breakdown.slider_click_release_step = 1
                if in_post_head_window:
                    breakdown.slider -= cfg.slider_early_release_penalty
                if reverse_window:
                    breakdown.slider_reverse_drop_step = 1
                    breakdown.slider -= cfg.slider_reverse_wrong_penalty

            if geom_inside:
                breakdown.slider_lost_follow = 1
                breakdown.slider -= cfg.slider_lost_follow_penalty * step_scale

        breakdown.slider += min(0.035, breakdown.slider_progress_gain * cfg.slider_progress_scale)

        jerk = abs(action.dx - motion_state.prev_dx) + abs(action.dy - motion_state.prev_dy)
        breakdown.slider -= max(0.0, jerk - cfg.jerk_deadzone) * cfg.slider_jerk_penalty_scale

        if prev_dist > follow_radius * 3.0:
            breakdown.slider -= cfg.slider_escape_penalty

    breakdown.total = (
        breakdown.approach
        + breakdown.prehit
        + breakdown.timing_bonus
        + breakdown.timing_penalty
        + breakdown.aim
        + breakdown.flow
        + breakdown.post_hit_exit
        + breakdown.smoothing
        + breakdown.click
        + breakdown.outcome
        + breakdown.calm
        + breakdown.jerk_penalty
        + breakdown.overspeed_penalty
        + breakdown.idle_penalty
        + breakdown.useless_motion_penalty
        + breakdown.slider
    )

    return breakdown.total, useful_click, breakdown


def ppo_update(
    cfg: TrainConfig,
    model: ActorCritic,
    optimizer: optim.Optimizer,
    buffer: RolloutBuffer,
    device: torch.device,
) -> dict:
    advantages_np, returns_np = compute_gae(
        rewards=buffer.rewards,
        values=buffer.values,
        dones=buffer.dones,
        gamma=cfg.gamma,
        gae_lambda=cfg.gae_lambda,
    )

    advantages_np = (advantages_np - advantages_np.mean()) / (advantages_np.std() + 1e-8)

    obs_t = torch.tensor(np.asarray(buffer.obs), dtype=torch.float32, device=device)
    actions_t = torch.tensor(np.asarray(buffer.actions), dtype=torch.float32, device=device)
    old_log_probs_t = torch.tensor(np.asarray(buffer.log_probs), dtype=torch.float32, device=device)
    returns_t = torch.tensor(returns_np, dtype=torch.float32, device=device)
    advantages_t = torch.tensor(advantages_np, dtype=torch.float32, device=device)

    batch_size = obs_t.size(0)
    indices = np.arange(batch_size)

    policy_losses: list[float] = []
    value_losses: list[float] = []
    entropies: list[float] = []
    kls: list[float] = []

    for _ in range(cfg.epochs_per_update):
        np.random.shuffle(indices)

        for start in range(0, batch_size, cfg.minibatch_size):
            end = start + cfg.minibatch_size
            mb_idx = indices[start:end]

            mb_obs = obs_t[mb_idx]
            mb_actions = actions_t[mb_idx]
            mb_old_log_probs = old_log_probs_t[mb_idx]
            mb_returns = returns_t[mb_idx]
            mb_advantages = advantages_t[mb_idx]

            dist, values = model.get_dist_and_value(mb_obs)

            clipped = torch.clamp(mb_actions, -0.999, 0.999)
            raw_actions = 0.5 * torch.log((1.0 + clipped) / (1.0 - clipped))

            log_probs = dist.log_prob(raw_actions).sum(dim=-1)
            entropy = dist.entropy().sum(dim=-1).mean()

            ratio = torch.exp(log_probs - mb_old_log_probs)
            surr1 = ratio * mb_advantages
            surr2 = torch.clamp(ratio, 1.0 - cfg.clip_ratio, 1.0 + cfg.clip_ratio) * mb_advantages
            policy_loss = -torch.min(surr1, surr2).mean()

            value_loss = ((values - mb_returns) ** 2).mean()

            loss = policy_loss + cfg.value_coef * value_loss - cfg.entropy_coef * entropy

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            approx_kl = (mb_old_log_probs - log_probs).mean().item()

            policy_losses.append(float(policy_loss.item()))
            value_losses.append(float(value_loss.item()))
            entropies.append(float(entropy.item()))
            kls.append(float(approx_kl))

    return {
        "policy_loss": float(np.mean(policy_losses)) if policy_losses else 0.0,
        "value_loss": float(np.mean(value_losses)) if value_losses else 0.0,
        "entropy": float(np.mean(entropies)) if entropies else 0.0,
        "kl": float(np.mean(kls)) if kls else 0.0,
    }


def run_episode(
    cfg: TrainConfig,
    env: OsuEnv,
    model: ActorCritic,
    device: torch.device,
    buffer: RolloutBuffer,
) -> EpisodeStats:
    stats = EpisodeStats()

    obs = env.reset()
    prev_click_down = False
    prev_raw_click_down = False
    motion_state = MotionState()
    prev_slider_active = False
    slider_segment_steps = 0
    slider_first_inside_step: int | None = None
    slider_segment_had_hold = False
    slider_first_hold_step: int | None = None
    slider_good_follow_chain = 0
    slider_segment_inside_steps = 0
    slider_segment_best_chain = 0
    slider_segment_finished = False

    while not env.done:
        obs_np = obs_to_numpy(obs)
        obs_t = torch.tensor(obs_np, dtype=torch.float32, device=device).unsqueeze(0)

        with torch.no_grad():
            action_t, log_prob_t, value_t = model.sample_action(obs_t)

        action_np = action_t.squeeze(0).cpu().numpy()

        osu_action = OsuAction(
            dx=float(action_np[0]),
            dy=float(action_np[1]),
            click_strength=float((action_np[2] + 1.0) * 0.5),
        )

        raw_click_down = osu_action.click_strength >= env.click_threshold
        slider_hold_down = obs.slider.active_slider > 0.5 and osu_action.click_strength >= env.slider_hold_threshold
        click_down = raw_click_down or slider_hold_down
        just_pressed = raw_click_down and not prev_raw_click_down
        prev_primary, _ = find_hit_targets(obs)
        click_timing_error = timing_error_ms(prev_primary)

        step = env.step(osu_action)
        next_obs = step.observation

        shaping_reward, useful_click, breakdown = phase23_shaping_reward(
            cfg=cfg,
            prev_obs=obs,
            next_obs=next_obs,
            action=osu_action,
            info=step.info,
            just_pressed=just_pressed,
            motion_state=motion_state,
        )

        total_reward = step.reward + shaping_reward

        buffer.add(
            obs=obs_np,
            action=action_np,
            log_prob=float(log_prob_t.item()),
            reward=float(total_reward),
            value=float(value_t.item()),
            done=step.done,
        )

        stats.reward_total += total_reward
        stats.env_reward_total += step.reward
        stats.shaping_reward_total += shaping_reward
        stats.steps += 1

        stats.jerk_penalty_total += -breakdown.jerk_penalty
        stats.overspeed_penalty_total += -breakdown.overspeed_penalty
        stats.useless_motion_penalty_total += -breakdown.useless_motion_penalty
        stats.flow_reward_total += breakdown.flow
        stats.approach_reward_total += breakdown.approach
        stats.timing_bonus_total += breakdown.timing_bonus
        stats.timing_penalty_total += -breakdown.timing_penalty
        stats.aim_reward_total += breakdown.aim
        stats.post_hit_exit_reward_total += breakdown.post_hit_exit
        stats.smoothing_reward_total += breakdown.smoothing
        stats.recoil_distance_total_px += breakdown.recoil_distance_px
        stats.recoil_samples += breakdown.recoil_sample
        stats.recoil_bad_steps += breakdown.bad_recoil_step
        stats.smooth_exit_steps += breakdown.smooth_exit_step
        stats.post_hit_jerk_total += breakdown.post_hit_jerk
        stats.slider_reward_total += breakdown.slider
        stats.slider_follow_gain_total += breakdown.slider_follow_gain
        stats.slider_progress_gain_total += breakdown.slider_progress_gain
        stats.slider_lost_follow_count += breakdown.slider_lost_follow
        stats.slider_click_hold_steps += breakdown.slider_click_hold_step
        stats.slider_click_released_steps += breakdown.slider_click_release_step
        stats.slider_target_alignment_total += breakdown.slider_target_alignment
        stats.slider_target_alignment_samples += breakdown.slider_target_alignment_sample
        stats.slider_track_good_steps += breakdown.slider_track_good_step
        stats.slider_track_bad_steps += breakdown.slider_track_bad_step
        stats.slider_stall_steps += breakdown.slider_stall_step
        stats.slider_wrong_dir_steps += breakdown.slider_wrong_dir_step
        stats.slider_progress_while_hold_total += breakdown.slider_progress_while_hold
        stats.slider_progress_while_inside_total += breakdown.slider_progress_while_inside
        stats.slider_reverse_events += breakdown.slider_reverse_event
        stats.slider_reverse_follow_steps += breakdown.slider_reverse_follow_step
        stats.slider_reverse_drop_steps += breakdown.slider_reverse_drop_step
        stats.slider_curve_steps += breakdown.slider_curve_step
        stats.slider_curve_good_steps += breakdown.slider_curve_good_step
        if breakdown.slider_hold_sample:
            stats.slider_dist_when_hold_total += breakdown.slider_dist_when_hold
            stats.slider_dist_when_hold_samples += 1
        if breakdown.slider_inside_sample:
            stats.slider_dist_when_inside_total += breakdown.slider_dist_when_inside
            stats.slider_dist_when_inside_samples += 1

        if obs.slider.active_slider > 0.5:
            if not prev_slider_active:
                slider_segment_steps = 0
                slider_first_inside_step = None
                slider_segment_had_hold = False
                slider_first_hold_step = None
                slider_good_follow_chain = 0
                slider_segment_inside_steps = 0
                slider_segment_best_chain = 0
                slider_segment_finished = False
            stats.slider_active_steps += 1
            stats.slider_post_head_steps += 1
            stats.slider_follow_dist_total += obs.slider.distance_to_target
            near_follow = obs.slider.distance_to_target <= max(1.0, obs.slider.follow_radius) * 2.0
            if obs.slider.inside_follow > 0.5:
                stats.slider_geom_inside_steps += 1
                if slider_first_inside_step is None:
                    slider_first_inside_step = slider_segment_steps
            if obs.slider.inside_follow > 0.5 and click_down:
                stats.slider_inside_steps += 1
                slider_segment_inside_steps += 1
                slider_good_follow_chain += 1
                slider_segment_best_chain = max(slider_segment_best_chain, slider_good_follow_chain)
                stats.slider_good_follow_chain_max = max(stats.slider_good_follow_chain_max, slider_good_follow_chain)
            else:
                if slider_good_follow_chain > 0:
                    stats.slider_good_follow_chain_total += slider_good_follow_chain
                    stats.slider_good_follow_chain_count += 1
                slider_good_follow_chain = 0
            if near_follow and click_down:
                stats.slider_near_hold_steps += 1
            elif near_follow:
                stats.slider_near_released_steps += 1
            if click_down:
                slider_segment_had_hold = True
                if slider_first_hold_step is None:
                    slider_first_hold_step = slider_segment_steps
            if prev_click_down and not click_down:
                stats.slider_click_release_count += 1
            slider_segment_steps += 1
        elif prev_slider_active:
            stats.slider_post_head_segments += 1
            if slider_segment_steps > 0:
                segment_quality = slider_segment_inside_steps / slider_segment_steps
                stats.slider_segment_quality_total += segment_quality
                stats.slider_segment_quality_count += 1
                if slider_segment_finished and segment_quality >= 0.55:
                    stats.slider_full_control_segments += 1
                elif slider_segment_inside_steps > 0 or slider_segment_finished:
                    stats.slider_partial_control_segments += 1
            if slider_good_follow_chain > 0:
                stats.slider_good_follow_chain_total += slider_good_follow_chain
                stats.slider_good_follow_chain_count += 1
                slider_good_follow_chain = 0
            if slider_segment_had_hold:
                stats.slider_head_to_hold_successes += 1
            if slider_first_hold_step is None:
                stats.slider_first_hold_delay_missed += 1
            else:
                stats.slider_first_hold_delay_total += slider_first_hold_step
                stats.slider_first_hold_delay_count += 1
            if slider_first_inside_step is None:
                stats.slider_time_to_first_inside_missed += 1
            else:
                stats.slider_time_to_first_inside_total += slider_first_inside_step
                stats.slider_time_to_first_inside_count += 1

        if prev_primary is not None and abs(prev_primary.time_to_hit_ms) <= cfg.prehit_time_window_ms:
            stats.prehit_steps += 1
            if (
                prev_primary.distance_to_cursor <= cfg.prehit_stable_distance_px
                and movement_magnitude(osu_action) <= cfg.prehit_settled_speed
            ):
                stats.stable_prehit_steps += 1

        if just_pressed:
            stats.total_clicks += 1
            if click_timing_error is not None:
                abs_timing_error = abs(click_timing_error)
                stats.timing_errors_ms.append(click_timing_error)
                if click_timing_error > cfg.timing_good_window_ms:
                    stats.early_clicks += 1
                elif click_timing_error < -cfg.timing_good_window_ms:
                    stats.late_clicks += 1
                if abs_timing_error > cfg.timing_focus_window_ms:
                    stats.off_window_clicks += 1
                if abs_timing_error <= cfg.timing_good_window_ms:
                    stats.good_window_clicks += 1

            if prev_primary is not None:
                stats.click_distances_px.append(prev_primary.distance_to_cursor)
                if prev_primary.distance_to_cursor <= cfg.click_near_distance_px:
                    stats.near_clicks += 1
                elif prev_primary.distance_to_cursor >= cfg.click_far_distance_px:
                    stats.far_clicks += 1

        if useful_click:
            stats.useful_clicks += 1

        if step.info.get("score_value", 0) > 0:
            stats.hit_count += 1
            if breakdown.post_hit_exit >= 0.0:
                stats.post_hit_good_exits += 1
            else:
                stats.post_hit_breaks += 1
        if step.info.get("judgement") == "miss":
            stats.miss_count += 1

        judgement = str(step.info.get("judgement", "none"))
        if judgement == "slider_head":
            stats.slider_head_hits += 1
        elif judgement == "slider_drop":
            stats.slider_drops += 1
        elif judgement == "slider_finish":
            stats.slider_finishes += 1
            slider_segment_finished = True
        elif judgement == "slider_tick":
            stats.slider_tick_hits += 1
        elif judgement == "slider_tick_miss":
            stats.slider_tick_misses += 1

        if movement_magnitude(osu_action) < cfg.urgent_idle_threshold:
            stats.idle_steps += 1

        # если был успешный скоринг — открываем короткое окно anti-recoil
        if step.info.get("score_value", 0) > 0 and not str(step.info.get("judgement", "")).startswith("slider_"):
            motion_state.recoil_steps_left = cfg.recoil_window_steps
            motion_state.recoil_anchor_x = next_obs.cursor_x
            motion_state.recoil_anchor_y = next_obs.cursor_y
        elif motion_state.recoil_steps_left > 0:
            motion_state.recoil_steps_left -= 1

        motion_state.prev_dx = osu_action.dx
        motion_state.prev_dy = osu_action.dy
        if next_obs.slider.active_slider > 0.5:
            motion_state.slider_active_steps = motion_state.slider_active_steps + 1 if obs.slider.active_slider > 0.5 else 0
            motion_state.slider_inside_chain = slider_good_follow_chain
            motion_state.prev_slider_tangent_x = next_obs.slider.tangent_x
            motion_state.prev_slider_tangent_y = next_obs.slider.tangent_y
            if breakdown.slider_reverse_event:
                motion_state.slider_reverse_steps_left = cfg.slider_reverse_window_steps
            elif motion_state.slider_reverse_steps_left > 0:
                motion_state.slider_reverse_steps_left -= 1
        else:
            motion_state.slider_active_steps = 0
            motion_state.slider_inside_chain = 0
            motion_state.prev_slider_tangent_x = 0.0
            motion_state.prev_slider_tangent_y = 0.0
            motion_state.slider_reverse_steps_left = 0

        prev_click_down = click_down
        prev_raw_click_down = raw_click_down
        prev_slider_active = obs.slider.active_slider > 0.5
        obs = next_obs

    if prev_slider_active:
        stats.slider_post_head_segments += 1
        if slider_segment_steps > 0:
            segment_quality = slider_segment_inside_steps / slider_segment_steps
            stats.slider_segment_quality_total += segment_quality
            stats.slider_segment_quality_count += 1
            if slider_segment_finished and segment_quality >= 0.55:
                stats.slider_full_control_segments += 1
            elif slider_segment_inside_steps > 0 or slider_segment_finished:
                stats.slider_partial_control_segments += 1
        if slider_good_follow_chain > 0:
            stats.slider_good_follow_chain_total += slider_good_follow_chain
            stats.slider_good_follow_chain_count += 1
        if slider_segment_had_hold:
            stats.slider_head_to_hold_successes += 1
        if slider_first_hold_step is None:
            stats.slider_first_hold_delay_missed += 1
        else:
            stats.slider_first_hold_delay_total += slider_first_hold_step
            stats.slider_first_hold_delay_count += 1
        if slider_first_inside_step is None:
            stats.slider_time_to_first_inside_missed += 1
        else:
            stats.slider_time_to_first_inside_total += slider_first_inside_step
            stats.slider_time_to_first_inside_count += 1

    return stats


def save_checkpoint(
    model: ActorCritic,
    optimizer: optim.Optimizer,
    cfg: TrainConfig,
    path: Path,
    update_idx: int,
    best_reward: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "update_idx": update_idx,
            "best_reward": best_reward,
            "config": asdict(cfg),
        },
        path,
    )


def maybe_load_checkpoint(
    model: ActorCritic,
    optimizer: optim.Optimizer,
    path: Path,
    device: torch.device,
    reset_training_state: bool = False,
) -> tuple[int, float]:
    if not path.exists():
        return 0, -1e18

    payload = torch.load(path, map_location=device)
    loaded_state = payload["model_state_dict"]
    model_state = model.state_dict()
    compatible_state = {}
    partial_keys: list[str] = []

    for key, value in loaded_state.items():
        if key not in model_state:
            continue
        if model_state[key].shape == value.shape:
            compatible_state[key] = value
            continue
        if key == "backbone.0.weight" and value.ndim == 2 and model_state[key].ndim == 2:
            expanded = model_state[key].clone()
            shared_cols = min(expanded.shape[1], value.shape[1])
            shared_rows = min(expanded.shape[0], value.shape[0])
            expanded[:shared_rows, :shared_cols] = value[:shared_rows, :shared_cols]
            compatible_state[key] = expanded
            partial_keys.append(key)

    model_state.update(compatible_state)
    model.load_state_dict(model_state)
    if partial_keys:
        print(f"[partial checkpoint load] expanded keys: {', '.join(partial_keys)}")

    if "optimizer_state_dict" in payload and not partial_keys:
        optimizer.load_state_dict(payload["optimizer_state_dict"])
    update_idx = int(payload.get("update_idx", 0))
    best_reward = float(payload.get("best_reward", -1e18))
    print(f"LOADED CHECKPOINT: {path}")
    if reset_training_state:
        return 0, -1e18
    return update_idx, best_reward


def ensure_run_dirs(cfg: TrainConfig) -> None:
    for path in (
        cfg.run_dir,
        cfg.checkpoint_dir,
        cfg.logs_dir,
        cfg.metrics_dir,
        cfg.replays_dir,
        cfg.eval_dir,
    ):
        Path(path).mkdir(parents=True, exist_ok=True)


def main() -> None:
    cfg = TrainConfig()
    set_seed(cfg.seed)
    ensure_run_dirs(cfg)

    device = torch.device(cfg.device)
    env = build_env(cfg)

    obs_dim = len(obs_to_numpy(env.reset()))
    model = ActorCritic(obs_dim=obs_dim, hidden_dim=cfg.hidden_dim).to(device)
    optimizer = optim.Adam(model.parameters(), lr=cfg.learning_rate)

    ckpt_dir = Path(cfg.checkpoint_dir)

    # старые базовые чекпоинты, от которых стартуем
    # новые recoil-чекпоинты, в которые сохраняем fine-tune
    latest_ckpt = ckpt_dir / cfg.latest_ckpt_name
    best_ckpt = ckpt_dir / cfg.best_ckpt_name

    source_ckpt = Path(cfg.source_checkpoint_path)
    if not source_ckpt.exists():
        raise FileNotFoundError(
            f"Phase 5 slider control fine-tuning requires source checkpoint: {source_ckpt}"
        )

    start_update, best_reward = maybe_load_checkpoint(
        model,
        optimizer,
        source_ckpt,
        device,
        reset_training_state=True,
    )

    # для fine-tune лучше не тащить старый абсолютный рекорд,
    # а начать свою отдельную "лучшую" линию

    print("=" * 100)
    print("PHASE 5 SLIDER CONTROL FINE-TUNING STARTED")
    print(f"Phase: {cfg.phase_name}")
    print(f"Map: {env.beatmap.artist} - {env.beatmap.title} [{env.beatmap.version}]")
    print(f"Source checkpoint: {source_ckpt}")
    print(f"Run dir: {Path(cfg.run_dir)}")
    print(f"Save latest: {latest_ckpt}")
    print(f"Save best: {best_ckpt}")
    print(f"Observation dim: {obs_dim}")
    print("Action dim: 3")
    print(f"Objects: {len(env.beatmap.hit_objects)}")
    print(f"Device: {device}")
    print("=" * 100)

    for update_idx in range(start_update + 1, cfg.updates + 1):
        buffer = RolloutBuffer()
        stats = run_episode(cfg, env, model, device, buffer)

        train_metrics = ppo_update(cfg, model, optimizer, buffer, device)

        if stats.reward_total > best_reward:
            best_reward = stats.reward_total
            save_checkpoint(
                model=model,
                optimizer=optimizer,
                cfg=cfg,
                path=best_ckpt,
                update_idx=update_idx,
                best_reward=best_reward,
            )
            print(f"[best saved] {best_ckpt}")

        if update_idx % cfg.save_every == 0 or update_idx == 1:
            save_checkpoint(
                model=model,
                optimizer=optimizer,
                cfg=cfg,
                path=latest_ckpt,
                update_idx=update_idx,
                best_reward=best_reward,
            )

        print(
            f"[update {update_idx:04d}] "
            f"reward={stats.reward_total:8.3f} "
            f"env={stats.env_reward_total:8.3f} "
            f"shape={stats.shaping_reward_total:8.3f} "
            f"hit_rate={stats.hit_rate:.3f} "
            f"clicks={stats.total_clicks:4d} "
            f"useful={stats.useful_click_ratio:.3f} "
            f"tmean={stats.timing_error_mean_ms:5.1f} "
            f"tmed={stats.timing_error_median_ms:5.1f} "
            f"good_t={stats.good_timing_ratio:.3f} "
            f"early={stats.early_clicks:3d} "
            f"late={stats.late_clicks:3d} "
            f"off={stats.off_window_clicks:3d} "
            f"dclick={stats.distance_at_click_mean_px:6.1f} "
            f"near={stats.near_click_ratio:.3f} "
            f"far={stats.far_click_ratio:.3f} "
            f"stable={stats.stable_prehit_ratio:.3f} "
            f"exit={stats.post_hit_good_exit_ratio:.3f} "
            f"idle={stats.idle_ratio:.3f} "
            f"hits={stats.hit_count:3d} "
            f"miss={stats.miss_count:3d} "
            f"approach={stats.approach_reward_total:7.3f} "
            f"time+={stats.timing_bonus_total:7.3f} "
            f"time-={stats.timing_penalty_total:7.3f} "
            f"aim={stats.aim_reward_total:7.3f} "
            f"flow={stats.flow_reward_total:7.3f} "
            f"exit_r={stats.post_hit_exit_reward_total:7.3f} "
            f"smooth_r={stats.smoothing_reward_total:7.3f} "
            f"slider_r={stats.slider_reward_total:7.3f} "
            f"sl_head={stats.slider_head_hits:3d} "
            f"sl_follow={stats.slider_inside_ratio:.3f} "
            f"sl_drop={stats.slider_drops:3d} "
            f"sl_fin={stats.slider_finishes:3d} "
            f"sl_tick={stats.slider_tick_hit_rate:.3f} "
            f"sl_dpx={stats.slider_follow_distance_mean_px:5.1f} "
            f"sl_active_steps={stats.slider_active_steps:4d} "
            f"sl_inside_ratio={stats.slider_inside_ratio:.3f} "
            f"sl_follow_dist_mean={stats.slider_follow_distance_mean_px:5.1f} "
            f"sl_follow_gain={stats.slider_follow_gain_total:6.3f} "
            f"sl_progress_gain={stats.slider_progress_gain_total:6.3f} "
            f"sl_lost_follow_count={stats.slider_lost_follow_count:3d} "
            f"sl_finish_rate={stats.slider_finish_rate:.3f} "
            f"sl_tick_hit_rate={stats.slider_tick_hit_rate:.3f} "
            f"sl_click_hold_steps={stats.slider_click_hold_steps:4d} "
            f"sl_click_release_count={stats.slider_click_release_count:3d} "
            f"sl_post_head_hold_ratio={stats.slider_post_head_hold_ratio:.3f} "
            f"sl_click_released_ratio={stats.slider_click_released_ratio:.3f} "
            f"sl_head_to_hold={stats.slider_head_to_hold_success_rate:.3f} "
            f"sl_release_after_head={stats.slider_release_after_head_ratio:.3f} "
            f"sl_hold_steps_mean={stats.slider_hold_steps_after_head_mean:5.1f} "
            f"sl_first_hold_delay={stats.slider_first_hold_delay_mean:5.1f} "
            f"sl_near_hold_ratio={stats.slider_near_hold_ratio:.3f} "
            f"sl_near_released_ratio={stats.slider_near_but_released_ratio:.3f} "
            f"sl_track_good={stats.slider_track_good_steps:4d} "
            f"sl_track_bad={stats.slider_track_bad_steps:4d} "
            f"sl_stall={stats.slider_stall_steps:4d} "
            f"sl_wrong_dir={stats.slider_wrong_dir_steps:4d} "
            f"sl_chain_mean={stats.slider_good_follow_chain_mean:4.1f} "
            f"sl_chain_max={stats.slider_good_follow_chain_max:3d} "
            f"sl_prog_hold={stats.slider_progress_while_hold:.3f} "
            f"sl_prog_inside={stats.slider_progress_while_inside:.3f} "
            f"sl_d_hold={stats.slider_dist_when_hold_mean_px:5.1f} "
            f"sl_d_inside={stats.slider_dist_when_inside_mean_px:5.1f} "
            f"sl_seg_q={stats.slider_segment_quality_mean:.3f} "
            f"sl_full={stats.slider_full_control_segments:3d} "
            f"sl_partial={stats.slider_partial_control_segments:3d} "
            f"sl_rev={stats.slider_reverse_events:3d} "
            f"sl_rev_follow={stats.slider_reverse_follow_ratio:.3f} "
            f"sl_curve={stats.slider_curve_steps:4d} "
            f"sl_curve_good={stats.slider_curve_good_ratio:.3f} "
            f"sl_geom_inside_ratio={stats.slider_geom_inside_ratio:.3f} "
            f"sl_time_to_first_inside={stats.slider_time_to_first_inside_mean:5.1f} "
            f"sl_first_inside_miss={stats.slider_time_to_first_inside_missed:3d} "
            f"sl_target_align={stats.slider_target_alignment_mean:5.3f} "
            f"rpx={stats.recoil_distance_mean_px:5.1f} "
            f"rjerk={stats.post_hit_jerk_mean:5.3f} "
            f"badrec={stats.bad_recoil_ratio:.3f} "
            f"smooth={stats.smooth_exit_ratio:.3f} "
            f"jerk={stats.jerk_penalty_total:7.3f} "
            f"over={stats.overspeed_penalty_total:7.3f} "
            f"drift={stats.useless_motion_penalty_total:7.3f} "
            f"policy_loss={train_metrics['policy_loss']:.4f} "
            f"value_loss={train_metrics['value_loss']:.4f} "
            f"entropy={train_metrics['entropy']:.4f} "
            f"kl={train_metrics['kl']:.5f}"
        )

    save_checkpoint(
        model=model,
        optimizer=optimizer,
        cfg=cfg,
        path=latest_ckpt,
        update_idx=cfg.updates,
        best_reward=best_reward,
    )
    print(f"[saved latest] {latest_ckpt}")
    print(f"[saved best] {best_ckpt}")
    print(f"[best reward] {best_reward:.3f}")


if __name__ == "__main__":
    main()
