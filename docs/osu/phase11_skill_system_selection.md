# Phase 11 / Skill System + Selection

Статус: реализована как опциональный runtime-слой поверх baseline RL policy.

Phase 11 использует skill memory во время игры. Система не выключает policy и не превращает агента в scripted autoplay. Baseline policy остаётся главным мотором, а skill layer даёт короткое локальное смещение действия, если текущий context достаточно похож на сохранённый успешный micro skill.

## Архитектура

Runtime pipeline:

```text
baseline policy action
        |
        v
runtime context descriptor
        |
        v
SkillMatcher -> SkillRanker -> SkillSelector
        |
        v
SkillExecutor local bias / fallback
        |
        v
final action
```

Код:

```text
src/skills/osu/skill_system/matcher.py
src/skills/osu/skill_system/ranker.py
src/skills/osu/skill_system/selector.py
src/skills/osu/skill_system/executor.py
src/skills/osu/skill_system/runtime.py
```

## Matcher

`SkillMatcher` строит runtime context descriptor из `OsuObservation` и ищет похожие `SkillEntry`.

Сравниваются:

- object sequence type;
- object count;
- spacing bucket;
- angle bucket;
- density bucket;
- bpm bucket;
- slider length bucket;
- reverse count;
- active slider/spinner state;
- local difficulty proxy.

На выходе:

- candidate skill;
- similarity score;
- applicability flags;
- reason codes.

## Ranker

`SkillRanker` учитывает не только similarity:

- confidence;
- support_count;
- recent success rate;
- expected gain;
- local risk;
- type compatibility;
- scene mismatch penalty;
- overuse penalty.

Режим ablation `no_selector_ranking` сохраняет matcher/selector, но заменяет rank score на raw similarity. Это позволяет честно проверить, даёт ли ранжирование пользу.

## Selector

`SkillSelector` решает:

- использовать навык;
- отказаться от навыка;
- выбрать один из конфликтующих кандидатов;
- удержать cooldown / anti-spam.

Основные gates:

- minimum similarity;
- minimum confidence;
- maximum risk;
- cooldown;
- per-type overuse limit.

Selector обязан уметь сказать “нет”. Это важнее, чем использовать skill любой ценой.

## Executor

`SkillExecutor` применяет навык только локально.

Он поддерживает:

- start condition;
- bounded execution window;
- hold/continue condition;
- abort condition;
- end condition;
- fallback на baseline action.

Исполнение сделано как `assist_bias`, а не как длинный hard override:

- slider skills мягко смещают action к slider target;
- spinner skills помогают удерживать стабильный tangent/radius;
- jump/chain skills добавляют короткий motion/click prior;
- baseline action всегда остаётся доступным fallback.

## Post-Use Evaluation

После runtime шага `SkillRuntime.post_step` обновляет confidence и usage stats:

- use count;
- success/failure;
- confidence before/after;
- slider quality delta;
- fallback flag;
- local reason.

Полная честная оценка baseline-vs-skill выполняется отдельным report script, потому что один runtime шаг не знает counterfactual baseline outcome.

## Интеграция в eval_osu

Baseline eval:

```powershell
python -m src.apps.eval_osu
```

Eval с skill system:

```powershell
$env:OSU_ENABLE_SKILL_SYSTEM='1'
$env:OSU_SKILL_MEMORY_PATH='D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase10_skill_memory\memory\skill_memory.sqlite'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_ENABLE_SKILL_SYSTEM
Remove-Item Env:\OSU_SKILL_MEMORY_PATH
```

С runtime debug log:

```powershell
$env:OSU_ENABLE_SKILL_SYSTEM='1'
$env:OSU_SKILL_RUNTIME_LOG='1'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_ENABLE_SKILL_SYSTEM
Remove-Item Env:\OSU_SKILL_RUNTIME_LOG
```

Eval с автоматическим пополнением памяти после игры:

```powershell
$env:OSU_SKILL_AUTO_EXTRACT='1'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_SKILL_AUTO_EXTRACT
```

Eval с включённой skill system и сохранением runtime confidence/stat updates:

```powershell
$env:OSU_ENABLE_SKILL_SYSTEM='1'
$env:OSU_SKILL_SAVE_RUNTIME_STATS='1'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_ENABLE_SKILL_SYSTEM
Remove-Item Env:\OSU_SKILL_SAVE_RUNTIME_STATS
```

## Full Skill Eval

Общий report:

```powershell
python -m src.apps.eval_skill_system --repeat 3
```

Per-skill-type и ablations:

```powershell
python -m src.apps.eval_skill_system --repeat 3 --per-skill-type --ablations
```

Явные карты:

```powershell
python -m src.apps.eval_skill_system `
  --map "D:\Projects\digital_agent_osu_project\data\raw\osu\maps\...\easy.osu" `
  --map "D:\Projects\digital_agent_osu_project\data\raw\osu\maps\...\normal.osu" `
  --repeat 3 --per-skill-type --ablations
```

Report сохраняется сюда:

```text
artifacts/runs/osu_phase10_skill_memory/eval/skill_system_eval_report.json
```

## Eval режимы

`eval_skill_system.py` сравнивает:

- baseline only;
- baseline + full skill system;
- per-skill-type runtime;
- ablations:
  - `no_selector_ranking`;
  - `no_confidence_gate`;
  - `no_fallback`;
  - `no_post_use_adaptation`.

## Метрики принятия

Смотреть:

- hit rate;
- misses;
- useful click ratio;
- timing mean/median/good ratio;
- near/far clicks;
- `dpx`;
- `sl_inside`;
- `sl_finish`;
- `sl_seg_q`;
- `sl_rev_follow`;
- spinner stats;
- skill selected count;
- active steps;
- abort count;
- helpful run count;
- harmful run count;
- per-skill-type delta.

Phase 11 считается здоровой, если:

- baseline path без skill system не изменился;
- skill system можно включить и выключить env/config флагом;
- skill usage не взрывает misses на gate pool;
- selected skills появляются не декоративно, а с локальными outcome deltas;
- harmful usage ratio остаётся низким;
- fallback срабатывает при плохом контексте;
- хотя бы на части карт или паттернов baseline + skills даёт выигрыш по `misses`, `sl_seg_q`, `dpx` или local pattern success.

## Ограничения текущего v1

- Extraction опирается на replay/eval traces; richer per-frame diagnostics дадут более точные action summaries.
- Executor intentionally conservative: он даёт assist, а не полное управление.
- Post-use adaptation лёгкая и online; основной verdict всё равно должен идти через `eval_skill_system.py`.
- Memory v1 по умолчанию хранится в SQLite, а JSON используется как debug/export формат.
