from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import torch

from src.apps.eval_osu import ActorCritic, EvalConfig, PPOPolicy, load_model_state_compatible, obs_to_numpy, rollout_episode
from src.core.config.paths import PATHS
from src.skills.osu.env.osu_env import OsuEnv
from src.skills.osu.parser.osu_parser import parse_beatmap
from src.skills.osu.skill_system.config import SkillSelectorConfig, SkillSystemConfig
from src.skills.osu.skill_system.runtime import SkillRuntime
from src.skills.osu.skill_system.storage import make_skill_memory_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate baseline vs osu skill system.")
    parser.add_argument("--memory", default=str(PATHS.phase10_skill_memory_path))
    parser.add_argument("--checkpoint", default=str(PATHS.phase8_easy_best_checkpoint))
    parser.add_argument("--map", action="append", default=[], help="Beatmap path. Can be passed multiple times.")
    parser.add_argument("--report", default=str(PATHS.phase11_skill_eval_report_path))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--per-skill-type", action="store_true")
    parser.add_argument("--ablations", action="store_true")
    parser.add_argument("--log-runtime", action="store_true")
    return parser.parse_args()


def default_maps() -> list[str]:
    maps = list(PATHS.phase8_train_maps)
    for extra in (PATHS.yasashii_suisei_easy_map, PATHS.idol_normal_map):
        if extra.exists():
            maps.append(extra)
    return [str(path) for path in maps]


def make_env(beatmap) -> OsuEnv:
    return OsuEnv(
        beatmap=beatmap,
        dt_ms=16.6667,
        upcoming_count=5,
        cursor_speed_scale=14.0,
        click_threshold=0.75,
        slider_hold_threshold=0.45,
        spinner_hold_threshold=0.45,
    )


def stats_dict(stats) -> dict:
    return {
        "hits": stats.hits,
        "misses": stats.misses,
        "clicks": stats.total_clicks,
        "hit_rate": stats.hits / max(1, stats.hits + stats.misses),
        "timing_mean_ms": stats.timing_mean_ms,
        "timing_median_ms": stats.timing_median_ms,
        "good_timing_ratio": stats.good_timing_ratio,
        "early": stats.early_clicks,
        "late": stats.late_clicks,
        "off": stats.off_window_clicks,
        "useful_click_ratio": stats.hits / max(1, stats.total_clicks),
        "near": stats.near_click_ratio,
        "far": stats.far_click_ratio,
        "dclick": stats.mean_click_distance_px,
        "sl_inside": stats.slider_inside_ratio,
        "dpx": stats.slider_follow_distance_mean_px,
        "sl_finish": stats.slider_finish_rate,
        "sl_seg_q": stats.slider_segment_quality_mean,
        "sl_full": stats.slider_full_control_segments,
        "sl_partial": stats.slider_partial_control_segments,
        "sl_rev_follow": stats.slider_reverse_follow_ratio,
        "spin_hold": stats.spinner_hold_ratio,
        "spin_step": stats.spinner_spin_step_ratio,
        "spin_miss": stats.spinner_miss_count,
    }


def delta_dict(skill: dict, baseline: dict) -> dict:
    keys = [
        "hits",
        "misses",
        "hit_rate",
        "useful_click_ratio",
        "good_timing_ratio",
        "far",
        "dpx",
        "sl_inside",
        "sl_finish",
        "sl_seg_q",
    ]
    return {key: skill.get(key, 0.0) - baseline.get(key, 0.0) for key in keys}


def load_policy(checkpoint_path: str, device: torch.device, obs_dim: int) -> PPOPolicy:
    model = ActorCritic(obs_dim=obs_dim, hidden_dim=256).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device)
    load_model_state_compatible(model, checkpoint)
    model.eval()
    return PPOPolicy(model=model, device=device)


def run_single(beatmap_path: str, policy: PPOPolicy, cfg: EvalConfig, runtime: SkillRuntime | None) -> tuple[dict, dict | None]:
    beatmap = parse_beatmap(beatmap_path)
    env = make_env(beatmap)
    _, stats = rollout_episode(env, policy, cfg, skill_runtime=runtime)
    skill_report = None if runtime is None else asdict(runtime.report)
    result = stats_dict(stats)
    result["map"] = f"{beatmap.artist} - {beatmap.title} [{beatmap.version}]"
    return result, skill_report


def make_runtime(memory_path: str, cfg: SkillSystemConfig, skill_type: str | None = None) -> SkillRuntime:
    store = make_skill_memory_store(memory_path)
    skills = store.load()
    if skill_type is not None:
        skills = [skill for skill in skills if skill.skill_type == skill_type]
    return SkillRuntime(skills=skills, cfg=cfg)


