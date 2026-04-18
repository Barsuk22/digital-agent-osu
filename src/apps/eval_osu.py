from __future__ import annotations

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


@dataclass(slots=True)
class EvalConfig:
    beatmap_path: str = str(PATHS.active_map)
    checkpoint_path: str = str(PATHS.phase3_smooth_best_checkpoint)
    replay_path: str = str(PATHS.phase3_smooth_best_eval_replay)
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    timing_good_window_ms: float = 55.0
    timing_focus_window_ms: float = 165.0
    click_near_distance_px: float = 58.0
    click_far_distance_px: float = 110.0


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


def first_circle(obs: OsuObservation):
    for item in obs.upcoming:
        if item.kind_id == 0:
            return item
    return None


def rollout_episode(env: OsuEnv, policy: PPOPolicy, cfg: EvalConfig) -> tuple[list, EvalStats]:
    obs = env.reset()
    stats = EvalStats()
    prev_click_down = False

    while not env.done:
        action = policy(obs)
        click_down = action.click_strength >= env.click_threshold
        just_pressed = click_down and not prev_click_down
        target = first_circle(obs)

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

        obs = step.observation
        prev_click_down = click_down

    return env.replay_frames, stats


def main() -> None:
    cfg = EvalConfig()
    device = torch.device(cfg.device)

    beatmap = parse_beatmap(cfg.beatmap_path)

    # 1. Делаем честный прогон без viewer
    env_rollout = OsuEnv(
        beatmap=beatmap,
        dt_ms=16.6667,
        upcoming_count=5,
        cursor_speed_scale=14.0,
        click_threshold=0.75,
    )

    obs_dim = len(obs_to_numpy(env_rollout.reset()))
    model = ActorCritic(obs_dim=obs_dim, hidden_dim=256).to(device)

    checkpoint_path = Path(cfg.checkpoint_path)
    if not checkpoint_path.exists():
        print(f"[phase3 smooth checkpoint not found] {checkpoint_path}")
        for fallback in (PATHS.phase2_best_checkpoint, PATHS.best_checkpoint):
            if fallback.exists():
                print(f"[fallback checkpoint] {fallback}")
                checkpoint_path = fallback
                break

    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
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
        f"far={stats.far_click_ratio:.3f}"
    )

    # 2. Показываем уже сохранённый replay
    env_view = OsuEnv(
        beatmap=beatmap,
        dt_ms=16.6667,
        upcoming_count=5,
        cursor_speed_scale=14.0,
        click_threshold=0.75,
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
