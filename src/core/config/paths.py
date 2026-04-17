from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()

    for path in [current, *current.parents]:
        if (path / "src").exists() and (path / "configs").exists():
            return path

    raise RuntimeError("Project root not found")


PROJECT_ROOT = find_project_root()


@dataclass(frozen=True, slots=True)
class OsuPaths:
    project_root: Path = PROJECT_ROOT

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def artifacts_dir(self) -> Path:
        return self.project_root / "artifacts"

    @property
    def maps_dir(self) -> Path:
        return self.raw_dir / "osu" / "maps"

    @property
    def spica_dir(self) -> Path:
        return self.maps_dir / "StylipS - Spica"

    @property
    def easy_ka_map(self) -> Path:
        return self.spica_dir / "StylipS - Spica. (TV-size) (Lanturn) [Easy-ka].osu"

    @property
    def beginner_ka_map(self) -> Path:
        return self.spica_dir / "StylipS - Spica. (TV-size) (Lanturn) [Beginner-ka].osu"

    @property
    def sentiment_dir(self) -> Path:
        return self.maps_dir / "Sati Akura - Sentimental Love"

    @property
    def sentiment_easy_map(self) -> Path:
        return self.sentiment_dir / "Sati Akura - Sentimental Love (TV Size) (Nao Tomori) [Myxo's Easy].osu"

    @property
    def active_map(self) -> Path:
        return self.easy_ka_map
        # return self.beginner_ka_map
        # return self.sentiment_easy_map

    @property
    def runs_dir(self) -> Path:
        return self.artifacts_dir / "runs"

    @property
    def osu_phase1_run_dir(self) -> Path:
        return self.runs_dir / "osu_phase1_ppo"

    @property
    def checkpoints_dir(self) -> Path:
        return self.osu_phase1_run_dir / "checkpoints"

    @property
    def replays_dir(self) -> Path:
        return self.osu_phase1_run_dir / "replays"

    @property
    def latest_checkpoint(self) -> Path:
        return self.checkpoints_dir / "latest.pt"

    @property
    def best_checkpoint(self) -> Path:
        return self.checkpoints_dir / "best.pt"

    @property
    def latest_live_replay(self) -> Path:
        return self.replays_dir / "latest_live_replay.json"

    @property
    def best_eval_replay(self) -> Path:
        return self.replays_dir / "best_eval_replay.json"


PATHS = OsuPaths()