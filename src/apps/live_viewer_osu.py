from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.skills.osu.env.osu_env import OsuEnv
from src.skills.osu.env.types import OsuAction
from src.skills.osu.parser.osu_parser import parse_beatmap
from src.skills.osu.replay.replay_io import save_replay
from src.skills.osu.viewer.pygame_viewer import OsuViewer, ViewerConfig
from src.core.config.paths import PATHS

@dataclass(slots=True)
class SimpleChasePolicy:
    click_time_threshold_ms: float = 55.0
    pos_gain: float = 0.06
    click_distance_threshold: float = 52.0

    def __call__(self, obs) -> OsuAction:
        target = None
        for item in obs.upcoming:
            if item.kind_id != -1:
                target = item
                break

        if target is None:
            return OsuAction(dx=0.0, dy=0.0, click_strength=0.0)

        dx = (target.x - obs.cursor_x) * self.pos_gain
        dy = (target.y - obs.cursor_y) * self.pos_gain

        dx = max(-1.0, min(1.0, dx))
        dy = max(-1.0, min(1.0, dy))

        should_click = (
            abs(target.time_to_hit_ms) <= self.click_time_threshold_ms
            and target.distance_to_cursor <= self.click_distance_threshold
        )

        click_strength = 1.0 if should_click else 0.0
        return OsuAction(dx=dx, dy=dy, click_strength=click_strength)


def main() -> None:
    beatmap_path = PATHS.active_map

    beatmap = parse_beatmap(beatmap_path)

    env = OsuEnv(
        beatmap=beatmap,
        dt_ms=16.6667,
        upcoming_count=5,
        cursor_speed_scale=14.0,
        click_threshold=0.75,
    )

    viewer = OsuViewer(
        env,
        ViewerConfig(
            window_width=1600,
            window_height=900,
            fps=60,
            background_dim_alpha=150,
            playfield_pad_x=80,
            playfield_pad_y=60,
        ),
    )

    policy = SimpleChasePolicy()
    viewer.run(policy)

    replay_path = PATHS.latest_live_replay
    save_replay(env.replay_frames, replay_path)
    print(f"[saved replay] {replay_path}")


if __name__ == "__main__":
    main()