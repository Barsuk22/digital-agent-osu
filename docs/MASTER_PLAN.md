# Master Plan - osu agent

Актуально на 2026-04-19.

Этот документ фиксирует общий план развития osu skill module. Статусы отражают текущее состояние проекта, а не первоначальный замысел.

## Текущая рамка

osu skill module - часть более широкой архитектуры цифрового агента. Его задача не в scripted-автоматизации osu!, а в формировании обучаемого моторного навыка через RL.

Текущий главный milestone: **Phase 7 / Multi-Map Generalization закрыта**.

Текущий golden checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Следующий планируемый milestone:

```text
Phase 8 / Easy Generalization & Pattern Formation
```

## Phase 0 / Core Foundation

Статус: закрыта.

Цель: создать osu-like среду, где агент действует в карте, получает judgement и reward.

Реализовано:

- `.osu` parser;
- circles, sliders, spinners;
- timing points и difficulty settings;
- environment с observation/action;
- hit/judgement system;
- replay frames;
- pygame viewer.

## Phase 1 / Initial Learning / Base PPO Learning

Статус: закрыта.

Цель: доказать, что агент может обучаться и взаимодействовать с реальной картой через PPO.

Реализовано:

- PPO training loop;
- Actor-Critic policy;
- rollout buffer;
- GAE;
- reward shaping;
- checkpoint save/load;
- eval через deterministic policy;
- replay после eval.

## Phase 1.5 / Movement Polishing

Статус: закрыта как recoil/movement база.

Цель: улучшить качество моторики уже обучаемого агента.

Фокус:

- сглаживание движения;
- снижение jerk и overspeed;
- anti-recoil после попаданий;
- мягкий выход к следующей цели;
- useful click ratio.

## Phase 2 / Timing Quality

Статус: закрыта.

Цель: улучшить точность кликов во времени.

Реализовано:

- timing metrics;
- reward вокруг hit window;
- штрафы за ранние/поздние клики;
- off-window click discipline.

## Phase 3 / Aim Stability

Статус: закрыта.

Цель: сделать связь позиции курсора и клика более устойчивой.

Реализовано:

- near/far click distinction;
- pre-hit stability;
- post-hit exit quality;
- aim-related train/eval метрики.

## Phase 3.5 / Post-hit Motion Smoothing

Статус: закрыта.

Цель: убрать остаточную отдачу после hit и снизить лишний jerk.

Результат: checkpoint стал пригодной базой для slider/spinner веток.

## Phase 4.1 / Slider Follow Fix

Статус: закрыта.

Цель: исправить поведение, при котором policy берет slider head, но не держит slider-follow.

Реализовано:

- активное состояние slider в observation;
- reward за удержание follow;
- диагностика hold/release/follow/drop;
- первые устойчивые slider-follow прогоны.

## Phase 5 / Slider Control

Статус: закрыта.

Цель: перейти от "попасть в head и держать click" к контролю полного slider segment.

Реализовано:

- segment-level metrics;
- `sl_seg_q`;
- `sl_full` / `sl_partial`;
- reverse/curve diagnostics;
- reward для sustained path tracking.

## Phase 6 / Spinner Control

Статус: закрыта.

Цель: обучить устойчивое spinner behavior и не ломать sliders/circles.

Реализовано:

- spinner observation/reward;
- spinner diagnostics;
- spinner-capable checkpoint line.

## Spica Main Fine-Tune

Статус: закрыта.

Цель: вернуть spinner-capable policy на основную Spica-карту и получить сильный single-map baseline.

Результат:

```text
artifacts/runs/osu_spica_main_finetune/checkpoints/golden_spica_main.pt
```

## Phase 7 / Multi-Map Generalization

Статус: закрыта 2026-04-19.

Цель: перенос поведения на несколько nearby easy/beginner карт.

Результат:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
best cycle score = 12.342
```

Закрывающие признаки:

- несколько train-карт проходят почти идеально;
- held-out `Chikatto` проходит почти идеально;
- Spica baseline не потерян;
- sliders восстановлены после multi-map degradation;
- best checkpoint выбирается по полному циклу;
- spinner behavior не разрушен.

Подробности:

```text
docs/osu/phase7_multimap_generalization_status.md
```

## Phase 8 / Easy Generalization & Pattern Formation

Статус: следующая планируемая стадия.

Старт:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Цель: расширить easy/generalization curriculum и начать формировать короткие паттерны, не прыгая сразу в hard-карты.

Направления:

- добавить held-out easy карты в curriculum;
- довести `Sentimental Love` до стабильного slider-follow;
- сохранить старый Phase 7 pool как regression gate;
- начать doubles/triples/short chains;
- hard/dense карты держать как stress-only eval.

Подробности:

```text
docs/osu/phase8_easy_generalization_plan.md
```

## Phase 9 / Stability Gate

Статус: планируется.

Цель: проверить, что агент играет повторяемо, а не случайно.

Проверяем:

- hit rate;
- useful clicks;
- timing drift;
- стабильность между eval-запусками;
- отсутствие регресса на старых gate-картах.

## Phase 10 / Skill Memory Init

Статус: планируется.

Цель: сохранять устойчивые успешные паттерны.

Возможные типы навыков:

- slider follow;
- reverse slider;
- short chain;
- spinner control;
- simple jump/double.

## Phase 11 / Skill System + Selection

Статус: планируется.

Цель: использовать извлеченные навыки во время игры.

Направления:

- skill selector;
- ranking применимости;
- fallback на основную policy;
- проверка, что skill usage действительно улучшает игру.

## Phase 12 / Speed & Complexity

Статус: долгосрочный план.

Цель: повысить сложность карт и плотность паттернов.

Направления:

- AR/OD выше текущих easy-карт;
- streams;
- jumps;
- temporal model;
- curriculum по сложности.

## Phase 13 / Final Generalization

Статус: долгосрочный план.

Цель: играть новые карты с разными стилями, BPM и паттернами.

Финальные метрики:

- accuracy;
- combo;
- стабильность;
- перенос навыка;
- качество моторики.