def main() -> None:
    args = parse_args()
    map_paths = args.map or default_maps()
    device = torch.device(args.device)
    probe_map = parse_beatmap(map_paths[0])
    probe_env = make_env(probe_map)
    obs_dim = len(obs_to_numpy(probe_env.reset()))
    policy = load_policy(args.checkpoint, device, obs_dim)

    eval_cfg = EvalConfig(
        checkpoint_path=args.checkpoint,
        device=args.device,
        enable_skill_system=False,
    )

    memory_store = make_skill_memory_store(args.memory)
    skills = memory_store.load()
    skill_types = sorted({skill.skill_type for skill in skills})

    report = {
        "checkpoint": args.checkpoint,
        "memory": args.memory,
        "maps": [],
        "per_skill_type": {},
        "ablations": {},
        "summary": {},
    }

    print(f"[skill eval] maps={len(map_paths)} skills={len(skills)} memory={args.memory}")
    for beatmap_path in map_paths:
        for repeat_idx in range(args.repeat):
            baseline, _ = run_single(beatmap_path, policy, eval_cfg, runtime=None)
            runtime_cfg = SkillSystemConfig(
                enable_skill_system=True,
                skill_memory_path=args.memory,
                log_runtime=args.log_runtime,
            )
            skill_runtime = make_runtime(args.memory, runtime_cfg)
            skill_result, usage_report = run_single(beatmap_path, policy, eval_cfg, runtime=skill_runtime)
            delta = delta_dict(skill_result, baseline)
            item = {
                "repeat": repeat_idx,
                "baseline": baseline,
                "skill_system": skill_result,
                "delta": delta,
                "usage": usage_report,
            }
            report["maps"].append(item)
            print(
                f"[map] {baseline['map']} repeat={repeat_idx} "
                f"baseline_hit={baseline['hit_rate']:.3f} skill_hit={skill_result['hit_rate']:.3f} "
                f"delta_miss={delta['misses']:.1f} delta_slq={delta['sl_seg_q']:.3f} "
                f"selected={usage_report['selected'] if usage_report else 0}"
            )

    if args.per_skill_type:
        for skill_type in skill_types:
            type_items = []
            for beatmap_path in map_paths:
                baseline, _ = run_single(beatmap_path, policy, eval_cfg, runtime=None)
                runtime_cfg = SkillSystemConfig(enable_skill_system=True, skill_memory_path=args.memory)
                runtime = make_runtime(args.memory, runtime_cfg, skill_type=skill_type)
                skill_result, usage_report = run_single(beatmap_path, policy, eval_cfg, runtime=runtime)
                type_items.append(
                    {
                        "baseline": baseline,
                        "skill_system": skill_result,
                        "delta": delta_dict(skill_result, baseline),
                        "usage": usage_report,
                    }
                )
            report["per_skill_type"][skill_type] = type_items

    if args.ablations:
        ablations = {
            "no_selector_ranking": SkillSelectorConfig(enable_ranker=False),
            "no_confidence_gate": SkillSelectorConfig(enable_confidence_gate=False),
            "no_fallback": SkillSelectorConfig(enable_fallback=False),
            "no_post_use_adaptation": SkillSelectorConfig(enable_post_use_adaptation=False),
        }
        for name, selector_cfg in ablations.items():
            items = []
            for beatmap_path in map_paths:
                baseline, _ = run_single(beatmap_path, policy, eval_cfg, runtime=None)
                runtime_cfg = SkillSystemConfig(
                    enable_skill_system=True,
                    skill_memory_path=args.memory,
                    selector=selector_cfg,
                )
                runtime = make_runtime(args.memory, runtime_cfg)
                skill_result, usage_report = run_single(beatmap_path, policy, eval_cfg, runtime=runtime)
                items.append(
                    {
                        "baseline": baseline,
                        "skill_system": skill_result,
                        "delta": delta_dict(skill_result, baseline),
                        "usage": usage_report,
                    }
                )
            report["ablations"][name] = items

    selected_total = sum(item["usage"]["selected"] for item in report["maps"] if item["usage"])
    active_total = sum(item["usage"]["active_steps"] for item in report["maps"] if item["usage"])
    harmful = sum(1 for item in report["maps"] if item["delta"]["misses"] > 0 or item["delta"]["sl_seg_q"] < -0.02)
    helpful = sum(1 for item in report["maps"] if item["delta"]["misses"] < 0 or item["delta"]["sl_seg_q"] > 0.02)
    report["summary"] = {
        "runs": len(report["maps"]),
        "skill_count": len(skills),
        "skill_types": skill_types,
        "selected_total": selected_total,
        "active_steps_total": active_total,
        "helpful_run_count": helpful,
        "harmful_run_count": harmful,
    }

    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "[summary] "
        f"runs={report['summary']['runs']} selected={selected_total} active_steps={active_total} "
        f"helpful_runs={helpful} harmful_runs={harmful}"
    )
    print(f"[saved report] {output}")


if __name__ == "__main__":
    main()
