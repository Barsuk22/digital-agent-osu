# Reward shaping osu-агента

Актуально на 2026-04-19.

Документ описывает текущее состояние reward shaping по коду `src/apps/train_osu.py`.

## Актуальное состояние

Текущая закрытая ветка обучения: **Phase 7 / Multi-Map Generalization**.

Golden checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Лучший результат:

```text
best cycle score = 12.342
best mode = cycle_mean_min_slider_v1
```

Phase 7 продолжила long-running shaping линию из предыдущих фаз:

- timing/click discipline;
- aim stability;
- post-hit flow;
- slider follow/control;
- spinner behavior;
- multi-map best selection.

Главная поздняя правка Phase 7: tight slider-follow shaping. Она была добавлена после того, как multi-map policy начала хорошо попадать, но визуально часть sliders проходила плохо: агент нажимал на slider head, держал click, но не велся достаточно точно за slider ball.

## Общая идея

Environment reward приходит из `OsuJudge`: попадания, промахи, slider/spinner события и базовые штрафы. Поверх него training loop добавляет shaping reward, который направляет агента к более полезному, точному и плавному поведению.

Это не scripted bot: reward не задает готовую траекторию. Он усиливает желательные признаки поведения и штрафует плохие моторные паттерны.

## Основные компоненты shaping

### Approach / movement

Агент получает положительный сигнал, когда сокращает дистанцию до текущей цели и движется в правильном направлении.

Цель: сохранять движение к объектам и не превращать refinement в стояние на месте.

### Timing

Timing-блок учитывает timing error в момент click:

- click около хорошего окна получает bonus;
- near-miss получает небольшой penalty;
- ранний click получает early penalty;
- поздний click получает late penalty;
- off-window click получает отдельный penalty.

Цель: уточнить timing без разрушения hit behavior.

### Click discipline

Лишние клики штрафуются:

- click без цели;
- click вне focus window;
- click далеко от цели.

Цель: уменьшить spam и повысить useful click ratio.

### Aim stability

Aim-блок различает:

- near click;
- far click;
- settled click;
- unstable click;
- micro-jitter около актуальной цели.

Близкий и спокойный click получает bonus. Дальний или нестабильный click получает penalty.

### Pre-hit positioning

Если объект скоро должен быть нажат и курсор уже рядом, агент получает bonus за стабильное удержание около цели.

Если курсор резко пролетает через цель в pre-hit окне, добавляется penalty.

### Post-hit flow

После successful hit агент получает сигнал за полезное движение к следующей цели.

Плохой выход, слишком большая дистанция до следующей цели или движение в обратную сторону штрафуются.

### Anti-recoil / post-hit exit

После successful scoring открывается короткое recoil-window. В этом окне штрафуются:

- слишком резкое удаление от точки попадания;
- jerk сразу после hit;
- движение прямо от точки попадания без полезного выхода;
- плохая направленность относительно следующей цели.

Bonus дается за мягкий выход в сторону следующего объекта.

### Motion quality

Сохраняются штрафы за:

- jerk;
- overspeed;
- бесполезное движение вне срочной ситуации;
- idle в срочном окне, если курсор далеко от цели.

## Slider shaping

Slider shaping развивался в несколько этапов.

### Phase 4.1 / Slider Follow Fix

Цель: оживить follow behavior после slider head.

Добавлено:

- активное состояние slider в observation;
- reward за удержание follow после `slider_head`;
- близость к текущей slider ball;
- progress во время активного slider;
- tick/finish signal;
- penalty за release, lost follow, jerk и premature escape.

### Phase 5 / Slider Control

Цель: перейти от head acquisition к full segment control.

Добавлено:

- `sl_seg_q`;
- `sl_full`;
- `sl_partial`;
- `sl_rev`;
- `sl_rev_follow`;
- `sl_curve`;
- `sl_curve_good`;
- reward за sustained inside-follow chains;
- reward за движение по slider tangent;
- диагностика reverse/curve windows.

### Phase 7 / Tight Follow Patch

Проблема: после multi-map обучения агент часто держал click, но не всегда точно ехал по slider ball.

Добавлено:

- tight follow radius;
- bonus за tight-follow;
- close-follow bonus;
- penalty за loose follow;
- penalty за hold далеко от slider ball;
- penalty за negative slider path delta;
- penalty за lost follow / escape;
- усиленный finish control bonus;
- `dpx` в concise train log.

Ожидаемое направление:

- `dpx` снижается;
- `sl_inside_ratio` растет или остается высоким;
- `sl_seg_q` растет или остается высоким;
- `sl_finish_rate` не падает;
- `far` не растет.

Итог Phase 7 подтвердил это направление: на старом gate pool `dpx` ушел примерно в диапазон `23-33` на большинстве карт, а sliders стали визуально устойчивыми.

## Spinner shaping

Spinner reward поддерживает:

- удержание click во время spinner;
- хороший радиус вращения;
- прогресс вращения;
- штрафы за stall, плохой радиус и miss.

Phase 7 показала, что spinner behavior не разрушился после multi-map и slider tight-follow изменений.

## Best checkpoint selection

В multi-map режиме одиночный episode reward опасен: длинная или легкая карта может случайно заблокировать лучший общий checkpoint.

Phase 7 использует cycle-based best mode:

```text
cycle_mean_min_slider_v1
```

Best score считается после полного цикла по всем train-картам и учитывает:

- `mean_selection`;
- `min_selection`;
- `mean_hit`;
- `mean_slider_inside`;
- `mean_slider_finish`;
- `mean_slider_quality`;
- `spinner_misses`.

Финальный Phase 7 best:

```text
score=12.342
mean_sel=8.956
min_sel=6.266
mean_hit=0.994
sl_inside=0.985
sl_fin=0.968
sl_q=0.987
spin_miss=0
```

## Основные метрики

Training/eval logs содержат:

- `reward`;
- `sel`;
- `hit`;
- `miss`;
- `clicks`;
- `useful`;
- `tmed`;
- `good_t`;
- `early`;
- `late`;
- `off`;
- `near`;
- `far`;
- `sl_head`;
- `sl_fin`;
- `sl_tick`;
- `sl_drop`;
- `sl_inside_ratio` / `sl`;
- `sl_follow_dist_mean` / `dpx`;
- `sl_finish_rate` / `fin`;
- `sl_seg_q` / `q`;
- `spin_miss`;
- `kl`.

## Что было важно для Phase 8.1

Phase 8.1 стартовала от:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

И была закрыта на:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
best cycle score = 12.486
```

Что сработало:

- не увеличивать сложность резко;
- держать Phase 7 train pool как regression gate;
- использовать `Sentimental Love` как slider-generalization target;
- hard/dense карты не включать в best score;
- следить, чтобы `dpx` не возвращался к плохим значениям;
- не поощрять простое удержание click без настоящего tracking.

Для Phase 10 важно не менять резко reward shaping, а сначала извлечь устойчивые паттерны из уже успешного поведения: slider follow, reverse slider, short chain, spinner control, simple jump/double.

## Что еще не закрыто

- параметры shaping пока живут в `TrainConfig`;
- нет полноценного YAML-конфига для фаз;
- hard/dense карты требуют отдельной curriculum-лестницы;
- skill memory еще не подключена к успешным паттернам.
