from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from src.skills.osu.domain.models import (
    CircleObject,
    DifficultySettings,
    HitObject,
    HitObjectType,
    ParsedBeatmap,
    SliderObject,
    TimingPoint,
)
from src.skills.osu.env.types import OsuAction, OsuObservation, SliderStateView, SpinnerStateView, UpcomingObjectView
from src.skills.osu.replay.replay_io import save_replay
from src.skills.osu.skill_system.config import SkillExtractionConfig, SkillSelectorConfig
from src.skills.osu.skill_system.dedup import dedup_and_merge_candidates
from src.skills.osu.skill_system.executor import SkillExecutor
from src.skills.osu.skill_system.extraction import SkillExtractor
from src.skills.osu.skill_system.matcher import SkillMatcher
from src.skills.osu.skill_system.models import SkillExtractionCandidate
from src.skills.osu.skill_system.ranker import SkillRanker
from src.skills.osu.skill_system.selector import SkillSelector
from src.skills.osu.skill_system.storage import make_skill_memory_store
from src.skills.osu.viewer.replay_models import ReplayFrame


def make_beatmap() -> ParsedBeatmap:
    objects = [
        HitObject(
            kind=HitObjectType.CIRCLE,
            circle=CircleObject(x=100.0, y=100.0, time_ms=1000.0, combo_index=0, combo_number=1, hitsound=0),
        ),
        HitObject(
            kind=HitObjectType.CIRCLE,
            circle=CircleObject(x=180.0, y=120.0, time_ms=1200.0, combo_index=1, combo_number=1, hitsound=0),
        ),
        HitObject(
            kind=HitObjectType.SLIDER,
            slider=SliderObject(
                x=220.0,
                y=160.0,
                time_ms=1500.0,
                combo_index=2,
                combo_number=1,
                hitsound=0,
                curve_type="L",
                control_points=[(220.0, 160.0), (300.0, 180.0)],
                repeats=2,
                pixel_length=160.0,
            ),
        ),
    ]
    return ParsedBeatmap(
        beatmap_path=Path("synthetic.osu"),
        beatmap_dir=Path("."),
        audio_filename="",
        audio_path=None,
        background_filename=None,
        background_path=None,
        video_filename=None,
        video_path=None,
        video_start_time_ms=0.0,
        title="Synthetic",
        artist="Unit",
        version="Easy",
        difficulty=DifficultySettings(hp=5.0, cs=4.0, od=5.0, ar=5.0, slider_multiplier=1.4, slider_tick_rate=1.0),
        timing_points=[
            TimingPoint(0.0, 500.0, 4, 1, 0, 80, True, 0),
            TimingPoint(0.0, -100.0, 4, 1, 0, 80, False, 0),
        ],
        hit_objects=objects,
    )


def make_replay_frames() -> list[ReplayFrame]:
    frames = []
    for idx, time_ms in enumerate(range(900, 1850, 50)):
        if time_ms < 1100:
            x, y = 100.0, 100.0
        elif time_ms < 1350:
            x, y = 180.0, 120.0
        else:
            x, y = 230.0 + (idx % 4) * 8.0, 162.0 + (idx % 3) * 4.0
        judgement = "none"
        score = 0
        if time_ms == 1000:
            judgement = "hit300"
            score = 300
        elif time_ms == 1200:
            judgement = "hit300"
            score = 300
        elif time_ms == 1500:
            judgement = "slider_head"
            score = 30
        elif time_ms == 1750:
            judgement = "slider_finish"
            score = 300
        frames.append(
            ReplayFrame(
                time_ms=float(time_ms),
                cursor_x=x,
                cursor_y=y,
                click_down=950 <= time_ms <= 1780,
                judgement=judgement,
                combo=idx,
                accuracy=1.0,
                score_value=score,
            )
        )
    return frames


def test_extractor_finds_valid_patterns_and_rejects_noise() -> None:
    beatmap = make_beatmap()
    frames = make_replay_frames()
    with TemporaryDirectory() as tmp:
        replay_path = Path(tmp) / "replay.json"
        save_replay(frames, replay_path)
        extractor = SkillExtractor(SkillExtractionConfig(min_confidence=0.35, min_extraction_score=0.35))
        candidates, report = extractor.extract_from_replay(beatmap, replay_path, checkpoint_id="unit")

    assert candidates
    assert report.candidates_found == len(candidates)
    assert any(candidate.skill_type == "slider_follow" for candidate in candidates)
    assert any(candidate.confidence > 0.35 for candidate in candidates)


