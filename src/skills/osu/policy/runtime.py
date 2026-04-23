from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from src.skills.osu.env.types import OsuAction, OsuObservation


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
        return self.act_on_array(obs_np)

    def act_on_array(self, obs: np.ndarray) -> OsuAction:
        obs_t = torch.tensor(obs, dtype=torch.float32, device=self.device).unsqueeze(0)

        with torch.no_grad():
            action_t = self.model.deterministic_action(obs_t)

        action = action_t.squeeze(0).cpu().numpy()

        return OsuAction(
            dx=float(action[0]),
            dy=float(action[1]),
            click_strength=float((action[2] + 1.0) * 0.5),
        )


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


def load_policy_from_checkpoint(
    checkpoint_path: str | Path,
    device: torch.device,
    obs_dim: int,
    hidden_dim: int = 256,
) -> PPOPolicy:
    model = ActorCritic(obs_dim=obs_dim, hidden_dim=hidden_dim).to(device)
    checkpoint = torch.load(Path(checkpoint_path), map_location=device)
    load_model_state_compatible(model, checkpoint)
    model.eval()
    return PPOPolicy(model=model, device=device)
