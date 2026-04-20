from __future__ import annotations

import hashlib
from collections import defaultdict

from src.skills.osu.skill_system.features import signature_similarity
from src.skills.osu.skill_system.models import SkillEntry, SkillExtractionCandidate, utc_now_iso


def skill_id_for(candidate: SkillExtractionCandidate) -> str:
    raw = "|".join(
        [
            candidate.skill_type,
            candidate.context_signature.stable_key(),
            candidate.creation_source.map_id,
            str(candidate.creation_source.object_start),
            str(candidate.creation_source.object_end),
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{candidate.skill_type}_{digest}"


def numeric_feature_similarity(a: dict, b: dict) -> float:
    shared = [key for key in a.keys() & b.keys() if isinstance(a[key], (int, float)) and isinstance(b[key], (int, float))]
    if not shared:
        return 0.5
    sims = []
    for key in shared:
        left = float(a[key])
        right = float(b[key])
        scale = max(abs(left), abs(right), 1.0)
        sims.append(max(0.0, 1.0 - abs(left - right) / scale))
    return sum(sims) / len(sims)


def skill_similarity(skill: SkillEntry, candidate: SkillExtractionCandidate) -> float:
    if skill.skill_type != candidate.skill_type:
        return 0.0
    sig_sim = signature_similarity(skill.context_signature, candidate.context_signature)
    feature_sim = numeric_feature_similarity(skill.pattern_features, candidate.pattern_features)
    return 0.72 * sig_sim + 0.28 * feature_sim


def merge_candidate_into_skill(skill: SkillEntry, candidate: SkillExtractionCandidate) -> SkillEntry:
    old_support = skill.support_count
    new_support = old_support + 1
    weight_old = old_support / new_support
    weight_new = 1.0 / new_support

    for key, value in candidate.pattern_features.items():
        if isinstance(value, (int, float)) and isinstance(skill.pattern_features.get(key), (int, float)):
            skill.pattern_features[key] = float(skill.pattern_features[key]) * weight_old + float(value) * weight_new
        else:
            skill.pattern_features.setdefault(key, value)

    for key, value in candidate.action_summary.items():
        if isinstance(value, (int, float)) and isinstance(skill.action_summary.get(key), (int, float)):
            skill.action_summary[key] = float(skill.action_summary[key]) * weight_old + float(value) * weight_new
        else:
            skill.action_summary.setdefault(key, value)

    skill.confidence = max(0.0, min(1.0, skill.confidence * weight_old + candidate.confidence * weight_new + 0.015))
    skill.support_count = new_support
    skill.last_updated_at = utc_now_iso()
    for tag in candidate.tags:
        if tag not in skill.tags:
            skill.tags.append(tag)
    return skill


def dedup_and_merge_candidates(
    candidates: list[SkillExtractionCandidate],
    existing_skills: list[SkillEntry] | None = None,
    similarity_threshold: float = 0.86,
) -> tuple[list[SkillEntry], dict[str, int]]:
    skills = list(existing_skills or [])
    stats = defaultdict(int)

    for candidate in candidates:
        best_idx = -1
        best_similarity = 0.0
        for idx, skill in enumerate(skills):
            sim = skill_similarity(skill, candidate)
            if sim > best_similarity:
                best_similarity = sim
                best_idx = idx

        if best_idx >= 0 and best_similarity >= similarity_threshold:
            skills[best_idx] = merge_candidate_into_skill(skills[best_idx], candidate)
            stats["merged"] += 1
        else:
            skills.append(candidate.to_entry(skill_id_for(candidate)))
            stats["created"] += 1

    stats["final"] = len(skills)
    return skills, dict(stats)
