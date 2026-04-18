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
class SliderDebugConfig:
    beatmap_path: str = str(PATHS.active_map)
    output_path: str = str(PATHS.phase5_slider_metrics_dir / "slider_control_debug_trace.json")
    dt_ms: float = 16.6667
    upcoming_count: int = 5
    cursor_speed_scale: float = 11.0
    click_threshold: float = 0.75
    slider_hold_threshold: float = 0.45
    max_trace_rows: int = 260


@dataclass(slots=True)
class SliderDebugStats:
    slider_head_hits: int = 0
    slider_follow_steps: int = 0
    slider_finishes: int = 0
    slider_drops: int = 0
    slider_tick_hits: int = 0
    slider_tick_misses: int = 0
    slider_active_steps: int = 0
    slider_inside_steps: int = 0
    slider_follow_dist_total: float = 0.0

    @property
    def slider_inside_ratio(self) -> float:
        return 0.0 if self.slider_active_steps <= 0 else self.slider_inside_steps / self.slider_active_steps

    @property
    def slider_follow_dist_mean(self) -> float:
        return 0.0 if self.slider_active_steps <= 0 else self.slider_follow_dist_total / self.slider_active_steps

    @property
    def slider_finish_rate(self) -> float:
        denom = self.slider_finishes + self.slider_drops
        return 0.0 if denom <= 0 else self.slider_finishes / denom

    @property
    def slider_tick_hit_rate(self) -> float:
        denom = self.slider_tick_hits + self.slider_tick_misses
        return 0.0 if denom <= 0 else self.slider_tick_hits / denom


def first_hit_target(obs: OsuObservation) -> UpcomingObjectView | None:
    for item in obs.upcoming:
        if item.kind_id in (0, 1):
            return item
    return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def chase_action(
    obs: OsuObservation,
    cursor_speed_scale: float,
    click_threshold: float,
) -> OsuAction:
    if obs.slider.active_slider > 0.5:
        target_x = obs.slider.target_x
        target_y = obs.slider.target_y
        click = 1.0
    else:
        target = first_hit_target(obs)
        if target is None:
            return OsuAction(dx=0.0, dy=0.0, click_strength=0.0)
        target_x = target.x
        target_y = target.y
        click = 1.0 if abs(target.time_to_hit_ms) <= 45.0 and target.distance_to_cursor <= 72.0 else 0.0

    dx = clamp((target_x - obs.cursor_x) / max(1.0, cursor_speed_scale), -1.0, 1.0)
    dy = clamp((target_y - obs.cursor_y) / max(1.0, cursor_speed_scale), -1.0, 1.0)
    if abs(dx) < 0.01:
        dx = 0.0
    if abs(dy) < 0.01:
        dy = 0.0

    return OsuAction(dx=dx, dy=dy, click_strength=max(click, click_threshold if click > 0.0 else 0.0))


def update_stats(stats: SliderDebugStats, obs: OsuObservation, action: OsuAction, judgement: str, slider_hold_threshold: float) -> None:
    if obs.slider.active_slider > 0.5:
        stats.slider_active_steps += 1
        stats.slider_follow_dist_total += obs.slider.distance_to_target
        if obs.slider.inside_follow > 0.5 and action.click_strength >= slider_hold_threshold:
            stats.slider_inside_steps += 1

    if judgement == "slider_head":
        stats.slider_head_hits += 1
    elif judgement == "slider_follow":
        stats.slider_follow_steps += 1
    elif judgement == "slider_finish":
        stats.slider_finishes += 1
    elif judgement == "slider_drop":
        stats.slider_drops += 1
    elif judgement == "slider_tick":
        stats.slider_tick_hits += 1
    elif judgement == "slider_tick_miss":
        stats.slider_tick_misses += 1


def main() -> None:
    cfg = SliderDebugConfig()
    beatmap = parse_beatmap(cfg.beatmap_path)
    env = OsuEnv(
        beatmap=beatmap,
        dt_ms=cfg.dt_ms,
        upcoming_count=cfg.upcoming_count,
        cursor_speed_scale=cfg.cursor_speed_scale,
        click_threshold=cfg.click_threshold,
        slider_hold_threshold=cfg.slider_hold_threshold,
    )

    obs = env.reset()
    stats = SliderDebugStats()
    trace: list[dict] = []
    tracing_first_slider = False
    first_slider_done = False

    while not env.done:
        action = chase_action(obs, cfg.cursor_speed_scale, cfg.click_threshold)
        step = env.step(action)
        judgement = str(step.info.get("judgement", "none"))
        update_stats(stats, obs, action, judgement, cfg.slider_hold_threshold)

        if obs.slider.active_slider > 0.5 and not first_slider_done:
            tracing_first_slider = True
            if len(trace) < cfg.max_trace_rows:
                trace.append(
                    {
                        "time_ms": round(obs.time_ms, 3),
                        "cursor_x": round(obs.cursor_x, 3),
                        "cursor_y": round(obs.cursor_y, 3),
                        "target_x": round(obs.slider.target_x, 3),
                        "target_y": round(obs.slider.target_y, 3),
                        "distance_to_follow_target": round(obs.slider.distance_to_target, 3),
                        "slider_progress": round(obs.slider.progress, 5),
                        "inside_follow": bool(obs.slider.inside_follow > 0.5),
                        "click_down": bool(step.info.get("click_down", False)),
                        "raw_click_down": bool(step.info.get("raw_click_down", False)),
                        "slider_hold_down": bool(step.info.get("slider_hold_down", False)),
                        "follow_radius": round(obs.slider.follow_radius, 3),
                        "judgement": judgement,
                    }
                )
        elif tracing_first_slider:
            first_slider_done = True
            tracing_first_slider = False

        obs = step.observation

    payload = {
        "map": {
            "artist": beatmap.artist,
            "title": beatmap.title,
            "version": beatmap.version,
            "objects": len(beatmap.hit_objects),
        },
        "policy": "deterministic slider chase sanity policy",
        "config": asdict(cfg),
        "summary": {
            "sl_head": stats.slider_head_hits,
            "sl_follow_steps": stats.slider_follow_steps,
            "sl_fin": stats.slider_finishes,
            "sl_drop": stats.slider_drops,
            "sl_tick_hit_rate": stats.slider_tick_hit_rate,
            "sl_inside_ratio": stats.slider_inside_ratio,
            "sl_follow_dist_mean": stats.slider_follow_dist_mean,
            "sl_finish_rate": stats.slider_finish_rate,
            "sl_active_steps": stats.slider_active_steps,
        },
        "first_slider_trace": trace,
    }

    output_path = Path(cfg.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"[debug trace] {output_path}")
    print(
        "[slider sanity] "
        f"sl_head={stats.slider_head_hits} "
        f"sl_follow_steps={stats.slider_follow_steps} "
        f"sl_fin={stats.slider_finishes} "
        f"sl_drop={stats.slider_drops} "
        f"sl_tick={stats.slider_tick_hit_rate:.3f} "
        f"sl_inside_ratio={stats.slider_inside_ratio:.3f} "
        f"sl_follow_dist_mean={stats.slider_follow_dist_mean:.1f} "
        f"sl_finish_rate={stats.slider_finish_rate:.3f}"
    )


if __name__ == "__main__":
    main()
