from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.skills.osu.skill_system.models import SCHEMA_VERSION, SkillEntry, SkillMemoryFile, utc_now_iso


class BaseSkillMemoryStore:
    path: Path
    skills: list[SkillEntry]

    def load(self) -> list[SkillEntry]:
        raise NotImplementedError

    def save(self, skills: list[SkillEntry] | None = None) -> None:
        raise NotImplementedError

    def append_or_replace(self, skill: SkillEntry) -> None:
        for idx, existing in enumerate(self.skills):
            if existing.skill_id == skill.skill_id:
                self.skills[idx] = skill
                return
        self.skills.append(skill)

    def filter(
        self,
        skill_type: str | None = None,
        min_confidence: float = 0.0,
        min_support_count: int = 1,
    ) -> list[SkillEntry]:
        result = []
        for skill in self.skills:
            if skill_type is not None and skill.skill_type != skill_type:
                continue
            if skill.confidence < min_confidence:
                continue
            if skill.support_count < min_support_count:
                continue
            result.append(skill)
        return result


class JsonSkillMemoryStore(BaseSkillMemoryStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.skills: list[SkillEntry] = []

    def load(self) -> list[SkillEntry]:
        if not self.path.exists():
            self.skills = []
            return self.skills
        memory = SkillMemoryFile.load(self.path)
        self.skills = memory.skills
        return self.skills

    def save(self, skills: list[SkillEntry] | None = None) -> None:
        if skills is not None:
            self.skills = skills
        self.path.parent.mkdir(parents=True, exist_ok=True)
        memory = SkillMemoryFile(
            schema_version=SCHEMA_VERSION,
            generated_at=utc_now_iso(),
            skills=self.skills,
        )
        self.path.write_text(memory.to_json(), encoding="utf-8")


class SQLiteSkillMemoryStore(BaseSkillMemoryStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.skills: list[SkillEntry] = []

    def load(self) -> list[SkillEntry]:
        if not self.path.exists():
            self.skills = []
            return self.skills
        self._ensure_schema()
        with self._connect() as conn:
            rows = conn.execute("select payload_json from skills order by confidence desc, support_count desc").fetchall()
        self.skills = [SkillEntry.from_dict(json.loads(row[0])) for row in rows]
        return self.skills

    def save(self, skills: list[SkillEntry] | None = None) -> None:
        if skills is not None:
            self.skills = skills
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        generated_at = utc_now_iso()
        with self._connect() as conn:
            conn.execute("delete from skills")
            conn.execute(
                "insert or replace into metadata(key, value) values(?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            conn.execute(
                "insert or replace into metadata(key, value) values(?, ?)",
                ("generated_at", generated_at),
            )
            for skill in self.skills:
                payload = json.dumps(skill.to_dict(), ensure_ascii=False)
                conn.execute(
                    """
                    insert into skills(
                        skill_id, skill_type, confidence, support_count, success_rate,
                        source_map_id, object_start, object_end, context_key,
                        last_used_at, last_updated_at, payload_json
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        skill.skill_id,
                        skill.skill_type,
                        skill.confidence,
                        skill.support_count,
                        skill.success_stats.success_rate,
                        skill.creation_source.map_id,
                        skill.creation_source.object_start,
                        skill.creation_source.object_end,
                        skill.context_signature.stable_key(),
                        skill.last_used_at,
                        skill.last_updated_at,
                        payload,
                    ),
                )

    def export_json(self, output_path: str | Path) -> None:
        skills = self.skills or self.load()
        JsonSkillMemoryStore(output_path).save(skills)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _ensure_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists metadata(
                    key text primary key,
                    value text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists skills(
                    skill_id text primary key,
                    skill_type text not null,
                    confidence real not null,
                    support_count integer not null,
                    success_rate real not null,
                    source_map_id text not null,
                    object_start integer not null,
                    object_end integer not null,
                    context_key text not null,
                    last_used_at text not null,
                    last_updated_at text not null,
                    payload_json text not null
                )
                """
            )
            conn.execute("create index if not exists idx_skills_type on skills(skill_type)")
            conn.execute("create index if not exists idx_skills_conf on skills(confidence)")
            conn.execute("create index if not exists idx_skills_context on skills(context_key)")


def make_skill_memory_store(path: str | Path) -> BaseSkillMemoryStore:
    path = Path(path)
    if path.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
        return SQLiteSkillMemoryStore(path)
    return JsonSkillMemoryStore(path)


SkillMemoryStore = JsonSkillMemoryStore
