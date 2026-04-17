from __future__ import annotations

from pathlib import Path

from src.skills.osu.env.osu_env import OsuEnv
from src.skills.osu.parser.osu_parser import parse_beatmap
from src.skills.osu.replay.replay_io import load_replay
from src.skills.osu.viewer.pygame_viewer import OsuViewer, ViewerConfig


def main() -> None:
    beatmap_path = (
        r"D:\Projects\digital_agent_osu_project\data\raw\osu\maps\StylipS - Spica"
        r"\StylipS - Spica. (TV-size) (Lanturn) [Easy-ka].osu"
    )

    replay_path = Path(
        r"D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase1_ppo\replays\latest_live_replay.json"
    )

    beatmap = parse_beatmap(beatmap_path)
    env = OsuEnv(beatmap=beatmap)

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