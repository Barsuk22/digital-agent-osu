from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from src.skills.osu.env.osu_env import OsuEnv
from src.skills.osu.env.types import OsuAction, OsuObservation
from src.skills.osu.parser.osu_parser import parse_beatmap
from src.skills.osu.replay.replay_io import save_replay
from src.skills.osu.viewer.pygame_viewer import OsuViewer, ViewerConfig
from src.core.config.paths import PATHS


def default_eval_beatmap_path() -> str:
    return os.environ.get("OSU_EVAL_MAP", str(PATHS.phase7_eval_maps[0]))


def default_eval_checkpoint_path() -> str:
    return os.environ.get("OSU_EVAL_CHECKPOINT", str(PATHS.phase8_easy_best_checkpoint))


@dataclass(slots=True)
class EvalConfig:
    beatmap_path: str = field(default_factory=default_eval_beatmap_path)
    checkpoint_path: str = field(default_factory=default_eval_checkpoint_path)
    replay_path: str = str(PATHS.phase8_easy_best_eval_replay)
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    timing_good_window_ms: float = 55.0
    timing_focus_window_ms: float = 165.0
    click_near_distance_px: float = 58.0
    click_far_distance_px: float = 110.0
    click_threshold: float = 0.75
    slider_hold_threshold: float = 0.45
    spinner_hold_threshold: float = 0.45
    spinner_good_radius_tolerance_px: float = 26.0
    spinner_min_radius_px: float = 42.0
    spinner_max_radius_px: float = 125.0
    spinner_min_delta_per_step: float = 0.025
    spinner_max_delta_per_step: float = 0.50
    spinner_eval_controller: bool = True
    spinner_target_radius_px: float = 76.0
    spinner_controller_extra_spins: float = 1.2
    spinner_controller_min_tangent_action: float = 0.16
    spinner_controller_max_tangent_action: float = 0.48
    spinner_controller_cursor_speed_scale: float = 14.0
    spinner_controller_radial_gain: float = 0.020
    spinner_controller_radial_cap: float = 0.35
    spinner_controller_click_strength: float = 0.62
    spinner_controller_variation_amp: float = 0.055
    spinner_controller_ramp_progress: float = 0.12
    spinner_controller_ramp_down_ms: float = 260.0


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

    values.extend(
        [
            obs.spinner.active_spinner,
            obs.spinner.primary_is_spinner,
            obs.spinner.progress,
            obs.spinner.spins / 8.0,
            obs.spinner.target_spins / 8.0,
            obs.spinner.time_to_end_ms / 1000.0,
            obs.spinner.center_x / 512.0,
            obs.spinner.center_y / 384.0,
            obs.spinner.distance_to_center / 256.0,
            obs.spinner.radius_error / 256.0,
            obs.spinner.angle_sin,
            obs.spinner.angle_cos,
            obs.spinner.angular_velocity / 60.0,
        ]
    )

    return np.asarray(values, dtype=np.float32)


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
        clamped_log_std = torch.clamp(self.log_std, min=-0.9, max=0.45)
        log_std = clamped_log_std.expand_as(mean)
        return mean, log_std, value

    def deterministic_action(self, obs: torch.Tensor) -> torch.Tensor:
        mean, _, _ = self.forward(obs)
        return torch.tanh(mean)


class PPOPolicy:
    def __init__(self, model: ActorCritic, device: torch.device) -> None:
        self.model = model
        self.device = device

    def __call__(self, obs: OsuObservation) -> OsuAction:
        obs_np = obs_to_numpy(obs)
        obs_t = torch.tensor(obs_np, dtype=torch.float32, device=self.device).unsqueeze(0)

        with torch.no_grad():
            action_t = self.model.deterministic_action(obs_t)

        action = action_t.squeeze(0).cpu().numpy()

        return OsuAction(
            dx=float(action[0]),
            dy=float(action[1]),
            click_strength=float((action[2] + 1.0) * 0.5),
        )


@dataclass(slots=True)
class SpinnerControllerState:
    active: bool = False
    direction: float = 1.0
    phase: float = 0.0
    spinner_count: int = 0


