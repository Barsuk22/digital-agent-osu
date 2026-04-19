from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from src.core.config.paths import PATHS
from src.skills.osu.env.osu_env import OsuEnv
from src.skills.osu.env.types import OsuAction, OsuObservation, UpcomingObjectView
from src.skills.osu.parser.osu_parser import parse_beatmap


@dataclass(slots=True)
class SpinnerDebugConfig:
    beatmap_path: str = str(PATHS.active_map)
    output_path: str = str(PATHS.phase6_spinner_metrics_dir / "spinner_control_debug_trace.json")
    dt_ms: float = 16.6667
    upcoming_count: int = 5
    cursor_speed_scale: float = 11.0
    click_threshold: float = 0.75
    slider_hold_threshold: float = 0.45
    spinner_hold_threshold: float = 0.45
    spinner_radius_px: float = 110.0
    angular_speed_rad_per_step: float = 0.22
    max_trace_rows: int = 320


@dataclass(slots=True)
class SpinnerDebugStats:
    spinner_active_steps: int = 0
    spinner_hold_steps: int = 0
    spinner_good_radius_steps: int = 0
    spinner_clear_count: int = 0
    spinner_partial_count: int = 0
    spinner_miss_count: int = 0
    spinner_radius_error_total: float = 0.0
    spinner_max_spins: float = 0.0

    @property
    def spinner_hold_ratio(self) -> float:
        return 0.0 if self.spinner_active_steps <= 0 else self.spinner_hold_steps / self.spinner_active_steps

    @property
    def spinner_good_radius_ratio(self) -> float:
        return 0.0 if self.spinner_active_steps <= 0 else self.spinner_good_radius_steps / self.spinner_active_steps

    @property
    def spinner_radius_error_mean(self) -> float:
        return 0.0 if self.spinner_active_steps <= 0 else self.spinner_radius_error_total / self.spinner_active_steps


def first_play_target(obs: OsuObservation) -> UpcomingObjectView | None:
    for item in obs.upcoming:
        if item.kind_id in (0, 1, 2):
            return item
    return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def chase_or_spin_action(obs: OsuObservation, cfg: SpinnerDebugConfig, angle: float) -> OsuAction:
    if obs.spinner.active_spinner > 0.5:
        target_x = obs.spinner.center_x + math.cos(angle) * cfg.spinner_radius_px
        target_y = obs.spinner.center_y + math.sin(angle) * cfg.spinner_radius_px
        click = 1.0
    else:
        target = first_play_target(obs)
        if target is None:
            return OsuAction(dx=0.0, dy=0.0, click_strength=0.0)

        if target.kind_id == 2 and 0.0 <= target.time_to_hit_ms <= 360.0:
            target_x = 256.0 + math.cos(angle) * cfg.spinner_radius_px
            target_y = 192.0 + math.sin(angle) * cfg.spinner_radius_px
            click = 0.0
        else:
            target_x = target.x
            target_y = target.y
            click = 1.0 if abs(target.time_to_hit_ms) <= 45.0 and target.distance_to_cursor <= 72.0 else 0.0

    dx = clamp((target_x - obs.cursor_x) / max(1.0, cfg.cursor_speed_scale), -1.0, 1.0)
    dy = clamp((target_y - obs.cursor_y) / max(1.0, cfg.cursor_speed_scale), -1.0, 1.0)
    return OsuAction(dx=dx, dy=dy, click_strength=max(click, cfg.click_threshold if click > 0.0 else 0.0))


def update_stats(stats: SpinnerDebugStats, obs: OsuObservation, action: OsuAction, judgement: str, cfg: SpinnerDebugConfig) -> None:
    if obs.spinner.active_spinner > 0.5:
        stats.spinner_active_steps += 1
        stats.spinner_radius_error_total += obs.spinner.radius_error
        stats.spinner_max_spins = max(stats.spinner_max_spins, obs.spinner.spins)
        if action.click_strength >= cfg.spinner_hold_threshold:
            stats.spinner_hold_steps += 1
        if obs.spinner.radius_error <= 58.0:
            stats.spinner_good_radius_steps += 1

    if judgement == "spinner_clear":
        stats.spinner_clear_count += 1
    elif judgement == "spinner_partial":
        stats.spinner_partial_count += 1
    elif judgement == "spinner_miss":
        stats.spinner_miss_count += 1


def main() -> None:
    cfg = SpinnerDebugConfig()
    beatmap = parse_beatmap(cfg.beatmap_path)
    env = OsuEnv(
        beatmap=beatmap,
        dt_ms=cfg.dt_ms,
        upcoming_count=cfg.upcoming_count,
        cursor_speed_scale=cfg.cursor_speed_scale,
        click_threshold=cfg.click_threshold,
        slider_hold_threshold=cfg.slider_hold_threshold,
        spinner_hold_threshold=cfg.spinner_hold_threshold,
    )

    obs = env.reset()
    stats = SpinnerDebugStats()
    trace: list[dict] = []
    angle = 0.0

    while not env.done:
        if obs.spinner.active_spinner > 0.5:
            angle += cfg.angular_speed_rad_per_step
        action = chase_or_spin_action(obs, cfg, angle)
        step = env.step(action)
        judgement = str(step.info.get("judgement", "none"))
        update_stats(stats, obs, action, judgement, cfg)

        if obs.spinner.active_spinner > 0.5 and len(trace) < cfg.max_trace_rows:
            trace.append(
                {
                    "time_ms": round(obs.time_ms, 3),
                    "cursor_x": round(obs.cursor_x, 3),
                    "cursor_y": round(obs.cursor_y, 3),
                    "spins": round(obs.spinner.spins, 4),
                    "progress": round(obs.spinner.progress, 4),
                    "radius_error": round(obs.spinner.radius_error, 3),
                    "angular_velocity": round(obs.spinner.angular_velocity, 3),
                    "click_down": bool(step.info.get("click_down", False)),
                    "judgement": judgement,
                }
            )

        obs = step.observation

    payload = {
        "map": {
            "artist": beatmap.artist,
            "title": beatmap.title,
            "version": beatmap.version,
            "objects": len(beatmap.hit_objects),
        },
        "policy": "deterministic spinner circle sanity policy",
        "config": asdict(cfg),
        "summary": {
            "spin_active": stats.spinner_active_steps,
            "spin_hold": stats.spinner_hold_ratio,
            "spin_good_rad": stats.spinner_good_radius_ratio,
            "spin_drad": stats.spinner_radius_error_mean,
            "spin_max": stats.spinner_max_spins,
            "spin_clear": stats.spinner_clear_count,
            "spin_part": stats.spinner_partial_count,
            "spin_miss": stats.spinner_miss_count,
        },
        "spinner_trace": trace,
    }

    output_path = Path(cfg.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"[debug trace] {output_path}")
    print(
        "[spinner sanity] "
        f"spin_active={stats.spinner_active_steps} "
        f"spin_hold={stats.spinner_hold_ratio:.3f} "
        f"spin_good_rad={stats.spinner_good_radius_ratio:.3f} "
        f"spin_drad={stats.spinner_radius_error_mean:.1f} "
        f"spin_max={stats.spinner_max_spins:.2f} "
        f"spin_clear={stats.spinner_clear_count} "
        f"spin_part={stats.spinner_partial_count} "
        f"spin_miss={stats.spinner_miss_count}"
    )


if __name__ == "__main__":
    main()
