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
    phase_name: str = "phase3_5_post_hit_motion_smoothing"

    seed: int = 42
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    updates: int = 180
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

    source_checkpoint_path: str = str(PATHS.phase2_best_checkpoint)
    run_dir: str = str(PATHS.osu_phase3_motion_smoothing_run_dir)
    checkpoint_dir: str = str(PATHS.phase3_smooth_checkpoints_dir)
    logs_dir: str = str(PATHS.phase3_smooth_logs_dir)
    metrics_dir: str = str(PATHS.phase3_smooth_metrics_dir)
    replays_dir: str = str(PATHS.phase3_smooth_replays_dir)
    eval_dir: str = str(PATHS.phase3_smooth_eval_dir)
    latest_ckpt_name: str = "latest_smooth.pt"
    best_ckpt_name: str = "best_smooth.pt"
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


@dataclass(slots=True)
class MotionState:
    prev_dx: float = 0.0
    prev_dy: float = 0.0

    recoil_steps_left: int = 0
    recoil_anchor_x: float = 0.0
    recoil_anchor_y: float = 0.0


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

    return np.asarray(values, dtype=np.float32)


def build_env(cfg: TrainConfig) -> OsuEnv:
    beatmap = parse_beatmap(cfg.beatmap_path)
    env = OsuEnv(
        beatmap=beatmap,
        dt_ms=cfg.dt_ms,
        upcoming_count=cfg.upcoming_count,
        cursor_speed_scale=cfg.cursor_speed_scale,
        click_threshold=cfg.click_threshold,
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

    prev_primary, prev_secondary = find_circle_targets(prev_obs)
    next_primary, next_secondary = find_circle_targets(next_obs)

    move_mag = movement_magnitude(action)
    urgency = compute_urgency(cfg, prev_primary)
    click_timing_error = timing_error_ms(prev_primary)
    click_abs_timing_error = abs(click_timing_error) if click_timing_error is not None else None

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
    if score_value > 0:
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
    motion_state = MotionState()

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

        click_down = osu_action.click_strength >= env.click_threshold
        just_pressed = click_down and not prev_click_down
        prev_primary, _ = find_circle_targets(obs)
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

        if movement_magnitude(osu_action) < cfg.urgent_idle_threshold:
            stats.idle_steps += 1

        # если был успешный скоринг — открываем короткое окно anti-recoil
        if step.info.get("score_value", 0) > 0:
            motion_state.recoil_steps_left = cfg.recoil_window_steps
            motion_state.recoil_anchor_x = next_obs.cursor_x
            motion_state.recoil_anchor_y = next_obs.cursor_y
        elif motion_state.recoil_steps_left > 0:
            motion_state.recoil_steps_left -= 1

        motion_state.prev_dx = osu_action.dx
        motion_state.prev_dy = osu_action.dy

        prev_click_down = click_down
        obs = next_obs

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
    model.load_state_dict(payload["model_state_dict"])
    if "optimizer_state_dict" in payload:
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
            f"Phase 3.5 motion smoothing fine-tuning requires source checkpoint: {source_ckpt}"
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
    print("PHASE 3.5 POST-HIT MOTION SMOOTHING FINE-TUNING STARTED")
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