def spinner_control_action(
    obs: OsuObservation,
    cfg: EvalConfig,
    policy_action: OsuAction,
    state: SpinnerControllerState,
) -> OsuAction:
    if not cfg.spinner_eval_controller or obs.spinner.active_spinner <= 0.5:
        state.active = False
        return policy_action

    if not state.active:
        state.active = True
        state.spinner_count += 1
        seed = obs.time_ms * 0.013 + obs.cursor_x * 0.017 + obs.cursor_y * 0.011
        state.direction = 1.0 if math.sin(seed) >= 0.0 else -1.0
        state.phase = seed + state.spinner_count * 1.618

    target_spins = max(obs.spinner.target_spins + cfg.spinner_controller_extra_spins, obs.spinner.target_spins)
    remaining_spins = max(0.0, target_spins - obs.spinner.spins)
    steps_left = max(1.0, obs.spinner.time_to_end_ms / 16.6667)
    radius_for_speed = max(24.0, obs.spinner.distance_to_center)
    needed_delta = remaining_spins * 2.0 * math.pi / steps_left
    tangent = needed_delta * radius_for_speed / max(1.0, cfg.spinner_controller_cursor_speed_scale)
    tangent = max(cfg.spinner_controller_min_tangent_action, min(cfg.spinner_controller_max_tangent_action, tangent))

    variation = cfg.spinner_controller_variation_amp * (
        0.70 * math.sin(obs.time_ms * 0.010 + state.phase)
        + 0.30 * math.sin(obs.time_ms * 0.023 + state.phase * 0.37)
    )
    tangent = max(
        cfg.spinner_controller_min_tangent_action,
        min(cfg.spinner_controller_max_tangent_action, tangent + variation),
    )

    ramp_up = min(1.0, max(0.35, obs.spinner.progress / max(1e-6, cfg.spinner_controller_ramp_progress)))
    if obs.spinner.spins >= obs.spinner.target_spins and obs.spinner.time_to_end_ms <= cfg.spinner_controller_ramp_down_ms:
        ramp_down = max(0.35, obs.spinner.time_to_end_ms / max(1.0, cfg.spinner_controller_ramp_down_ms))
    else:
        ramp_down = 1.0
    tangent *= min(ramp_up, ramp_down) * state.direction

    radial = (cfg.spinner_target_radius_px - obs.spinner.distance_to_center) * cfg.spinner_controller_radial_gain
    radial = max(-cfg.spinner_controller_radial_cap, min(cfg.spinner_controller_radial_cap, radial))

    angle_sin = obs.spinner.angle_sin
    angle_cos = obs.spinner.angle_cos
    dx = -angle_sin * tangent + angle_cos * radial
    dy = angle_cos * tangent + angle_sin * radial

    return OsuAction(
        dx=max(-0.95, min(0.95, dx)),
        dy=max(-0.95, min(0.95, dy)),
        click_strength=cfg.spinner_controller_click_strength,
    )


