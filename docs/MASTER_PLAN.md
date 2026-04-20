# Master Plan - osu agent

Актуально на 2026-04-19.

Этот документ фиксирует общий план развития osu skill module. Статусы отражают текущее состояние проекта.

## Текущая рамка

osu skill module - часть более широкой архитектуры цифрового агента. Его задача не в scripted-автоматизации osu!, а в формировании обучаемого моторного навыка через RL.

Текущий milestone:

```text
Phase 10 / Skill Memory Init
```

Golden baseline:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Последняя закрытая training ветка:

```text
artifacts/runs/osu_phase8_easy_generalization/
```

## Закрытые фазы

### Phase 0 / Core Foundation

Статус: закрыта.

Реализовано:

- `.osu` parser;
- circles, sliders, spinners;
- timing points и difficulty settings;
- environment с observation/action;
- hit/judgement system;
- replay frames;
- pygame viewer.

### Phase 1 / Base PPO Learning

Статус: закрыта.

Реализовано:

- PPO training loop;
- Actor-Critic policy;
- rollout buffer;
- GAE;
- reward shaping;
- checkpoint save/load;
- deterministic eval;
- replay после eval.

### Phase 1.5 / Movement Polishing

Статус: закрыта как recoil/movement база.

Фокус:

- сглаживание движения;
- снижение jerk и overspeed;
- anti-recoil после попаданий;
- мягкий выход к следующей цели;
- useful click ratio.

### Phase 2 / Timing Quality

Статус: закрыта.

Реализовано:

- timing metrics;
- reward вокруг hit window;
- штрафы за ранние/поздние клики;
- off-window click discipline.

### Phase 3 / Aim Stability

Статус: закрыта.

Реализовано:

- near/far click distinction;
- pre-hit stability;
- post-hit exit quality;
- aim-related train/eval metrics.

### Phase 3.5 / Post-hit Motion Smoothing

Статус: закрыта.

Результат: checkpoint стал пригодной базой для slider/spinner веток.

### Phase 4.1 / Slider Follow Fix

Статус: закрыта.

Реализовано:

- active slider state в observation;
- reward за удержание follow;
- диагностика hold/release/follow/drop;
- первые устойчивые slider-follow прогоны.

### Phase 5 / Slider Control

Статус: закрыта.

Реализовано:

- segment-level metrics;
- `sl_seg_q`;
- `sl_full` / `sl_partial`;
- reverse/curve diagnostics;
- reward для sustained path tracking.

### Phase 6 / Spinner Control

Статус: закрыта.

Реализовано:

- spinner observation/reward;
- spinner diagnostics;
- spinner-capable checkpoint line.

### Spica Main Fine-Tune

Статус: закрыта.

Результат:

```text
artifacts/runs/osu_spica_main_finetune/checkpoints/golden_spica_main.pt
```

### Phase 7 / Multi-Map Generalization

Статус: закрыта 2026-04-19.

Результат:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
best cycle score = 12.342
```

Закрывающие признаки:

- несколько train-карт проходятся почти идеально;
- held-out `Chikatto` проходится почти идеально;
- Spica baseline не потерян;
- sliders восстановлены после multi-map degradation;
- best checkpoint выбирается по полному циклу;
- spinner behavior не разрушен.

Подробности:

```text
docs/osu/phase7_multimap_generalization_status.md
```

### Phase 8.1 / Easy Generalization + Stability Gate

Статус: закрыта 2026-04-19.

Старт:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Выход:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/latest_easy_generalization.pt
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Best mode:

```text
cycle_easy_generalization_gate_v1
```

Цель:

- расширить easy/generalization curriculum;
- довести `Sentimental Love` до стабильного slider-follow;
- сохранить старый Phase 7 pool как regression gate;
- начать doubles/triples/short chains;
- hard/dense карты держать как stress-only eval.

Phase 9 / Stability Gate встроена в Phase 8.1: best checkpoint получает штрафы за регресс старого gate pool, плохой `Sentimental Love`, рост `dpx` и нестабильный slider-follow.

Результат:

```text
best cycle score = 12.486
best checkpoint = artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Закрывающие признаки:

- `Sentimental Love` поднялась до уверенного slider-follow;
- `Chikatto` как held-out easy карта проходит почти идеально;
- старый Phase 7 gate pool удержан без критического регресса;
- новая held-out easy карта `YOASOBI - Yasashii Suisei` прошла без misses;
- hard/dense карты остаются stress-only eval, а не критерием закрытия.

Подробности:

```text
docs/osu/phase8_easy_generalization_plan.md
```

### Phase 9 / Gate Report

Статус: пройдена 2026-04-19.

Цель: проверить, что агент играет повторяемо, а не случайно.

Проверяем:

- hit rate;
- useful clicks;
- timing drift;
- стабильность между eval-запусками;
- отсутствие регресса на старых gate-картах;
- `Sentimental Love` как target;
- `Chikatto` как heldout.

Итоговый gate-report:

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

Вывод: checkpoint принят как стабильная основа для Phase 10. Главная техническая заметка: timing drift часто ранний, но slider-follow и aim stability достаточны для перехода.

## Текущая фаза

### Phase 10 / Skill Memory Init

Статус: следующая планируемая стадия.

Цель: сохранять устойчивые успешные паттерны.

Возможные типы навыков:

- slider follow;
- reverse slider;
- short chain;
- spinner control;
- simple jump/double.

### Phase 11 / Skill System + Selection

Статус: планируется.

Цель: использовать извлеченные навыки во время игры.

Направления:

- skill selector;
- ranking применимости;
- fallback на основную policy;
- проверка, что skill usage действительно улучшает игру.

## Phase 10/11 implementation update

Phase 10 реализована как foundation для skill memory:

- `SkillEntry` schema;
- extraction из replay/eval traces;
- quality/confidence scoring;
- dedup / merge;
- SQLite skill memory storage with optional JSON export;
- `build_skill_memory.py`;
- `inspect_skill_memory.py`.

Phase 11 реализована как опциональный runtime layer:

- matcher;
- ranker;
- selector с confidence/risk/cooldown gates;
- bounded executor с fallback;
- post-use stats update;
- интеграция в `eval_osu`;
- `eval_skill_system.py` для baseline-vs-skill, per-type и ablation reports.

Подробности:

```text
docs/osu/phase10_skill_memory_init.md
docs/osu/phase11_skill_system_selection.md
```

### Phase 12 / Speed & Complexity

Статус: долгосрочный план.

Цель: повысить сложность карт и плотность паттернов.

Направления:

- AR/OD выше текущих easy-карт;
- streams;
- jumps;
- temporal model;
- curriculum по сложности.

### Phase 13 / Final Generalization

Статус: долгосрочный план.

Цель: играть новые карты с разными стилями, BPM и паттернами.

Финальные метрики:

- accuracy;
- combo;
- стабильность;
- перенос навыка;
- качество моторики.
