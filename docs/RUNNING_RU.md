# Запуск проекта

Актуально на 2026-04-19.

Все команды выполняются из корня проекта:

```powershell
cd D:\Projects\digital_agent_osu_project
```

## Текущий статус

Phase 7 / Multi-Map Generalization закрыта.
Phase 8.1 / Easy Generalization + Stability Gate закрыта.
Phase 9 / Gate Report пройдена.

Лучший Phase 7 checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Финальный лучший score Phase 7:

```text
best cycle score = 12.342
```

Следующая планируемая стадия:

```text
Phase 10 / Skill Memory Init
```

Phase 8 и Phase 9 шли вместе: Phase 8 обучила новый easy/generalization pool, а Phase 9 была встроена в выбор best checkpoint как stability gate и затем подтверждена eval-прогонами.

## Phase 8.1 обучение

Команда:

```powershell
python -m src.apps.train_osu
```

Стартовая база:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Новая run-директория:

```text
artifacts/runs/osu_phase8_easy_generalization/
```

Checkpoint-и Phase 8.1:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/latest_easy_generalization.pt
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Лимит обучения:

```text
updates = 700
```

Один цикл равен 7 картам.

Финальный результат:

```text
best cycle score = 12.486
best checkpoint = artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

## Phase 8.1 curriculum

```text
1. StylipS - Spica. (TV-size) [Beginner-ka]
2. Suzuki Minori - Dame wa Dame (TV Size) [maikayuii's Beginner]
3. MIMiNARI - Itowanai feat. Tomita Miyu, Ichinose Kana (TV Size) [Teages's Easy]
4. noa - Megane o Hazushite (TV Size) [Easy]
5. ONMYO-ZA - Kouga Ninpouchou [JauiPlaY's Easy]
6. Sati Akura - Sentimental Love (TV Size) [Myxo's Easy]
7. Sati Akura - Chikatto Chika Chika [Easy]
```

Роли:

- `gate`: первые 5 карт, старый Phase 7 regression gate;
- `target`: `Sentimental Love`, главная карта для подтягивания слайдеров;
- `heldout`: `Chikatto`, проверка переноса на easy-карту.

## Best checkpoint selection

Режим:

```text
cycle_easy_generalization_gate_v1
```

Он учитывает:

- средний и минимальный selection score;
- hit rate;
- slider inside / finish / segment quality;
- `dpx`, то есть среднюю дистанцию до slider ball/head;
- отсутствие регресса на старом Phase 7 pool;
- качество `Sentimental Love`.

В консоли cycle summary теперь показывает роли карт:

```text
gate
target
heldout
```

и добавляет:

```text
dpx
gate=ok/watch
```

## Eval

Команда:

```powershell
python -m src.apps.eval_osu
```

По умолчанию eval теперь проверяет:

```text
Sati Akura - Sentimental Love (TV Size) [Myxo's Easy]
```

и берет:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Если Phase 8 checkpoint еще не создан, eval автоматически откатится на:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Выбор конкретного checkpoint:

```powershell
$env:OSU_EVAL_CHECKPOINT='D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase8_easy_generalization\checkpoints\best_easy_generalization.pt'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_EVAL_CHECKPOINT
```

Выбор конкретной карты:

```powershell
$env:OSU_EVAL_MAP='D:\Projects\digital_agent_osu_project\data\raw\osu\maps\...\map.osu'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_EVAL_MAP
```

Replay после eval сохраняется сюда:

```text
artifacts/runs/osu_phase8_easy_generalization/replays/best_eval_replay.json
```

## Phase 9 gate-report

Итоговые eval-прогоны на `best_easy_generalization.pt`:

```text
Chikatto:          hits=133 miss=0 sl_inside=0.997 dpx=23.2 sl_seg_q=0.997
Sentimental Love:  hits=124 miss=3 sl_inside=0.951 dpx=32.5 sl_seg_q=0.961
Spica:             hits=84  miss=4 sl_inside=0.985 dpx=22.8 sl_seg_q=0.980
Suzuki:            hits=85  miss=1 sl_inside=1.000 dpx=26.7 sl_seg_q=1.000
MIMiNARI:          hits=91  miss=0 sl_inside=1.000 dpx=23.4 sl_seg_q=1.000
noa:               hits=120 miss=0 sl_inside=0.983 dpx=20.5 sl_seg_q=0.993
ONMYO-ZA:          hits=359 miss=2 sl_inside=0.980 dpx=28.4 sl_seg_q=0.981
YOASOBI held-out:  hits=129 miss=0 sl_inside=0.923 dpx=40.0 sl_seg_q=0.952
```

Phase 9 пройдена. Для следующих запусков `best_easy_generalization.pt` считается принятой основой.

## Replay

```powershell
python -m src.apps.replay_osu
```

Команда открывает последний сохраненный Phase 8 eval replay. Если его еще нет, откатывается на Phase 7 replay.

## Stress-only eval

Эти карты можно гонять вручную, но они не являются критерием закрытия Phase 8.1:

```text
Sati Akura - INTERNET YAMERO [Easy]
Sati Akura - Animal [Even if it's ugly, that's the way I want it.]
```

Они нужны как стресс-тест. На них нормально видеть много misses: задача Phase 8.1 сейчас не hard-clear, а стабильный easy/generalization.

## Что смотреть в eval

Главные метрики:

- `hits` / `miss`;
- `tmed`, `good_t`, `early`, `late`, `off`;
- `near`, `far`, `dclick`;
- `sl_inside_ratio`;
- `sl_follow_dist_mean`;
- `sl_finish_rate`;
- `sl_tick`, `sl_drop`;
- `sl_seg_q`;
- `sl_full`, `sl_partial`;
- `sl_rev_follow`, `sl_curve_good`;
- `spin_clear`, `spin_part`, `spin_miss`.

Для анализа Phase 8.1 / Phase 10 особенно важно:

- `far` около нуля на easy-картах;
- `sl_follow_dist_mean` не возвращается к 55-70 на gate pool;
- `sl_inside_ratio` и `sl_seg_q` остаются высокими;
- `Sentimental Love` не откатывается к состоянию “50 на 50”;
- старые Phase 7 карты не деградируют.

## Phase 10 / Skill Memory Init

Следующая планируемая стадия.

Цель: сохранять устойчивые успешные паттерны:

- slider follow;
- reverse slider;
- short chain;
- spinner control;
- simple jump/double.

## Phase 10/11 skill system

Сборка skill memory:

```powershell
python -m src.apps.build_skill_memory
```

Проверка памяти:

```powershell
python -m src.apps.inspect_skill_memory --verbose
```

Обычный eval с включённой skill system:

```powershell
$env:OSU_ENABLE_SKILL_SYSTEM='1'
$env:OSU_SKILL_MEMORY_PATH='D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase10_skill_memory\memory\skill_memory.sqlite'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_ENABLE_SKILL_SYSTEM
Remove-Item Env:\OSU_SKILL_MEMORY_PATH
```

Eval с автоматическим пополнением skill memory:

```powershell
$env:OSU_SKILL_AUTO_EXTRACT='1'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_SKILL_AUTO_EXTRACT
```

Полный baseline-vs-skill report:

```powershell
python -m src.apps.eval_skill_system --repeat 3 --per-skill-type --ablations
```

Report:

```text
artifacts/runs/osu_phase10_skill_memory/eval/skill_system_eval_report.json
```

## Документация по стадиям

```text
docs/osu/phase7_multimap_generalization_status.md
docs/osu/phase8_easy_generalization_plan.md
docs/osu/phase10_skill_memory_init.md
docs/osu/phase11_skill_system_selection.md
docs/osu/curriculum_plan.md
docs/osu/reward_design.md
```

## Карты и медиа

Карты и медиа не входят в репозиторий. Локальные `.osu`, аудио, фоны и видео ожидаются здесь:

```text
data/raw/osu/maps/
```

Известные пути задаются в:

```text
src/core/config/paths.py
```
