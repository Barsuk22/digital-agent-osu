from __future__ import annotations

from pathlib import Path

from src.skills.osu.env.osu_env import OsuEnv
from src.skills.osu.parser.osu_parser import parse_beatmap
from src.skills.osu.replay.replay_io import load_replay
from src.skills.osu.viewer.pygame_viewer import OsuViewer, ViewerConfig
from src.core.config.paths import PATHS


def main() -> None:
    beatmap_path = PATHS.phase7_eval_maps[0]
    replay_path = PATHS.phase7_multimap_best_eval_replay
    if not replay_path.exists() and PATHS.spica_main_best_eval_replay.exists():
        replay_path = PATHS.spica_main_best_eval_replay
    if not replay_path.exists() and PATHS.phase6_spinner_best_eval_replay.exists():
        replay_path = PATHS.phase6_spinner_best_eval_replay
    if not replay_path.exists() and PATHS.phase5_slider_best_eval_replay.exists():
        replay_path = PATHS.phase5_slider_best_eval_replay
    if not replay_path.exists() and PATHS.phase4_slider_best_eval_replay.exists():
        replay_path = PATHS.phase4_slider_best_eval_replay
    if not replay_path.exists() and PATHS.phase3_smooth_best_eval_replay.exists():
        replay_path = PATHS.phase3_smooth_best_eval_replay
    if not replay_path.exists() and PATHS.phase2_best_eval_replay.exists():
        replay_path = PATHS.phase2_best_eval_replay
    if not replay_path.exists() and PATHS.best_eval_replay.exists():
        replay_path = PATHS.best_eval_replay

    if not replay_path.exists():
        print("[бух] replay не найден")
        print("[сделай сначала] python -m src.apps.eval_osu")
        return

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

    frames = load_replay(replay_path)
    viewer.play_replay(frames)


if __name__ == "__main__":
    main()
