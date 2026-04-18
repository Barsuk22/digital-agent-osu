# Phase 4.1 / Slider Follow Fix

Дата: 2026-04-18

## Статус

Предыдущая ветка Slider Intro показала полезный, но неполный результат: policy стабильно брала slider head, однако почти сразу теряла follow. По логам это выглядело как `sl_head > 0`, `sl_drop ~= sl_head`, `sl_follow ~= 0`, `sl_fin = 0`, `sl_tick ~= 0`.

Phase 4.1 не начинает обучение заново и не заменяет уже рабочее circle gameplay. Это отдельная fine-tuning ветка для обучения начальному slider-follow поведению.

## База обучения

Новая фаза стартует от:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/best_smooth.pt
```

## Артефакты

Новая ветка сохраняется отдельно:

```text
artifacts/runs/osu_phase4_slider_follow_fix/
artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/latest_slider_follow.pt
artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/best_slider_follow.pt
artifacts/runs/osu_phase4_slider_follow_fix/replays/best_eval_replay.json
```

Старые phase1/phase2/phase3 артефакты не перезаписываются.

## Что изменено

Observation расширен с 33 до 46 признаков. Добавлен явный блок активного slider:

- флаг активного slider;
- флаг, что primary object является slider;
- прогресс активного slider;
- текущая target point / slider ball;
- distance до follow target;
- inside follow flag;
- head hit flag;
- время до конца slider;
- локальная tangent direction;
- effective follow radius.

Для старых checkpoint с input dim 33 используется partial load: старые веса первого слоя копируются в общую часть, новые slider-признаки инициализируются текущей инициализацией модели.

## Reward

Добавлен мягкий slider-follow shaping поверх существующего circle/timing/aim shaping:

- reward за удержание follow после head hit;
- reward за близость к текущей slider ball;
- reward за уменьшение distance до slider target;
- reward за progress во время активного slider;
- penalty за потерю follow;
- penalty за release click во время slider;
- penalty за резкий jerk и premature escape от slider path.

Также slider head больше не открывает post-hit recoil окно, потому что оно толкало policy уходить к следующему объекту сразу после head hit.

После первых логов Phase 4.1 был найден bottleneck: policy стабильно брала head, но `slider_r` уходил в большой постоянный минус (`-80..-100`) до появления первых follow-успехов. Это делало active slider почти постоянным наказанием, а не обучающим мостиком. Shaping смягчен:

- outside-follow больше не получает большой постоянный штраф;
- положительный сигнал за приближение к slider ball появился до входа в follow radius;
- добавлен небольшой reward за удержание click во время active slider;
- penalties за lost follow, escape, jerk и release стали мягче;
- tick/drop penalties в judge уменьшены, finish/tick rewards сохранены как полезный целевой сигнал.

Цель этой правки — сначала дать policy обнаружить достижимое поведение, а уже затем усиливать качество follow.

Второй диагностический проход после 50+ updates показал, что reward bridge уже не разрушает общий reward и circles/timing сохранены, но PPO-policy все еще ведет себя как tapper: head hit есть, а sustained hold/follow не формируется. Для этого добавлены отдельные click-hold метрики и усилен только active-slider hold bridge:

- `sl_click_hold_steps`;
- `sl_click_release_count`;
- `sl_post_head_hold_ratio`;
- `sl_click_released_ratio`;
- `sl_geom_inside_ratio`;
- `sl_time_to_first_inside`;
- `sl_first_inside_miss`;
- `sl_target_align`.

Reward дополнительно поощряет удержание click сразу после `slider_head` и направление движения к текущей slider ball. Это не меняет observation dim и не трогает circle/timing shaping вне active slider.

Третий узкий bottleneck оказался в click semantics: policy геометрически уже подводит курсор к slider (`sl_geom_inside_ratio` порядка 0.4+), но продолжает отпускать click сразу после head. Поэтому `just_pressed` оставлен на строгом `click_threshold=0.75`, а удержание во время уже активного slider получило отдельный `slider_hold_threshold=0.45`. Circle/timing поведение использует прежний строгий порог; смягчение применяется только к active-slider hold, чтобы PPO получил достижимый переход от tap к sustained hold.

Для этой проверки добавлены head-to-hold метрики:

- `sl_head_to_hold`;
- `sl_release_after_head`;
- `sl_hold_steps_mean`;
- `sl_first_hold_delay`;
- `sl_near_hold_ratio`;
- `sl_near_released_ratio`.

После появления hold-сигнала следующий bottleneck сместился в path tracking: policy чаще держит click, но все еще плохо сокращает distance до slider ball. Shaping уточнен без изменения observation:

- усилен reward за positive `sl_follow_gain`;
- усилен direction-aware reward к текущей slider ball;
- общий bonus за сам факт hold уменьшен;
- добавлен мягкий penalty за far/fake hold, stall и wrong-direction movement;
- inside-follow получает небольшой sustain bonus за короткие непрерывные цепочки.

Для диагностики tracking добавлены `sl_track_good`, `sl_track_bad`, `sl_stall`, `sl_wrong_dir`, `sl_chain_mean`, `sl_chain_max`, `sl_prog_hold`, `sl_prog_inside`, `sl_d_hold`, `sl_d_inside`.

## Debug sanity

Добавлен deterministic sanity-check:

```powershell
python -m src.apps.debug_slider_follow
```

Он использует простую policy: если slider активен, двигаться прямо к текущей slider ball и удерживать click down. Trace сохраняется сюда:

```text
artifacts/runs/osu_phase4_slider_follow_fix/metrics/slider_follow_debug_trace.json
```

На активной карте sanity-check подтвердил достижимость follow:

```text
sl_head=28
sl_follow_steps=2013
sl_fin=28
sl_drop=0
sl_tick_hit_rate=1.000
sl_inside_ratio=1.000
sl_follow_dist_mean=2.3
sl_finish_rate=1.000
```

Вывод: env/judge/path физически могут выдавать follow/tick/finish. Текущий bottleneck был в обучающем сигнале для PPO-policy, а не в невозможности slider follow в окружении.

## Slider logic

Slider path стал устойчивее для обучения:

- passthrough `P` теперь строится как дуга через три точки, когда это возможно;
- bezier `B` учитывает разрыв сегментов через duplicate control point;
- добавлена локальная tangent direction;
- tick timing теперь считается от beat length / slider tick rate, а не только от `SliderTickRate` как числа ticks per span.

Это не полная 1:1 parity с osu! lazer, но заметно более полезная геометрия для RL-сигнала.

## Метрики

В train/eval добавлены slider-метрики:

- `sl_head`;
- `sl_follow`;
- `sl_drop`;
- `sl_fin`;
- `sl_tick`;
- `sl_dpx`;
- `sl_active_steps`;
- `sl_inside_ratio`;
- `sl_follow_dist_mean`;
- `sl_follow_gain`;
- `sl_progress_gain`;
- `sl_lost_follow_count`;
- `sl_finish_rate`;
- `sl_tick_hit_rate`.

Цель первых прогонов: увидеть, что `sl_inside_ratio`, `sl_follow_gain`, `sl_progress_gain`, `sl_tick_hit_rate` и `sl_finish_rate` начинают расти, а `sl_drop ~= sl_head` перестает быть постоянным паттерном.

## Ограничения

Phase 4.1 все еще intro/fix стадия. Она не обещает perfect slider mastery, reverse sliders на сложных картах или полную совместимость с osu! lazer renderer. После первых логов может понадобиться еще одна итерация по весам shaping и effective follow radius.
 
# Follow-up: Phase 5 / Slider Control

Phase 4.1 is no longer the final active slider target. Phase 5 / Slider Control has been added as the next stage:

```text
docs/osu/phase5_slider_control_status.md
```

It fine-tunes from `artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/best_slider_follow.pt` and saves into `artifacts/runs/osu_phase5_slider_control/`.