def test_dedup_merges_similar_candidates() -> None:
    beatmap = make_beatmap()
    frames = make_replay_frames()
    extractor = SkillExtractor(SkillExtractionConfig(min_confidence=0.35, min_extraction_score=0.35))
    candidates, _ = extractor.extract_from_frames(beatmap, frames, replay_id="unit", checkpoint_id="unit")
    slider_candidates = [item for item in candidates if item.skill_type == "slider_follow"]
    assert len(slider_candidates) >= 1

    skills, stats = dedup_and_merge_candidates([slider_candidates[0], slider_candidates[0]], similarity_threshold=0.80)
    assert len(skills) == 1
    assert skills[0].support_count == 2
    assert stats["merged"] == 1


def test_sqlite_skill_memory_roundtrip() -> None:
    beatmap = make_beatmap()
    frames = make_replay_frames()
    extractor = SkillExtractor(SkillExtractionConfig(min_confidence=0.35, min_extraction_score=0.35))
    candidates, _ = extractor.extract_from_frames(beatmap, frames, replay_id="unit", checkpoint_id="unit")
    skills, _ = dedup_and_merge_candidates(candidates, similarity_threshold=0.80)
    assert skills

    with TemporaryDirectory() as tmp:
        memory_path = Path(tmp) / "skill_memory.sqlite"
        store = make_skill_memory_store(memory_path)
        store.save(skills)
        loaded = store.load()

    assert len(loaded) == len(skills)
    assert loaded[0].skill_id == skills[0].skill_id


def make_obs(kind_id: int = 1) -> OsuObservation:
    return OsuObservation(
        time_ms=1000.0,
        cursor_x=210.0,
        cursor_y=150.0,
        upcoming=[
            UpcomingObjectView(kind_id=kind_id, x=230.0, y=160.0, time_to_hit_ms=120.0, distance_to_cursor=24.0, is_active=1.0),
            UpcomingObjectView(kind_id=-1, x=0.0, y=0.0, time_to_hit_ms=0.0, distance_to_cursor=0.0, is_active=0.0),
        ],
        slider=SliderStateView(
            active_slider=1.0 if kind_id == 1 else 0.0,
            primary_is_slider=1.0 if kind_id == 1 else 0.0,
            progress=0.4,
            target_x=235.0,
            target_y=165.0,
            distance_to_target=30.0,
            distance_to_ball=30.0,
            inside_follow=1.0,
            head_hit=1.0,
            time_to_end_ms=400.0,
            tangent_x=1.0,
            tangent_y=0.0,
            follow_radius=80.0,
        ),
        spinner=SpinnerStateView(
            active_spinner=0.0,
            primary_is_spinner=0.0,
            progress=0.0,
            spins=0.0,
            target_spins=2.0,
            time_to_end_ms=0.0,
            center_x=256.0,
            center_y=192.0,
            distance_to_center=70.0,
            radius_error=6.0,
            angle_sin=0.0,
            angle_cos=1.0,
            angular_velocity=0.0,
        ),
    )


def test_matcher_ranker_selector_and_executor_keep_fallback_available() -> None:
    beatmap = make_beatmap()
    frames = make_replay_frames()
    extractor = SkillExtractor(SkillExtractionConfig(min_confidence=0.35, min_extraction_score=0.35))
    candidates, _ = extractor.extract_from_frames(beatmap, frames, replay_id="unit", checkpoint_id="unit")
    skills, _ = dedup_and_merge_candidates(candidates, similarity_threshold=0.80)
    skill = next(item for item in skills if item.skill_type == "slider_follow")
    skill.confidence = 0.9
    skill.support_count = 5

    obs = make_obs(kind_id=1)
    matcher = SkillMatcher([skill])
    matches = matcher.match(obs)
    assert matches[0].applicable
    assert matches[0].similarity > 0.0

    ranker = SkillRanker()
    ranked = ranker.rank(matches, obs)
    assert ranked[0].rank_score > 0.0

    selector = SkillSelector(SkillSelectorConfig(min_similarity=0.1, min_confidence=0.1))
    selection = selector.select(ranked, obs.time_ms)
    assert selection.selected is not None

    executor = SkillExecutor()
    executor.maybe_start(selection.selected, obs.time_ms)
    result = executor.apply(obs, OsuAction(dx=0.0, dy=0.0, click_strength=0.2))
    assert result.event in {"active", "end"}
    assert result.action.click_strength >= 0.2

    bad_obs = make_obs(kind_id=1)
    bad_obs.slider.distance_to_target = 200.0
    bad_result = executor.apply(bad_obs, OsuAction(dx=0.0, dy=0.0, click_strength=0.2))
    assert bad_result.event in {"abort", "baseline"}