@dataclass(slots=True)
class EvalStats:
    total_clicks: int = 0
    hits: int = 0
    misses: int = 0
    early_clicks: int = 0
    late_clicks: int = 0
    off_window_clicks: int = 0
    good_window_clicks: int = 0
    near_clicks: int = 0
    far_clicks: int = 0
    slider_head_hits: int = 0
    slider_drops: int = 0
    slider_finishes: int = 0
    slider_tick_hits: int = 0
    slider_tick_misses: int = 0
    slider_active_steps: int = 0
    slider_inside_steps: int = 0
    slider_follow_dist_total: float = 0.0
    slider_click_hold_steps: int = 0
    slider_click_released_steps: int = 0
    slider_good_follow_chain_total: int = 0
    slider_good_follow_chain_count: int = 0
    slider_good_follow_chain_max: int = 0
    slider_segment_quality_total: float = 0.0
    slider_segment_quality_count: int = 0
    slider_full_control_segments: int = 0
    slider_partial_control_segments: int = 0
    slider_reverse_events: int = 0
    slider_reverse_follow_steps: int = 0
    slider_reverse_drop_steps: int = 0
    slider_curve_steps: int = 0
    slider_curve_good_steps: int = 0
    spinner_active_steps: int = 0
    spinner_hold_steps: int = 0
    spinner_good_radius_steps: int = 0
    spinner_spin_steps: int = 0
    spinner_stall_steps: int = 0
    spinner_clear_count: int = 0
    spinner_partial_count: int = 0
    spinner_no_hold_count: int = 0
    spinner_miss_count: int = 0
    spinner_radius_error_total: float = 0.0
    spinner_spin_progress_max: float = 0.0
    timing_errors_ms: list[float] = field(default_factory=list)
    click_distances_px: list[float] = field(default_factory=list)

    @property
    def timing_mean_ms(self) -> float:
        return 0.0 if not self.timing_errors_ms else float(np.mean([abs(v) for v in self.timing_errors_ms]))

    @property
    def timing_median_ms(self) -> float:
        return 0.0 if not self.timing_errors_ms else float(np.median([abs(v) for v in self.timing_errors_ms]))

    @property
    def good_timing_ratio(self) -> float:
        return 0.0 if self.total_clicks <= 0 else self.good_window_clicks / self.total_clicks

    @property
    def mean_click_distance_px(self) -> float:
        return 0.0 if not self.click_distances_px else float(np.mean(self.click_distances_px))

    @property
    def near_click_ratio(self) -> float:
        return 0.0 if self.total_clicks <= 0 else self.near_clicks / self.total_clicks

    @property
    def far_click_ratio(self) -> float:
        return 0.0 if self.total_clicks <= 0 else self.far_clicks / self.total_clicks

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
    def slider_good_follow_chain_mean(self) -> float:
        if self.slider_good_follow_chain_count <= 0:
            return 0.0
        return self.slider_good_follow_chain_total / self.slider_good_follow_chain_count

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

    @property
    def spinner_hold_ratio(self) -> float:
        return 0.0 if self.spinner_active_steps <= 0 else self.spinner_hold_steps / self.spinner_active_steps

    @property
    def spinner_good_radius_ratio(self) -> float:
        return 0.0 if self.spinner_active_steps <= 0 else self.spinner_good_radius_steps / self.spinner_active_steps

    @property
    def spinner_spin_step_ratio(self) -> float:
        return 0.0 if self.spinner_active_steps <= 0 else self.spinner_spin_steps / self.spinner_active_steps

    @property
    def spinner_radius_error_mean_px(self) -> float:
        return 0.0 if self.spinner_active_steps <= 0 else self.spinner_radius_error_total / self.spinner_active_steps


def first_circle(obs: OsuObservation):
    for item in obs.upcoming:
        if item.kind_id == 0:
            return item
    return None


def first_hit_target(obs: OsuObservation):
    for item in obs.upcoming:
        if item.kind_id in (0, 1):
            return item
    return None


def load_model_state_compatible(model: ActorCritic, checkpoint: dict) -> None:
    loaded_state = checkpoint["model_state_dict"]
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


