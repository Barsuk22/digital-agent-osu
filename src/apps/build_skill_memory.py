from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from src.core.config.paths import PATHS
from src.skills.osu.parser.osu_parser import parse_beatmap
from src.skills.osu.skill_system.config import SkillExtractionConfig
from src.skills.osu.skill_system.dedup import dedup_and_merge_candidates
from src.skills.osu.skill_system.extraction import SkillExtractor, summarize_candidates
from src.skills.osu.skill_system.storage import SQLiteSkillMemoryStore, make_skill_memory_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build osu micro-skill memory from replay traces.")
    parser.add_argument("--replay", action="append", default=[], help="Replay JSON path. Can be passed multiple times.")
    parser.add_argument("--map", action="append", default=[], help="Beatmap path matching --replay. Can be passed multiple times.")
    parser.add_argument("--checkpoint-id", default=str(PATHS.phase8_easy_best_checkpoint), help="Checkpoint id/path stored in source metadata.")
    parser.add_argument("--output", default=str(PATHS.phase10_skill_memory_path), help="Output skill memory path (.sqlite or .json).")
    parser.add_argument("--export-json", default="", help="Optional debug JSON export path.")
    parser.add_argument("--merge-existing", action="store_true", help="Merge into existing skill memory instead of replacing it.")
    parser.add_argument("--min-confidence", type=float, default=0.55)
    parser.add_argument("--dedup-similarity", type=float, default=0.86)
    return parser.parse_args()


def default_inputs() -> tuple[list[str], list[str]]:
    return (
        [str(PATHS.phase8_easy_best_eval_replay)],
        [str(PATHS.phase7_eval_maps[0])],
    )


def main() -> None:
    args = parse_args()
    replay_paths = list(args.replay)
    map_paths = list(args.map)
    if not replay_paths and not map_paths:
        replay_paths, map_paths = default_inputs()

    if len(replay_paths) != len(map_paths):
        raise SystemExit("--replay and --map must have the same count")

    extraction_cfg = SkillExtractionConfig(
        min_confidence=args.min_confidence,
        dedup_similarity_threshold=args.dedup_similarity,
    )
    extractor = SkillExtractor(extraction_cfg)
    all_candidates = []
    total_rejects = Counter()

    for replay_path, map_path in zip(replay_paths, map_paths, strict=True):
        beatmap = parse_beatmap(map_path)
        candidates, report = extractor.extract_from_replay(
            beatmap=beatmap,
            replay_path=replay_path,
            checkpoint_id=args.checkpoint_id,
        )
        all_candidates.extend(candidates)
        total_rejects.update(report.reject_reasons)
        print(
            f"[source] map='{beatmap.artist} - {beatmap.title} [{beatmap.version}]' "
            f"replay={replay_path} candidates={len(candidates)} rejected={report.rejected}"
        )

    store = make_skill_memory_store(args.output)
    existing = store.load() if args.merge_existing else []
    skills, merge_stats = dedup_and_merge_candidates(
        all_candidates,
        existing_skills=existing,
        similarity_threshold=args.dedup_similarity,
    )
    store.save(skills)
    if args.export_json:
        if isinstance(store, SQLiteSkillMemoryStore):
            store.export_json(args.export_json)
        else:
            make_skill_memory_store(args.export_json).save(skills)

    by_type = Counter(skill.skill_type for skill in skills)
    avg_conf_by_type = {}
    for skill_type in by_type:
        items = [skill for skill in skills if skill.skill_type == skill_type]
        avg_conf_by_type[skill_type] = sum(skill.confidence for skill in items) / len(items)

    print(f"[saved] {Path(args.output)}")
    if args.export_json:
        print(f"[export json] {Path(args.export_json)}")
    print(
        "[summary] "
        f"candidates={len(all_candidates)} "
        f"rejected={sum(total_rejects.values())} "
        f"created={merge_stats.get('created', 0)} "
        f"merged={merge_stats.get('merged', 0)} "
        f"final={len(skills)}"
    )
    print("[final by type]")
    for skill_type, count in sorted(by_type.items()):
        print(f"  - {skill_type}: count={count} avg_conf={avg_conf_by_type[skill_type]:.3f}")
    if total_rejects:
        print("[reject reasons]")
        for reason, count in total_rejects.most_common():
            print(f"  - {reason}: {count}")
    print("[top skills]")
    for skill in sorted(skills, key=lambda item: (item.confidence, item.support_count), reverse=True)[:10]:
        print(
            f"  - {skill.skill_id} type={skill.skill_type} "
            f"conf={skill.confidence:.3f} support={skill.support_count} "
            f"source='{skill.creation_source.map_id}'"
        )


if __name__ == "__main__":
    main()
