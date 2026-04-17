from __future__ import annotations

from dataclasses import dataclass
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
    checkpoint_path: str = str(PATHS.best_checkpoint)
    replay_path: str = str(PATHS.best_eval_replay)
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


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
        self.log_std = nn.Parameter(torch.full((action_dim,), -0.5))

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.backbone(obs)
        mean = self.actor_mean(features)
        value = self.critic(features).squeeze(-1)
        return mean, value

    def deterministic_action(self, obs: torch.Tensor) -> torch.Tensor:
        mean, _ = self.forward(obs)
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


def rollout_episode(env: OsuEnv, policy: PPOPolicy) -> list:
    obs = env.reset()

    while not env.done:
        action = policy(obs)
        step = env.step(action)
        obs = step.observation

    return env.replay_frames


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

    checkpoint = torch.load(cfg.checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    policy = PPOPolicy(model=model, device=device)

    frames = rollout_episode(env_rollout, policy)

    replay_path = Path(cfg.replay_path)
    save_replay(frames, replay_path)
    print(f"[saved replay] {replay_path}")

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