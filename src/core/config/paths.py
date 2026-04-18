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
    def osu_phase2_timing_run_dir(self) -> Path:
        return self.runs_dir / "osu_phase2_timing"

    @property
    def osu_phase3_motion_smoothing_run_dir(self) -> Path:
        return self.runs_dir / "osu_phase3_motion_smoothing"

    @property
    def osu_phase4_slider_intro_run_dir(self) -> Path:
        return self.runs_dir / "osu_phase4_slider_follow_fix"

    @property
    def osu_phase5_slider_control_run_dir(self) -> Path:
        return self.runs_dir / "osu_phase5_slider_control"

    @property
    def checkpoints_dir(self) -> Path:
        return self.osu_phase1_run_dir / "checkpoints"

    @property
    def replays_dir(self) -> Path:
        return self.osu_phase1_run_dir / "replays"

    @property
    def phase2_checkpoints_dir(self) -> Path:
        return self.osu_phase2_timing_run_dir / "checkpoints"

    @property
    def phase2_logs_dir(self) -> Path:
        return self.osu_phase2_timing_run_dir / "logs"

    @property
    def phase2_metrics_dir(self) -> Path:
        return self.osu_phase2_timing_run_dir / "metrics"

    @property
    def phase2_replays_dir(self) -> Path:
        return self.osu_phase2_timing_run_dir / "replays"

    @property
    def phase2_eval_dir(self) -> Path:
        return self.osu_phase2_timing_run_dir / "eval"

    @property
    def phase3_smooth_checkpoints_dir(self) -> Path:
        return self.osu_phase3_motion_smoothing_run_dir / "checkpoints"

    @property
    def phase3_smooth_logs_dir(self) -> Path:
        return self.osu_phase3_motion_smoothing_run_dir / "logs"

    @property
    def phase3_smooth_metrics_dir(self) -> Path:
        return self.osu_phase3_motion_smoothing_run_dir / "metrics"

    @property
    def phase3_smooth_replays_dir(self) -> Path:
        return self.osu_phase3_motion_smoothing_run_dir / "replays"

    @property
    def phase3_smooth_eval_dir(self) -> Path:
        return self.osu_phase3_motion_smoothing_run_dir / "eval"

    @property
    def phase4_slider_checkpoints_dir(self) -> Path:
        return self.osu_phase4_slider_intro_run_dir / "checkpoints"

    @property
    def phase4_slider_logs_dir(self) -> Path:
        return self.osu_phase4_slider_intro_run_dir / "logs"

    @property
    def phase4_slider_metrics_dir(self) -> Path:
        return self.osu_phase4_slider_intro_run_dir / "metrics"

    @property
    def phase4_slider_replays_dir(self) -> Path:
        return self.osu_phase4_slider_intro_run_dir / "replays"

    @property
    def phase4_slider_eval_dir(self) -> Path:
        return self.osu_phase4_slider_intro_run_dir / "eval"

    @property
    def phase5_slider_checkpoints_dir(self) -> Path:
        return self.osu_phase5_slider_control_run_dir / "checkpoints"

    @property
    def phase5_slider_logs_dir(self) -> Path:
        return self.osu_phase5_slider_control_run_dir / "logs"

    @property
    def phase5_slider_metrics_dir(self) -> Path:
        return self.osu_phase5_slider_control_run_dir / "metrics"

    @property
    def phase5_slider_replays_dir(self) -> Path:
        return self.osu_phase5_slider_control_run_dir / "replays"

    @property
    def phase5_slider_eval_dir(self) -> Path:
        return self.osu_phase5_slider_control_run_dir / "eval"

    @property
    def latest_checkpoint(self) -> Path:
        return self.checkpoints_dir / "latest_recoil.pt"

    @property
    def best_checkpoint(self) -> Path:
        return self.checkpoints_dir / "best_recoil.pt"

    @property
    def phase2_latest_checkpoint(self) -> Path:
        return self.phase2_checkpoints_dir / "latest_timing.pt"

    @property
    def phase2_best_checkpoint(self) -> Path:
        return self.phase2_checkpoints_dir / "best_timing.pt"

    @property
    def phase3_smooth_latest_checkpoint(self) -> Path:
        return self.phase3_smooth_checkpoints_dir / "latest_smooth.pt"

    @property
    def phase3_smooth_best_checkpoint(self) -> Path:
        return self.phase3_smooth_checkpoints_dir / "best_smooth.pt"

    @property
    def phase4_slider_latest_checkpoint(self) -> Path:
        return self.phase4_slider_checkpoints_dir / "latest_slider_follow.pt"

    @property
    def phase4_slider_best_checkpoint(self) -> Path:
        return self.phase4_slider_checkpoints_dir / "best_slider_follow.pt"

    @property
    def phase5_slider_latest_checkpoint(self) -> Path:
        return self.phase5_slider_checkpoints_dir / "latest_slider_control.pt"

    @property
    def phase5_slider_best_checkpoint(self) -> Path:
        return self.phase5_slider_checkpoints_dir / "best_slider_control.pt"

    @property
    def latest_live_replay(self) -> Path:
        return self.replays_dir / "latest_live_replay.json"

    @property
    def best_eval_replay(self) -> Path:
        return self.replays_dir / "best_eval_replay.json"

    @property
    def phase2_best_eval_replay(self) -> Path:
        return self.phase2_replays_dir / "best_eval_replay.json"

    @property
    def phase3_smooth_best_eval_replay(self) -> Path:
        return self.phase3_smooth_replays_dir / "best_eval_replay.json"

    @property
    def phase4_slider_best_eval_replay(self) -> Path:
        return self.phase4_slider_replays_dir / "best_eval_replay.json"

    @property
    def phase5_slider_best_eval_replay(self) -> Path:
        return self.phase5_slider_replays_dir / "best_eval_replay.json"


PATHS = OsuPaths()
