# Phase 10 / Skill Memory Init

Статус: реализована как инженерная база для извлечения и хранения micro skills.

Phase 10 добавляет первый слой памяти навыков поверх уже обученной RL policy. Навык здесь не является scripted autoplay и не заменяет policy целиком. Это компактная запись успешного локального моторного паттерна, которую можно сравнить с похожей игровой ситуацией и использовать позднее как подсказку для Phase 11.

## Стартовая точка

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Phase 9 gate report считается закрытым: checkpoint стабилен на easy/generalization pool, `Sentimental Love` больше не является 50/50 case, `Chikatto` и новый held-out easy проходят уверенно.

## Выход

```text
artifacts/runs/osu_phase10_skill_memory/memory/skill_memory.sqlite
```

JSON export для ручной отладки можно создать отдельно:

```text
artifacts/runs/osu_phase10_skill_memory/memory/skill_memory.json
```

Дополнительные рабочие директории:

```text
artifacts/runs/osu_phase10_skill_memory/logs/
artifacts/runs/osu_phase10_skill_memory/eval/
```

## Реализованные компоненты

Кодовая база:

```text
src/skills/osu/skill_system/
```

Основные модули:

- `models.py` - формальная схема `SkillEntry`, `SkillContextSignature`, `SkillSuccessStats`, `SkillExtractionCandidate`, `SkillUsageRecord`;
- `features.py` - компактные context signatures и similarity;
- `extraction.py` - извлечение кандидатов из replay/eval traces;
- `dedup.py` - similarity, dedup и merge похожих навыков;
- `storage.py` - load/save/update/filter/export skill memory;
- `config.py` - конфиги extraction, selector, executor, runtime.

## SkillEntry

Каждый навык хранит:

- `skill_id`;
- `skill_type`;
- `creation_source`;
- `context_signature`;
- `pattern_features`;
- `action_summary`;
- `applicability_conditions`;
- `success_stats`;
- `failure_stats`;
- `confidence`;
- `support_count`;
- `last_used_at`;
- `last_updated_at`;
- `tags`.

Поддержанные `skill_type`:

```text
slider_follow
reverse_slider
short_chain
spinner_control
simple_jump
simple_double
burst
triplets
kick_sliders
slider_aim
```

Phase 10 намеренно не извлекает напрямую `reading`, `accuracy`, `stamina`, `speed tapping`, `tech patterns`, `deathstream`, `flow aim`, `precision aim`, `jump chains`, `stream`. Эти категории должны появляться позже как композиции micro skills или агрегированные поведенческие характеристики.

## Extraction

Extraction проходит по локальным окнам replay и beatmap объектов. Кандидат сохраняется только если окно выглядит завершённым и качественным:

- достаточно hits;
- мало misses;
- нет грубых far clicks;
- timing drift не выглядит сломанным;
- slider/spinner специфические proxy-метрики проходят пороги;
- extraction score и confidence выше минимального порога.

Текущий extraction v1 использует replay frames и judgement-level признаки. Для slider follow он не имеет прямой истории slider ball на каждом frame, поэтому использует приближённые proxy: удержание click, near/far, локальное расстояние, hit/drop/finish и признаки окружения. Это нормально для начальной memory, но для будущей Phase 12 полезно сохранять richer trace с per-frame slider target/ball distance.

## Dedup / Merge

Навыки не копятся как тысячи одинаковых записей. При сборке:

- строится stable context key;
- считается similarity по context signature и numeric pattern features;
- похожие кандидаты merge-ятся;
- `support_count` увеличивается;
- `confidence` пересчитывается как сглаженная оценка качества.

## Build

Базовый запуск:

```powershell
python -m src.apps.build_skill_memory
```

С JSON export:

```powershell
python -m src.apps.build_skill_memory --export-json "D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase10_skill_memory\memory\skill_memory.json"
```

Явный replay/map pair:

```powershell
python -m src.apps.build_skill_memory `
  --replay "D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase8_easy_generalization\replays\best_eval_replay.json" `
  --map "D:\Projects\digital_agent_osu_project\data\raw\osu\maps\...\map.osu"
```

Несколько источников:

```powershell
python -m src.apps.build_skill_memory `
  --replay "D:\...\chikatto_eval_replay.json" --map "D:\...\chikatto.osu" `
  --replay "D:\...\sentimental_eval_replay.json" --map "D:\...\sentimental.osu" `
  --merge-existing
```

Автоматическое пополнение памяти после каждого eval:

```powershell
$env:OSU_SKILL_AUTO_EXTRACT='1'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_SKILL_AUTO_EXTRACT
```

В этом режиме `eval_osu` сохраняет replay, извлекает из него успешные локальные паттерны, dedup/merge-ит их с текущей SQLite memory и печатает `[skill_auto_extract]`.

Важно: стандартный `eval_osu` всё ещё пишет replay в один файл `best_eval_replay.json` и перезаписывает его. Для аккуратной offline multi-map memory лучше сохранять replay под отдельными именами после каждого eval или передавать в build только актуальную пару replay/map.

## Inspect

```powershell
python -m src.apps.inspect_skill_memory
```

Подробный вывод:

```powershell
python -m src.apps.inspect_skill_memory --verbose --limit 30
```

Фильтр по типу:

```powershell
python -m src.apps.inspect_skill_memory --type slider_follow --min-confidence 0.70
```

## Критерии готовности Phase 10

Phase 10 считается принятой, если:

- `skill_memory.sqlite` создаётся и загружается без ошибок;
- в memory есть не декоративные, а осмысленные записи;
- видны основные типы: `slider_follow`, `reverse_slider`, `short_chain`, `spinner_control`, `simple_jump` / `simple_double`;
- `support_count` растёт при повторном build на похожих паттернах;
- low-quality/noisy фрагменты отбрасываются;
- inspection tool показывает source, confidence, applicability и stats.

## Что смотреть

Минимальный здоровый memory report:

```text
final skills > 0
created + merged > 0
avg confidence по основным типам >= 0.60
rejected candidates есть, но они объяснены reason codes
```

Если memory быстро захламляется однотипными навыками с низким support и confidence, нужно поднять `min_confidence`, `min_extraction_score` или `dedup_similarity_threshold`.
