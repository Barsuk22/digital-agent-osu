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
    def suzuki_dame_dir(self) -> Path:
        return self.maps_dir / "Suzuki Minori - Dame wa Dame"

    @property
    def suzuki_dame_beginner_map(self) -> Path:
        return self.suzuki_dame_dir / "Suzuki Minori - Dame wa Dame (TV Size) (chapter) [maikayuii's Beginner].osu"

    @property
    def miminari_itowanai_dir(self) -> Path:
        return self.maps_dir / "MIMiNARI - Itowanai feat. Tomita Miyu, Ichinose Kana"

    @property
    def miminari_itowanai_easy_map(self) -> Path:
        return (
            self.miminari_itowanai_dir
            / "MIMiNARI - Itowanai feat. Tomita Miyu, Ichinose Kana (TV Size) (Pata-Mon) [Teages's Easy].osu"
        )

    @property
    def noa_megane_dir(self) -> Path:
        return self.maps_dir / "noa - Megane o Hazushite"

    @property
    def noa_megane_easy_map(self) -> Path:
        return self.noa_megane_dir / "noa - Megane o Hazushite (TV Size) (Pata-Mon) [Easy].osu"

    @property
    def onmyo_kouga_dir(self) -> Path:
        return self.maps_dir / "ONMYO-ZA - Kouga Ninpouchou"

    @property
    def onmyo_kouga_easy_map(self) -> Path:
        return self.onmyo_kouga_dir / "ONMYO-ZA - Kouga Ninpouchou (App) [JauiPlaY's Easy].osu"

    @property
    def sentiment_dir(self) -> Path:
        return self.maps_dir / "Sati Akura - Sentimental Love"

    @property
    def sentiment_easy_map(self) -> Path:
        return self.sentiment_dir / "Sati Akura - Sentimental Love (TV Size) (Nao Tomori) [Myxo's Easy].osu"

    @property
    def chikatto_dir(self) -> Path:
        return self.maps_dir / "Sati Akura - Chikatto Chika Chika"

    @property
    def chikatto_easy_map(self) -> Path:
        return self.chikatto_dir / "Sati Akura - Chikatto Chika Chika (-Mikan) [Easy].osu"

    @property
    def animal_dir(self) -> Path:
        return self.maps_dir / "Sati Akura - Animal"

    @property
    def animal_hard_map(self) -> Path:
        return self.animal_dir / "Sati Akura - Animal (AltheaFran) [Even if it's ugly, that's the way I want it.].osu"

    @property
    def internet_yamero_dir(self) -> Path:
        return self.maps_dir / "Sati Akura - INTERNET YAMERO"

    @property
    def internet_yamero_easy_map(self) -> Path:
        return self.internet_yamero_dir / "Sati Akura - INTERNET YAMERO (BAN BLAT) [Easy].osu"

    @property
    def yasashii_suisei_dir(self) -> Path:
        return self.maps_dir / "YOASOBI - Yasashii Suisei"

    @property
    def yasashii_suisei_easy_map(self) -> Path:
        return self.yasashii_suisei_dir / "YOASOBI - Yasashii Suisei (TV Size) (Tighnari) [Kyouren's Easy].osu"

    @property
    def idol_dir(self) -> Path:
        return self.maps_dir / "Sati Akura - IDOL"

    @property
    def idol_normal_map(self) -> Path:
        return self.idol_dir / "YOASOBI feat. Sati Akura - Idol feat. Sati Akura (CREEPO4EK) [(Normal)].osu"

    @property
    def phase7_train_maps(self) -> tuple[Path, ...]:
        return (
            self.beginner_ka_map,
            self.suzuki_dame_beginner_map,
            self.miminari_itowanai_easy_map,
            self.noa_megane_easy_map,
            self.onmyo_kouga_easy_map,
        )

    @property
    def phase8_train_maps(self) -> tuple[Path, ...]:
        return (
            self.beginner_ka_map,
            self.suzuki_dame_beginner_map,
            self.miminari_itowanai_easy_map,
            self.noa_megane_easy_map,
            self.onmyo_kouga_easy_map,
            self.sentiment_easy_map,
            self.chikatto_easy_map,
        )

    @property
    def phase8_stress_eval_maps(self) -> tuple[Path, ...]:
        return (
            self.internet_yamero_easy_map,
            self.animal_hard_map,
        )

    @property
    def phase7_eval_maps(self) -> tuple[Path, ...]:
        return (
            # self.chikatto_easy_map,
            # self.sentiment_easy_map,
            # self.beginner_ka_map,
            # self.suzuki_dame_beginner_map,
            # self.miminari_itowanai_easy_map,
            # self.noa_megane_easy_map,
            # self.onmyo_kouga_easy_map,
            # self.yasashii_suisei_easy_map,
            self.animal_hard_map,
            # self.internet_yamero_easy_map,
            # self.idol_normal_map,
        )

    @property
    def spinner_training_dir(self) -> Path:
        return self.maps_dir / "Spinner Training"

    @property
    def phase6_spinner_curriculum_map(self) -> Path:
        return self.spinner_training_dir / "You - Spinner Training [Phase 6 Curriculum].osu"

    @property
    def active_map(self) -> Path:
        # return self.easy_ka_map
        return self.beginner_ka_map
        # return self.sentiment_easy_map
        # return self.phase6_spinner_curriculum_map

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
    def osu_phase6_spinner_control_run_dir(self) -> Path:
        return self.runs_dir / "osu_phase6_spinner_control"

    @property
    def osu_spica_main_finetune_run_dir(self) -> Path:
        return self.runs_dir / "osu_spica_main_finetune"

    @property
    def osu_phase7_multimap_run_dir(self) -> Path:
        return self.runs_dir / "osu_phase7_multimap_generalization"

    @property
    def osu_phase8_easy_generalization_run_dir(self) -> Path:
        return self.runs_dir / "osu_phase8_easy_generalization"

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
    def phase6_spinner_checkpoints_dir(self) -> Path:
        return self.osu_phase6_spinner_control_run_dir / "checkpoints"

    @property
    def phase6_spinner_logs_dir(self) -> Path:
        return self.osu_phase6_spinner_control_run_dir / "logs"

    @property
    def phase6_spinner_metrics_dir(self) -> Path:
        return self.osu_phase6_spinner_control_run_dir / "metrics"

    @property
    def phase6_spinner_replays_dir(self) -> Path:
        return self.osu_phase6_spinner_control_run_dir / "replays"

    @property
    def phase6_spinner_eval_dir(self) -> Path:
        return self.osu_phase6_spinner_control_run_dir / "eval"

    @property
    def spica_main_checkpoints_dir(self) -> Path:
        return self.osu_spica_main_finetune_run_dir / "checkpoints"

    @property
    def spica_main_logs_dir(self) -> Path:
        return self.osu_spica_main_finetune_run_dir / "logs"

    @property
    def spica_main_metrics_dir(self) -> Path:
        return self.osu_spica_main_finetune_run_dir / "metrics"

    @property
    def spica_main_replays_dir(self) -> Path:
        return self.osu_spica_main_finetune_run_dir / "replays"

    @property
    def spica_main_eval_dir(self) -> Path:
        return self.osu_spica_main_finetune_run_dir / "eval"

    @property
    def phase7_multimap_checkpoints_dir(self) -> Path:
        return self.osu_phase7_multimap_run_dir / "checkpoints"

    @property
    def phase7_multimap_logs_dir(self) -> Path:
        return self.osu_phase7_multimap_run_dir / "logs"

    @property
    def phase7_multimap_metrics_dir(self) -> Path:
        return self.osu_phase7_multimap_run_dir / "metrics"

    @property
    def phase7_multimap_replays_dir(self) -> Path:
        return self.osu_phase7_multimap_run_dir / "replays"

    @property
    def phase7_multimap_eval_dir(self) -> Path:
        return self.osu_phase7_multimap_run_dir / "eval"

    @property
    def phase8_easy_checkpoints_dir(self) -> Path:
        return self.osu_phase8_easy_generalization_run_dir / "checkpoints"

    @property
    def phase8_easy_logs_dir(self) -> Path:
        return self.osu_phase8_easy_generalization_run_dir / "logs"

    @property
    def phase8_easy_metrics_dir(self) -> Path:
        return self.osu_phase8_easy_generalization_run_dir / "metrics"

    @property
    def phase8_easy_replays_dir(self) -> Path:
        return self.osu_phase8_easy_generalization_run_dir / "replays"

    @property
    def phase8_easy_eval_dir(self) -> Path:
        return self.osu_phase8_easy_generalization_run_dir / "eval"

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
    def phase6_spinner_latest_checkpoint(self) -> Path:
        return self.phase6_spinner_checkpoints_dir / "latest_spinner_control.pt"

    @property
    def phase6_spinner_best_checkpoint(self) -> Path:
        return self.phase6_spinner_checkpoints_dir / "best_spinner_control.pt"

    @property
    def spica_main_latest_checkpoint(self) -> Path:
        return self.spica_main_checkpoints_dir / "latest_spica_main.pt"

    @property
    def spica_main_best_checkpoint(self) -> Path:
        return self.spica_main_checkpoints_dir / "best_spica_main.pt"

    @property
    def spica_main_golden_checkpoint(self) -> Path:
        return self.spica_main_checkpoints_dir / "golden_spica_main.pt"

    @property
    def phase7_multimap_latest_checkpoint(self) -> Path:
        return self.phase7_multimap_checkpoints_dir / "latest_multimap.pt"

    @property
    def phase7_multimap_best_checkpoint(self) -> Path:
        return self.phase7_multimap_checkpoints_dir / "best_multimap.pt"

    @property
    def phase8_easy_latest_checkpoint(self) -> Path:
        return self.phase8_easy_checkpoints_dir / "latest_easy_generalization.pt"

    @property
    def phase8_easy_best_checkpoint(self) -> Path:
        return self.phase8_easy_checkpoints_dir / "best_easy_generalization.pt"

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

    @property
    def phase6_spinner_best_eval_replay(self) -> Path:
        return self.phase6_spinner_replays_dir / "best_eval_replay.json"

    @property
    def spica_main_best_eval_replay(self) -> Path:
        return self.spica_main_replays_dir / "best_eval_replay.json"

    @property
    def phase7_multimap_best_eval_replay(self) -> Path:
        return self.phase7_multimap_replays_dir / "best_eval_replay.json"

    @property
    def phase8_easy_best_eval_replay(self) -> Path:
        return self.phase8_easy_replays_dir / "best_eval_replay.json"


PATHS = OsuPaths()
