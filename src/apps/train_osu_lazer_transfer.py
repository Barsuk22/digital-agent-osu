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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safe fine-tune launcher for osu!lazer transfer/generalization without touching old checkpoints."
    )
    parser.add_argument("--run-name", default="osu_lazer_transfer_generalization")
    parser.add_argument("--source-checkpoint", default=str(PATHS.phase8_easy_best_checkpoint))
    parser.add_argument("--levels", nargs="+", default=list(ALLOWED_LEVELS), choices=["beginner", "easy", "normal"])
    parser.add_argument("--updates", type=int, default=500)
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--cursor-speed", type=float, default=10.5)
    parser.add_argument("--max-maps", type=int, default=0, help="0 means use all discovered maps.")
    parser.add_argument("--maps-dir", default=str(PATHS.maps_dir))
    parser.add_argument("--map", dest="maps", action="append", default=[], help="Explicit .osu map path. Can be repeated.")
    parser.add_argument("--reset-best", action="store_true", help="Reset best metric when resuming from latest.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


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
        if not any(level in version for level in levels):
            continue

        selected.append(path)

    if max_maps > 0:
        selected = selected[:max_maps]
    return selected


def build_transfer_config(args: argparse.Namespace, train_maps: list[Path]) -> TrainConfig:
    run_dir = PATHS.runs_dir / args.run_name
    checkpoints_dir = run_dir / "checkpoints"
    logs_dir = run_dir / "logs"
    metrics_dir = run_dir / "metrics"
    replays_dir = run_dir / "replays"
    eval_dir = run_dir / "eval"

    return replace(
        TrainConfig(),
        beatmap_path=str(train_maps[0]),
        train_beatmap_paths=tuple(str(path) for path in train_maps),
        phase_name=args.run_name,
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
        best_selection_mode="train_pool_mean_v1",
    )


def print_selected_maps(train_maps: list[Path]) -> None:
    print(f"[maps] selected={len(train_maps)}")
    for index, path in enumerate(train_maps, start=1):
        beatmap = parse_beatmap(path)
        print(f"  {index:02d}. {beatmap.artist} - {beatmap.title} [{beatmap.version}]")


def main() -> None:
    args = parse_args()
    levels = tuple(dict.fromkeys(level.lower() for level in args.levels))
    if args.maps:
        train_maps = [Path(path).resolve() for path in args.maps]
    else:
        train_maps = discover_train_maps(levels=levels, max_maps=max(0, args.max_maps), maps_dir=Path(args.maps_dir))
    if not train_maps:
        raise SystemExit(f"No maps discovered for levels={levels}")

    print_selected_maps(train_maps)
    cfg = build_transfer_config(args, train_maps)

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
    resume_from_latest = latest_ckpt.exists()
    resume_ckpt = latest_ckpt if resume_from_latest else base_ckpt
    if not resume_ckpt.exists():
        raise FileNotFoundError(f"{cfg.phase_name} requires source checkpoint: {resume_ckpt}")

    start_update, best_reward = maybe_load_checkpoint(
        model,
        optimizer,
        cfg,
        resume_ckpt,
        device,
        reset_training_state=(not resume_from_latest) or args.reset_best,
    )
    if args.reset_best:
        best_reward = float("-inf")

    print("=" * 100)
    print("OSU LAZER TRANSFER FINE-TUNE STARTED")
    print(f"Phase: {cfg.phase_name}")
    print(f"Source checkpoint: {resume_ckpt}")
    print(f"Run dir: {cfg.run_dir}")
    print(f"Save latest: {latest_ckpt}")
    print(f"Save best: {best_ckpt}")
    print(f"Levels: {', '.join(levels)}")
    print(f"Maps: {len(cfg.train_beatmap_paths)}")
    print(f"Observation dim: {obs_dim}")
    print(f"Device: {device}")
    print("=" * 100)

    cycle_scores = []
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
            print_cycle_summary(cfg, cycle_idx, cycle_score, best_reward, cycle_scores)
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

        if update_idx % cfg.save_every == 0 or update_idx == start_update + 1:
            save_checkpoint(
                model=model,
                optimizer=optimizer,
                cfg=cfg,
                path=latest_ckpt,
                update_idx=update_idx,
                best_reward=best_reward,
            )

        print_concise_update(update_idx, selection_reward, stats, env, train_metrics)


if __name__ == "__main__":
    main()
