from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import torch
import torch.optim as optim

from src.apps.train_osu import (
    ActorCritic,
    RolloutBuffer,
    TrainConfig,
    build_cycle_map_score,
    build_env,
    checkpoint_selection_reward,
    cycle_selection_score,
    ensure_run_dirs,
    maybe_load_checkpoint,
    obs_to_numpy,
    ppo_update,
    print_concise_update,
    print_cycle_summary,
    run_episode,
    save_checkpoint,
    select_train_beatmap_path,
    set_seed,
)
from src.core.config.paths import PATHS
from src.skills.osu.parser.osu_parser import parse_beatmap


ALLOWED_LEVELS = ("beginner", "easy")
TRAINING_PROFILES = ("precision", "slider", "spinner", "mixed")
BLOCKED_KEYWORDS = (
    "hard",
    "insane",
    "expert",
    "extra",
    "lunatic",
    "another",
    "hyper",
    "oni",
    "sample",
)
SPINNER_TRAINING_KEYWORDS = ("spinner training", "long lesson", "phase 6 curriculum", "baby steps")
SAFE_MIN_CURSOR_SPEED = 5.0
SAFE_DEFAULT_CURSOR_SPEED = 10.5
SAFE_MIN_SAVE_EVERY = 10
SAFE_MIN_LEARNING_RATE = 3e-6
SAFE_DEFAULT_LEARNING_RATE = 1e-5
LATEST_REGRESSION_MARGIN = 2.5
EARLY_STOP_REGRESSION_MARGIN = 6.0
EARLY_STOP_BAD_CYCLES = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safe fine-tune launcher for osu!lazer transfer/generalization without touching old checkpoints."
    )
    parser.add_argument("--run-name", default="osu_lazer_transfer_generalization")
    parser.add_argument("--source-checkpoint", default=str(PATHS.phase8_easy_best_checkpoint))
    parser.add_argument("--profile", default="precision", choices=TRAINING_PROFILES)
    parser.add_argument("--levels", nargs="+", default=list(ALLOWED_LEVELS), choices=["beginner", "easy", "normal"])
    parser.add_argument("--updates", type=int, default=400)
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--cursor-speed", type=float, default=10.5)
    parser.add_argument("--max-maps", type=int, default=0, help="0 means use all discovered maps.")
    parser.add_argument("--maps-dir", default=str(PATHS.maps_dir))
    parser.add_argument("--map", dest="maps", action="append", default=[], help="Explicit .osu map path. Can be repeated.")
    parser.add_argument("--reset-best", action="store_true", help="Reset best metric when resuming from latest.")
    parser.add_argument("--resume-latest", action="store_true", help="Resume from latest instead of the protected best checkpoint.")
    parser.add_argument("--allow-spinner-training", action="store_true", help="Allow synthetic spinner-only maps in non-spinner profiles.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def apply_safety_defaults(args: argparse.Namespace) -> None:
    if args.cursor_speed < SAFE_MIN_CURSOR_SPEED:
        print(
            f"[safety] cursor-speed={args.cursor_speed:g} is too low for lazer transfer; "
            f"using {SAFE_DEFAULT_CURSOR_SPEED:g}. This is training cursor scale, not osu! sensitivity."
        )
        args.cursor_speed = SAFE_DEFAULT_CURSOR_SPEED

    if args.save_every < SAFE_MIN_SAVE_EVERY:
        print(f"[safety] save-every={args.save_every} is too aggressive; using {SAFE_MIN_SAVE_EVERY}.")
        args.save_every = SAFE_MIN_SAVE_EVERY

    if args.learning_rate < SAFE_MIN_LEARNING_RATE:
        print(
            f"[safety] learning-rate={args.learning_rate:g} is below the transfer preset; "
            f"using {SAFE_DEFAULT_LEARNING_RATE:g}."
        )
        args.learning_rate = SAFE_DEFAULT_LEARNING_RATE


def discover_train_maps(levels: tuple[str, ...], max_maps: int = 0, maps_dir: Path | None = None) -> list[Path]:
    selected: list[Path] = []
    root = maps_dir or PATHS.maps_dir
    for path in sorted(root.rglob("*.osu")):
        try:
            beatmap = parse_beatmap(path)
        except Exception:
            continue

        version = beatmap.version.lower()
        if any(blocked in version for blocked in BLOCKED_KEYWORDS):
            continue
        if is_spinner_training_map(path, beatmap.artist, beatmap.title, beatmap.version):
            continue
        if not any(level in version for level in levels):
            continue

        selected.append(path)

    if max_maps > 0:
        selected = selected[:max_maps]
    return selected


def is_spinner_training_map(path: Path, artist: str | None = None, title: str | None = None, version: str | None = None) -> bool:
    haystack = " ".join(
        value.lower()
        for value in (
            str(path),
            artist or "",
            title or "",
            version or "",
        )
    )
    return any(keyword in haystack for keyword in SPINNER_TRAINING_KEYWORDS)


def filter_maps_for_profile(args: argparse.Namespace, maps: list[Path]) -> list[Path]:
    if args.profile == "mixed" or args.allow_spinner_training:
        return maps

    filtered: list[Path] = []
    skipped_spinner: list[Path] = []
    for path in maps:
        try:
            beatmap = parse_beatmap(path)
            spinner_training = is_spinner_training_map(path, beatmap.artist, beatmap.title, beatmap.version)
        except Exception:
            spinner_training = is_spinner_training_map(path)

        if args.profile == "spinner":
            if spinner_training:
                filtered.append(path)
            else:
                skipped_spinner.append(path)
            continue

        if spinner_training:
            skipped_spinner.append(path)
            continue
        filtered.append(path)

    if skipped_spinner:
        mode = "keeping only" if args.profile == "spinner" else "excluding"
        print(f"[profile] {mode} spinner-training maps for profile={args.profile}: skipped={len(skipped_spinner)}")
    return filtered


def build_transfer_config(args: argparse.Namespace, train_maps: list[Path]) -> TrainConfig:
    run_name = args.run_name
    if args.profile == "spinner" and run_name == "osu_lazer_transfer_generalization":
        run_name = "osu_lazer_spinner_specialist"
    run_dir = PATHS.runs_dir / run_name
    checkpoints_dir = run_dir / "checkpoints"
    logs_dir = run_dir / "logs"
    metrics_dir = run_dir / "metrics"
    replays_dir = run_dir / "replays"
    eval_dir = run_dir / "eval"

    return replace(
        TrainConfig(),
        beatmap_path=str(train_maps[0]),
        train_beatmap_paths=tuple(str(path) for path in train_maps),
        phase_name=run_name,
        updates=args.updates,
        learning_rate=args.learning_rate,
        cursor_speed_scale=args.cursor_speed,
        source_checkpoint_path=str(Path(args.source_checkpoint).resolve()),
        run_dir=str(run_dir),
        checkpoint_dir=str(checkpoints_dir),
        logs_dir=str(logs_dir),
        metrics_dir=str(metrics_dir),
        replays_dir=str(replays_dir),
        eval_dir=str(eval_dir),
        latest_ckpt_name="latest_lazer_transfer.pt",
        best_ckpt_name="best_lazer_transfer.pt",
        save_every=args.save_every,
        best_selection_mode=f"lazer_transfer_{args.profile}_v2",
    )


def apply_profile_config(cfg: TrainConfig, profile: str) -> TrainConfig:
    if profile == "precision":
        return replace(
            cfg,
            entropy_coef=0.0015,
            clip_ratio=0.08,
            spinner_aux_loss_coef=0.05,
            slider_path_delta_scale=0.050,
            slider_stall_penalty=0.006,
            overspeed_penalty_scale=0.004,
            jerk_penalty_scale=0.004,
        )
    if profile == "slider":
        return replace(
            cfg,
            entropy_coef=0.002,
            clip_ratio=0.08,
            spinner_aux_loss_coef=0.05,
            slider_follow_hold_bonus=0.024,
            slider_follow_close_bonus=0.018,
            slider_path_delta_scale=0.070,
            slider_progress_scale=0.042,
            slider_stall_penalty=0.014,
            slider_finish_control_bonus=0.380,
        )
    if profile == "spinner":
        return replace(
            cfg,
            entropy_coef=0.004,
            clip_ratio=0.10,
            spinner_aux_loss_coef=0.35,
            spinner_angular_delta_scale=0.440,
            spinner_speed_bonus=0.055,
            spinner_progress_bonus=0.150,
            spinner_stall_penalty=0.070,
            spinner_direction_flip_penalty=0.030,
        )
    return cfg


def print_selected_maps(train_maps: list[Path]) -> None:
    print(f"[maps] selected={len(train_maps)}")
    for index, path in enumerate(train_maps, start=1):
        beatmap = parse_beatmap(path)
        print(f"  {index:02d}. {beatmap.artist} - {beatmap.title} [{beatmap.version}]")


def main() -> None:
    args = parse_args()
    apply_safety_defaults(args)
    levels = tuple(dict.fromkeys(level.lower() for level in args.levels))
    if args.maps:
        train_maps = [Path(path).resolve() for path in args.maps]
    else:
        train_maps = discover_train_maps(levels=levels, max_maps=max(0, args.max_maps), maps_dir=Path(args.maps_dir))
    train_maps = filter_maps_for_profile(args, train_maps)
    if not train_maps:
        raise SystemExit(f"No maps discovered for profile={args.profile} levels={levels}")

    print_selected_maps(train_maps)
    cfg = apply_profile_config(build_transfer_config(args, train_maps), args.profile)

    if args.dry_run:
        print(f"[dry-run] source checkpoint: {cfg.source_checkpoint_path}")
        print(f"[dry-run] run dir: {cfg.run_dir}")
        print(f"[dry-run] updates: {cfg.updates}")
        print(f"[dry-run] cursor speed: {cfg.cursor_speed_scale}")
        return

    set_seed(cfg.seed)
    ensure_run_dirs(cfg)

    device = torch.device(cfg.device)
    env = build_env(cfg, cfg.train_beatmap_paths[0] if cfg.train_beatmap_paths else cfg.beatmap_path)
    obs_dim = len(obs_to_numpy(env.reset()))
    model = ActorCritic(obs_dim=obs_dim, hidden_dim=cfg.hidden_dim).to(device)
    optimizer = optim.Adam(model.parameters(), lr=cfg.learning_rate)

    ckpt_dir = Path(cfg.checkpoint_dir)
    latest_ckpt = ckpt_dir / cfg.latest_ckpt_name
    best_ckpt = ckpt_dir / cfg.best_ckpt_name
    base_ckpt = Path(cfg.source_checkpoint_path)
    resume_from_latest = args.resume_latest and latest_ckpt.exists()
    resume_ckpt = latest_ckpt if resume_from_latest else best_ckpt if best_ckpt.exists() else base_ckpt
    if not resume_ckpt.exists():
        raise FileNotFoundError(f"{cfg.phase_name} requires source checkpoint: {resume_ckpt}")

    loaded_update, best_reward = maybe_load_checkpoint(
        model,
        optimizer,
        cfg,
        resume_ckpt,
        device,
        reset_training_state=False,
    )
    start_update = loaded_update if resume_from_latest else 0
    if args.reset_best:
        print("[safety] reset-best requested; best checkpoint will only be replaced by a full-cycle improvement.")
        best_reward = float("-inf")

    print("=" * 100)
    print("OSU LAZER TRANSFER FINE-TUNE STARTED")
    print(f"Phase: {cfg.phase_name}")
    print(f"Source checkpoint: {resume_ckpt}")
    print(f"Run dir: {cfg.run_dir}")
    print(f"Save latest: {latest_ckpt}")
    print(f"Save best: {best_ckpt}")
    print(f"Levels: {', '.join(levels)}")
    print(f"Profile: {args.profile}")
    print(f"Maps: {len(cfg.train_beatmap_paths)}")
    print(f"Observation dim: {obs_dim}")
    print(f"Device: {device}")
    print("=" * 100)

    cycle_scores = []
    last_cycle_score: float | None = None
    bad_cycle_streak = 0
    train_map_count = max(1, len(cfg.train_beatmap_paths))

    for update_idx in range(start_update + 1, cfg.updates + 1):
        env = build_env(cfg, select_train_beatmap_path(cfg, update_idx))
        buffer = RolloutBuffer()
        stats = run_episode(cfg, env, model, device, buffer)

        train_metrics = ppo_update(cfg, model, optimizer, buffer, device)
        selection_reward = checkpoint_selection_reward(cfg, stats, env)

        cycle_scores.append(build_cycle_map_score(cfg, update_idx, selection_reward, stats, env))
        if len(cycle_scores) >= train_map_count:
            cycle_idx = update_idx // train_map_count
            cycle_score = cycle_selection_score(cfg, cycle_scores)
            last_cycle_score = cycle_score
            print_cycle_summary(cfg, cycle_idx, cycle_score, best_reward, cycle_scores)
            if best_reward > -1e17 and cycle_score < best_reward - EARLY_STOP_REGRESSION_MARGIN:
                bad_cycle_streak += 1
                print(
                    f"[safety] severe regression cycle={cycle_score:.3f} best={best_reward:.3f} "
                    f"streak={bad_cycle_streak}/{EARLY_STOP_BAD_CYCLES}; latest will not be overwritten."
                )
            else:
                bad_cycle_streak = 0
            if cycle_score > best_reward:
                best_reward = cycle_score
                save_checkpoint(
                    model=model,
                    optimizer=optimizer,
                    cfg=cfg,
                    path=best_ckpt,
                    update_idx=update_idx,
                    best_reward=best_reward,
                )
                print(f"[best saved cycle] {best_ckpt}")
            cycle_scores.clear()
            if bad_cycle_streak >= EARLY_STOP_BAD_CYCLES:
                print("[safety] stopping training after repeated severe regression; keep/export best checkpoint.")
                break

        if update_idx % cfg.save_every == 0 or update_idx == start_update + 1:
            if last_cycle_score is None:
                print("[latest skipped] waiting for first full map cycle before saving latest.")
            elif best_reward <= -1e17 or last_cycle_score >= best_reward - LATEST_REGRESSION_MARGIN:
                save_checkpoint(
                    model=model,
                    optimizer=optimizer,
                    cfg=cfg,
                    path=latest_ckpt,
                    update_idx=update_idx,
                    best_reward=best_reward,
                )
            else:
                print(
                    f"[latest skipped] cycle score {last_cycle_score:.3f} is too far below best {best_reward:.3f}."
                )

        print_concise_update(update_idx, selection_reward, stats, env, train_metrics)


if __name__ == "__main__":
    main()
