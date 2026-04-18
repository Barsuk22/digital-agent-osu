# Master Plan — osu agent

Этот документ фиксирует общий план развития osu skill module. Статусы фаз ниже отражают текущее состояние проекта, а не только первоначальный замысел.

## Текущая рамка

osu skill module — часть более широкой архитектуры цифрового агента. Его задача не в scripted-автоматизации osu!, а в формировании обучаемого моторного навыка через RL.

Ключевое состояние на сейчас:

- Phase 0 / Foundation закрыта;
- Phase 1 / Initial Learning / Base PPO Learning закрыта по смыслу;
- Phase 1.5 / Movement Polishing стала базой для следующего этапа;
- Phase 2 / Timing Refinement и Phase 3 / Aim Stability Refinement закрыты как рабочая timing/aim ветка;
- активная стадия — Phase 3.5 / Post-hit Motion Smoothing;
- дальнейшие фазы связаны со sliders, multi-map generalization и skill memory.

## Phase 0 / Core Foundation

Статус: закрыта.

Цель: создать osu-like среду, где агент действительно действует в карте, получает judgement и reward.

Реализовано:

- `.osu` parser;
- circles, sliders, spinners;
- timing points и difficulty settings;
- environment с observation/action;
- hit/judgement system;
- replay frames;
- pygame viewer.

Ограничения:

- renderer и slider geometry не являются точной копией osu! lazer;
- часть моделей среды намеренно упрощена для RL-обучения;
- конфиги ещё не полностью вынесены из кода.

## Phase 1 / Initial Learning / Base PPO Learning

Статус: закрыта по смыслу как этап достижения базовой обучаемости.

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

Критерий Phase 1 был не в идеальной игре, а в достижении базовой обучаемости. Этот критерий выполнен: агент проходит train/eval/replay pipeline и способен попадать по объектам.

## Phase 1.5 / Movement Polishing

Статус: закрыта как recoil/movement база для Phase 2/3.

Цель: улучшить качество моторики уже обучаемого агента.

Текущий фокус:

- сглаживание движения;
- снижение jerk и overspeed;
- anti-recoil после попаданий;
- мягкий выход к следующей цели;
- улучшение useful click ratio;
- humanlike movement polishing;
- развитие reward shaping.

Отдельная fine-tune ветка сохраняется в `best_recoil.pt` и `latest_recoil.pt`, чтобы не затирать базовый checkpoint Phase 1.

## Phase 2 / Timing Quality

Статус: реализована и закрыта как рабочая timing-refinement ветка.

Цель: улучшить точность кликов во времени.

Реализовано:

- явные timing-метрики;
- усиление reward вокруг hit window;
- штрафы за ранние и поздние клики;
- уменьшение off-window clicking.
- отдельные `timing_bonus` и `timing_penalty` в breakdown;
- сохранение в `artifacts/runs/osu_phase2_timing/`.

База загрузки:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt
```

## Phase 3 / Aim Stability

Статус: реализована и закрыта вместе с Phase 2 как рабочая aim-stability ветка.

Цель: сделать связь позиции курсора и клика более устойчивой.

Реализовано:

- штрафы за click далеко от цели;
- удержание около объекта в pre-hit окне;
- анализ post-hit движения;
- снижение случайных отскоков и лишних микродвижений.
- distinction между near/far/settled/unstable click;
- micro-stability около актуальной цели;
- отдельный `post_hit_exit` вклад для anti-recoil/exit quality;
- aim-related метрики в train/eval.

## Phase 3.5 / Post-hit Motion Smoothing

Статус: активная стадия.

Цель: убрать остаточную "отдачу" после попадания, не ломая уже сильный timing/aim checkpoint.

База обучения:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
```

Новая ветка сохранения:

```text
artifacts/runs/osu_phase3_motion_smoothing/
```

Реализуемый фокус:

- короткое post-hit recoil-window;
- штраф за слишком резкий отлёт от точки попадания;
- штраф за post-hit jerk;
- мягкий bonus за плавный выход к следующей цели;
- отдельные метрики `smooth_r`, `rpx`, `rjerk`, `badrec`, `smooth`.

## Phase 4 / Slider Intro

Статус: частично заложена в foundation, но как полноценная фаза ещё не закрыта.

Сейчас есть:

- slider head hit;
- follow reward;
- ticks;
- finish/drop logic;
- визуализация slider body/ball/follow circle.

Дальше нужно:

- улучшить slider path accuracy;
- усилить обучение follow behavior;
- отдельно оценивать slider stability.

## Phase 5 / Slider Control

Статус: планируется.

Цель: научить агента стабильно вести простые sliders.

Направления:

- reward за удержание;
- tick consistency;
- штраф за drop;
- eval-метрики по slider segments.

## Phase 6 / Spinner Control

Статус: базовая логика есть, полноценное обучение планируется.

Сейчас spinner поддерживается в judgement через накопление вращения. Дальше нужно обучать устойчивое spinner behavior и добавить метрики.

## Phase 7 / Multi-Map Generalization

Статус: планируется.

Цель: перенос поведения на несколько easy-карт.

Направления:

- train/eval pools;
- разные BPM и паттерны;
- сравнение поведения на seen/unseen картах;
- защита от переобучения на одну карту.

## Phase 8 / Pattern Formation

Статус: планируется.

Цель: перейти от реакции на отдельные объекты к коротким последовательностям движения.

Направления:

- doubles;
- triples;
- короткие chains;
- анализ повторяемых successful segments.

## Phase 9 / Stability Gate

Статус: планируется.

Цель: проверить, что агент играет повторяемо, а не случайно.

Проверяем:

- hit rate;
- useful clicks;
- timing drift;
- похожесть удачных эпизодов;
- стабильность поведения между eval-запусками.

## Phase 10 / Skill Memory Init

Статус: планируется.

Цель: сохранять только устойчивые успешные паттерны.

Возможные типы навыков:

- jump;
- short chain;
- slider follow.

## Phase 11 / Skill System + Selection

Статус: планируется.

Цель: использовать извлечённые навыки во время игры.

Направления:

- skill selector;
- ranking применимости;
- fallback на основную policy;
- проверка, что skill usage действительно улучшает игру.

## Phase 12 / Speed & Complexity

Статус: долгосрочный план.

Цель: повысить сложность карт и плотность паттернов.

Возможные направления:

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
