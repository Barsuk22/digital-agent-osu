from __future__ import annotations

import argparse

from src.core.config.paths import PATHS
from src.skills.osu.skill_system.storage import make_skill_memory_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect osu skill memory.")
    parser.add_argument("--memory", default=str(PATHS.phase10_skill_memory_path))
    parser.add_argument("--type", default="")
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument("--min-support", type=int, default=1)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = make_skill_memory_store(args.memory)
    skills = store.load()
    filtered = store.filter(
        skill_type=args.type or None,
        min_confidence=args.min_confidence,
        min_support_count=args.min_support,
    )
    filtered.sort(key=lambda item: (item.confidence, item.support_count), reverse=True)

    print(f"[memory] {args.memory}")
    print(f"[skills] total={len(skills)} filtered={len(filtered)}")
    for skill in filtered[: args.limit]:
        stats = skill.success_stats
        source = skill.creation_source
        print(
            f"- {skill.skill_id} type={skill.skill_type} "
            f"conf={skill.confidence:.3f} support={skill.support_count} "
            f"uses={stats.uses} success={stats.successful_uses}/{stats.uses} "
            f"source='{source.map_id}' objs={source.object_start}-{source.object_end}"
        )
        print(
            "  applicability: "
            f"{skill.context_signature.stable_key()} "
            f"conditions={skill.applicability_conditions}"
        )
        if args.verbose:
            print(f"  features={skill.pattern_features}")
            print(f"  action={skill.action_summary}")
            print(f"  failure={skill.failure_stats}")


if __name__ == "__main__":
    main()