def rollout_episode(env: OsuEnv, policy: PPOPolicy, cfg: EvalConfig) -> tuple[list, EvalStats]:
    obs = env.reset()
    stats = EvalStats()
    prev_click_down = False
    prev_raw_click_down = False
    prev_slider_active = False
    slider_segment_steps = 0
    slider_segment_inside_steps = 0
    slider_good_follow_chain = 0
    slider_segment_finished = False
    prev_tangent_x = 0.0
    prev_tangent_y = 0.0
    reverse_steps_left = 0
    spinner_controller_state = SpinnerControllerState()

    while not env.done:
        action = spinner_control_action(obs, cfg, policy(obs), spinner_controller_state)
        raw_click_down = action.click_strength >= env.click_threshold
        slider_hold_down = obs.slider.active_slider > 0.5 and action.click_strength >= env.slider_hold_threshold
        spinner_hold_down = obs.spinner.active_spinner > 0.5 and action.click_strength >= env.spinner_hold_threshold
        click_down = raw_click_down or slider_hold_down or spinner_hold_down
        just_pressed = raw_click_down and not prev_raw_click_down
        target = first_hit_target(obs)

        step = env.step(action)

        if just_pressed:
            stats.total_clicks += 1
            if target is not None:
                timing_error = target.time_to_hit_ms
                abs_timing_error = abs(timing_error)
                stats.timing_errors_ms.append(timing_error)
                stats.click_distances_px.append(target.distance_to_cursor)

                if timing_error > cfg.timing_good_window_ms:
                    stats.early_clicks += 1
                elif timing_error < -cfg.timing_good_window_ms:
                    stats.late_clicks += 1
                if abs_timing_error > cfg.timing_focus_window_ms:
                    stats.off_window_clicks += 1
                if abs_timing_error <= cfg.timing_good_window_ms:
                    stats.good_window_clicks += 1
                if target.distance_to_cursor <= cfg.click_near_distance_px:
                    stats.near_clicks += 1
                elif target.distance_to_cursor >= cfg.click_far_distance_px:
                    stats.far_clicks += 1

        if step.info.get("score_value", 0) > 0:
            stats.hits += 1
        if step.info.get("judgement") == "miss":
            stats.misses += 1

        if obs.slider.active_slider > 0.5:
            if not prev_slider_active:
                slider_segment_steps = 0
                slider_segment_inside_steps = 0
                slider_good_follow_chain = 0
                slider_segment_finished = False
                prev_tangent_x = 0.0
                prev_tangent_y = 0.0
                reverse_steps_left = 0

            tangent_dot = obs.slider.tangent_x * prev_tangent_x + obs.slider.tangent_y * prev_tangent_y
            curved_step = slider_segment_steps > 0 and tangent_dot < 0.92
            reverse_event = slider_segment_steps > 0 and tangent_dot < -0.35
            reverse_window = reverse_steps_left > 0 or reverse_event
            if curved_step:
                stats.slider_curve_steps += 1
            if reverse_event:
                stats.slider_reverse_events += 1
                reverse_steps_left = 18

            stats.slider_active_steps += 1
            stats.slider_follow_dist_total += obs.slider.distance_to_target
            if obs.slider.inside_follow > 0.5 and click_down:
                stats.slider_inside_steps += 1
                slider_segment_inside_steps += 1
                slider_good_follow_chain += 1
                stats.slider_good_follow_chain_max = max(stats.slider_good_follow_chain_max, slider_good_follow_chain)
                if curved_step:
                    stats.slider_curve_good_steps += 1
                if reverse_window:
                    stats.slider_reverse_follow_steps += 1
            else:
                if slider_good_follow_chain > 0:
                    stats.slider_good_follow_chain_total += slider_good_follow_chain
                    stats.slider_good_follow_chain_count += 1
                slider_good_follow_chain = 0
                if reverse_window:
                    stats.slider_reverse_drop_steps += 1
            if click_down:
                stats.slider_click_hold_steps += 1
            else:
                stats.slider_click_released_steps += 1
                if reverse_window:
                    stats.slider_reverse_drop_steps += 1
            slider_segment_steps += 1
            prev_tangent_x = obs.slider.tangent_x
            prev_tangent_y = obs.slider.tangent_y
            if reverse_steps_left > 0 and not reverse_event:
                reverse_steps_left -= 1
        elif prev_slider_active:
            if slider_good_follow_chain > 0:
                stats.slider_good_follow_chain_total += slider_good_follow_chain
                stats.slider_good_follow_chain_count += 1
                slider_good_follow_chain = 0
            if slider_segment_steps > 0:
                segment_quality = slider_segment_inside_steps / slider_segment_steps
                stats.slider_segment_quality_total += segment_quality
                stats.slider_segment_quality_count += 1
                if slider_segment_finished and segment_quality >= 0.55:
                    stats.slider_full_control_segments += 1
                elif slider_segment_inside_steps > 0 or slider_segment_finished:
                    stats.slider_partial_control_segments += 1

        if obs.spinner.active_spinner > 0.5:
            stats.spinner_active_steps += 1
            stats.spinner_radius_error_total += obs.spinner.radius_error
            stats.spinner_spin_progress_max = max(stats.spinner_spin_progress_max, obs.spinner.spins)
            if click_down:
                stats.spinner_hold_steps += 1
            if obs.spinner.radius_error <= cfg.spinner_good_radius_tolerance_px:
                stats.spinner_good_radius_steps += 1
            angular_step = abs(obs.spinner.angular_velocity) * 0.0166667
            valid_radius = cfg.spinner_min_radius_px <= obs.spinner.distance_to_center <= cfg.spinner_max_radius_px
            if valid_radius and cfg.spinner_min_delta_per_step <= angular_step <= cfg.spinner_max_delta_per_step:
                stats.spinner_spin_steps += 1
            elif click_down:
                stats.spinner_stall_steps += 1

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
        elif judgement == "spinner_clear":
            stats.spinner_clear_count += 1
        elif judgement == "spinner_partial":
            stats.spinner_partial_count += 1
        elif judgement == "spinner_no_hold":
            stats.spinner_no_hold_count += 1
        elif judgement == "spinner_miss":
            stats.spinner_miss_count += 1

        current_slider_active = obs.slider.active_slider > 0.5
        obs = step.observation
        prev_click_down = click_down
        prev_raw_click_down = raw_click_down
        prev_slider_active = current_slider_active

    if prev_slider_active:
        if slider_good_follow_chain > 0:
            stats.slider_good_follow_chain_total += slider_good_follow_chain
            stats.slider_good_follow_chain_count += 1
        if slider_segment_steps > 0:
            segment_quality = slider_segment_inside_steps / slider_segment_steps
            stats.slider_segment_quality_total += segment_quality
            stats.slider_segment_quality_count += 1
            if slider_segment_finished and segment_quality >= 0.55:
                stats.slider_full_control_segments += 1
            elif slider_segment_inside_steps > 0 or slider_segment_finished:
                stats.slider_partial_control_segments += 1

    return env.replay_frames, stats


def main() -> None:
    cfg = EvalConfig()
    device = torch.device(cfg.device)

    beatmap = parse_beatmap(cfg.beatmap_path)
    print(f"[beatmap] {beatmap.artist} - {beatmap.title} [{beatmap.version}]")
    if beatmap.background_filename and beatmap.background_path is None:
        print(f"[background missing] {beatmap.background_filename}")
    if beatmap.video_path is not None:
        print(f"[video] {beatmap.video_path} start={beatmap.video_start_time_ms:.0f}ms")
    elif beatmap.video_filename:
        print(f"[video missing] {beatmap.video_filename}")

    # 1. Делаем честный прогон без viewer
    env_rollout = OsuEnv(
        beatmap=beatmap,
        dt_ms=16.6667,
        upcoming_count=5,
        cursor_speed_scale=14.0,
        click_threshold=cfg.click_threshold,
        slider_hold_threshold=cfg.slider_hold_threshold,
        spinner_hold_threshold=cfg.spinner_hold_threshold,
    )

    obs_dim = len(obs_to_numpy(env_rollout.reset()))
    model = ActorCritic(obs_dim=obs_dim, hidden_dim=256).to(device)

    checkpoint_path = Path(cfg.checkpoint_path)
    if not checkpoint_path.exists():
        print(f"[phase8 easy checkpoint not found] {checkpoint_path}")
        for fallback in (
            PATHS.phase8_easy_latest_checkpoint,
            PATHS.phase7_multimap_best_checkpoint,
            PATHS.phase7_multimap_latest_checkpoint,
            PATHS.spica_main_golden_checkpoint,
            PATHS.spica_main_latest_checkpoint,
            PATHS.spica_main_best_checkpoint,
            PATHS.phase6_spinner_latest_checkpoint,
            PATHS.phase6_spinner_best_checkpoint,
            PATHS.phase5_slider_best_checkpoint,
            PATHS.phase4_slider_best_checkpoint,
            PATHS.phase3_smooth_best_checkpoint,
            PATHS.phase2_best_checkpoint,
            PATHS.best_checkpoint,
        ):
            if fallback.exists():
                print(f"[fallback checkpoint] {fallback}")
                checkpoint_path = fallback
                break

    checkpoint = torch.load(checkpoint_path, map_location=device)
    load_model_state_compatible(model, checkpoint)
    model.eval()

    policy = PPOPolicy(model=model, device=device)

    frames, stats = rollout_episode(env_rollout, policy, cfg)

    replay_path = Path(cfg.replay_path)
    save_replay(frames, replay_path)
    print(f"[checkpoint] {checkpoint_path}")
    print(f"[saved replay] {replay_path}")
    print(
        "[eval] "
        f"hits={stats.hits} "
        f"miss={stats.misses} "
        f"clicks={stats.total_clicks} "
        f"tmean={stats.timing_mean_ms:.1f} "
        f"tmed={stats.timing_median_ms:.1f} "
        f"good_t={stats.good_timing_ratio:.3f} "
        f"early={stats.early_clicks} "
        f"late={stats.late_clicks} "
        f"off={stats.off_window_clicks} "
        f"dclick={stats.mean_click_distance_px:.1f} "
        f"near={stats.near_click_ratio:.3f} "
        f"far={stats.far_click_ratio:.3f} "
        f"sl_head={stats.slider_head_hits} "
        f"sl_fin={stats.slider_finishes} "
        f"sl_tick={stats.slider_tick_hit_rate:.3f} "
        f"sl_drop={stats.slider_drops} "
        f"sl_inside_ratio={stats.slider_inside_ratio:.3f} "
        f"sl_follow_dist_mean={stats.slider_follow_distance_mean_px:.1f} "
        f"sl_finish_rate={stats.slider_finish_rate:.3f} "
        f"sl_click_hold_steps={stats.slider_click_hold_steps} "
        f"sl_click_released_steps={stats.slider_click_released_steps} "
        f"sl_chain_mean={stats.slider_good_follow_chain_mean:.1f} "
        f"sl_chain_max={stats.slider_good_follow_chain_max} "
        f"sl_seg_q={stats.slider_segment_quality_mean:.3f} "
        f"sl_full={stats.slider_full_control_segments} "
        f"sl_partial={stats.slider_partial_control_segments} "
        f"sl_rev={stats.slider_reverse_events} "
        f"sl_rev_follow={stats.slider_reverse_follow_ratio:.3f} "
        f"sl_curve={stats.slider_curve_steps} "
        f"sl_curve_good={stats.slider_curve_good_ratio:.3f} "
        f"spin_active={stats.spinner_active_steps} "
        f"spin_hold={stats.spinner_hold_ratio:.3f} "
        f"spin_good_rad={stats.spinner_good_radius_ratio:.3f} "
        f"spin_drad={stats.spinner_radius_error_mean_px:.1f} "
        f"spin_step={stats.spinner_spin_step_ratio:.3f} "
        f"spin_prog={stats.spinner_spin_progress_max:.2f} "
        f"spin_stall={stats.spinner_stall_steps} "
        f"spin_clear={stats.spinner_clear_count} "
        f"spin_part={stats.spinner_partial_count} "
        f"spin_nohold={stats.spinner_no_hold_count} "
        f"spin_miss={stats.spinner_miss_count}"
    )

    # 2. Показываем уже сохранённый replay
    env_view = OsuEnv(
        beatmap=beatmap,
        dt_ms=16.6667,
        upcoming_count=5,
        cursor_speed_scale=14.0,
        click_threshold=cfg.click_threshold,
        slider_hold_threshold=cfg.slider_hold_threshold,
        spinner_hold_threshold=cfg.spinner_hold_threshold,
    )

    viewer = OsuViewer(
        env_view,
        ViewerConfig(
            window_width=1600,
            window_height=900,
            fps=60,
            background_dim_alpha=150,
            playfield_pad_x=80,
            playfield_pad_y=60,
        ),
    )

    viewer.play_replay(frames)


if __name__ == "__main__":
    main()
