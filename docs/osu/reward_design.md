# Reward shaping osu-агента

## Актуальное состояние shaping

Текущая версия `src/apps/train_osu.py` переведена на **Phase 3.5 / Post-hit Motion Smoothing**. Она продолжает policy из:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
```

и сохраняет новый fine-tune отдельно:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/best_smooth.pt
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/latest_smooth.pt
```

Phase 2/3 timing/aim shaping остаётся в коде и не удаляется. Новый блок добавлен поверх него и отвечает за мягкий выход после successful hit: меньше отскока от точки попадания, меньше post-hit jerk, меньше движения прямо "от ноты" без полезного выхода и больше плавного движения к следующей цели.

Новые диагностические элементы в breakdown/log:

- `smoothing` / `smooth_r` — вклад reward за post-hit сглаживание;
- `rpx` — средняя дистанция от точки недавнего попадания в recoil-window;
- `rjerk` — средний jerk в post-hit окне;
- `badrec` — доля слишком резких отскоков;
- `smooth` — доля мягких выходов к следующей цели.

Ограничение намеренное: shaping не должен заставить агента бояться выходить к следующей цели. Поэтому штрафы мягкие, окно короткое, а хороший направленный выход всё ещё получает bonus.

Документ описывает текущее состояние reward shaping по коду `src/apps/train_osu.py`.

## Общая идея

Environment reward приходит из `OsuJudge`: попадания, промахи, slider/spinner события и базовые штрафы. Поверх него training loop добавляет shaping reward, который направляет агента к более полезному, точному и плавному поведению.

Это не scripted bot: reward не задаёт готовую траекторию. Он усиливает желательные признаки поведения и штрафует плохие моторные паттерны.

Текущая версия shaping относится к Phase 2 / Timing Refinement и Phase 3 / Aim Stability Refinement. Она продолжает policy из `best_recoil.pt`, а не обучает агента с нуля.

## Основные компоненты shaping

### Approach / movement

Агент получает положительный сигнал, когда сокращает дистанцию до текущей цели и движется в правильном направлении. Есть отдельный вклад для primary и secondary target.

Цель: сохранить уже выученное движение к объектам и не превратить refinement в стояние на месте.

### Timing

Добавлен отдельный timing-блок.

Он учитывает timing error в момент click:

- click около хорошего окна получает `timing_bonus`;
- near-miss получает небольшой `timing_penalty`;
- ранний click получает мягкий early penalty;
- поздний click получает мягкий late penalty;
- off-window click получает отдельный penalty.

Цель: уточнить timing без разрушения hit behavior. Penalty намеренно мягкий, чтобы агент не начал бояться кликать.

### Click discipline

Лишние клики штрафуются:

- click без цели;
- click вне focus window;
- click далеко от цели.

Цель: уменьшить spam и повысить useful click ratio.

### Aim stability

Добавлен отдельный `aim` вклад.

Он различает:

- near click;
- far click;
- settled click;
- unstable click;
- micro-jitter около актуальной цели.

Близкий и спокойный click получает небольшой bonus. Дальний или нестабильный click получает penalty.

### Pre-hit positioning

Если объект скоро должен быть нажат и курсор уже рядом, агент получает bonus за стабильное удержание около цели.

Если курсор резко пролетает через цель в pre-hit окне, добавляется небольшой penalty.

Цель: сделать вход в объект более устойчивым.

### Post-hit flow

После successful hit агент получает сигнал за полезное движение к следующей цели.

Плохой выход, слишком большая дистанция до следующей цели или движение в обратную сторону штрафуются.

### Anti-recoil / post-hit exit

Anti-recoil логика теперь учитывается через отдельный `post_hit_exit` вклад.

После successful scoring открывается короткое recoil-window. В этом окне штрафуются:

- слишком резкое удаление от точки попадания;
- jerk сразу после hit;
- движение прямо от точки попадания без полезного выхода;
- плохая направленность относительно следующей цели.

Небольшой bonus даётся за мягкий выход в сторону следующего объекта.

### Motion quality

Сохраняются штрафы за:

- jerk;
- overspeed;
- бесполезное движение вне срочной ситуации;
- idle в срочном окне, если курсор далеко от цели.

## Метрики

Training log теперь показывает не только reward/hit/click метрики, но и диагностику Phase 2/3:

- `tmean`;
- `tmed`;
- `good_t`;
- `early`;
- `late`;
- `off`;
- `dclick`;
- `near`;
- `far`;
- `stable`;
- `exit`;
- `time+`;
- `time-`;
- `aim`;
- `exit_r`.

Eval также печатает summary по timing и aim после deterministic rollout.

## Checkpoint-ветки

Phase 1 / recoil база:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt
```

Phase 2/3 refinement сохраняется отдельно:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
artifacts/runs/osu_phase2_timing/checkpoints/latest_timing.pt
```

Разделение нужно, чтобы не перезаписывать уже хорошую recoil policy.

## Что ещё не закрыто

- параметры shaping пока живут в `TrainConfig`;
- нет отдельного YAML-конфига для Phase 2/3;
- multi-map reward validation ещё не сделан;
- slider-specific refinement требует отдельной стадии.
# Update 2026-04-18: Phase 4.1 slider-follow shaping

Текущая активная ветка обучения sliders:

```text
artifacts/runs/osu_phase4_slider_follow_fix/
```

Она продолжает policy из:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/best_smooth.pt
```

Причина обновления: прежняя slider-intro логика давала head hit, но почти не давала обучаемого состояния и reward для удержания slider ball. Теперь observation содержит отдельный slider state block, а shaping добавляет мягкие компоненты:

- удержание follow после `slider_head`;
- близость к текущей slider ball;
- уменьшение distance до slider target;
- progress во время активного slider;
- tick/finish signal;
- penalty за release, lost follow, jerk и premature escape.

Важное ограничение: это intro/fix stage, не final slider mastery. Вес slider shaping намеренно умеренный, чтобы не разрушить уже рабочие circles/timing/aim.

После первых PPO-логов стало видно, что slider shaping был слишком наказующим до появления follow-навыка: `slider_r` стабильно уходил примерно в `-80..-100`, а `sl_inside_ratio` оставался около нуля. Поэтому активный slider больше не считается ошибкой по умолчанию. Теперь до входа в follow radius есть acquisition ladder: reward за сокращение distance до slider ball, небольшой signal за удержание click и мягкие penalties только за явный release/lost follow/escape.

Deterministic debug-policy `python -m src.apps.debug_slider_follow` подтверждает, что env/judge могут выдавать ненулевые `slider_follow`, `slider_finish` и `slider_tick`, если курсор едет за ball.

Следующая узкая диагностика разделяет click и movement:

- `sl_post_head_hold_ratio` показывает, удерживает ли policy click после head;
- `sl_click_release_count` показывает premature release transitions;
- `sl_geom_inside_ratio` показывает, входит ли курсор в follow circle даже без учета click;
- `sl_target_align` показывает, направлено ли движение к текущей slider ball.

Дополнительный shaping применяется только во время active slider: небольшой early-hold reward после head, penalty за ранний release и мягкий direction reward к slider target.

После следующего диагностического прогона стало видно, что курсор уже часто бывает геометрически рядом с follow zone (`sl_geom_inside_ratio` заметно выше нуля), но `sl_click_hold_steps` почти всегда оставался 0-3. Поэтому click semantics разделены: обычный `click_threshold=0.75` по-прежнему определяет новое нажатие для circles/head hit, а active-slider hold принимает более мягкий `slider_hold_threshold=0.45`. Это не делает circle clicks более свободными, но дает PPO непрерывный мост от tap к hold во время уже активного slider.

Новые диагностические метрики: `sl_head`, `sl_follow`, `sl_drop`, `sl_fin`, `sl_tick`, `sl_dpx`, `sl_active_steps`, `sl_inside_ratio`, `sl_follow_dist_mean`, `sl_follow_gain`, `sl_progress_gain`, `sl_lost_follow_count`, `sl_finish_rate`, `sl_tick_hit_rate`.

Для head-to-hold перехода дополнительно логируются `sl_head_to_hold`, `sl_release_after_head`, `sl_hold_steps_mean`, `sl_first_hold_delay`, `sl_near_hold_ratio` и `sl_near_released_ratio`.

Следующая правка не меняет input dim и не трогает circle clicks. После оживления hold стало видно, что policy часто держит click без настоящего tracking: `sl_follow_gain` остается отрицательным, а distance до ball большой. Поэтому slider shaping теперь сильнее различает:

- good tracking: hold + сокращение distance или движение в сторону текущей slider ball;
- fake hold: hold далеко от ball без улучшения distance;
- stall: hold при почти нулевом полезном движении;
- wrong direction: движение от текущего follow target.

Generic reward за сам факт hold уменьшен, а reward за path delta и direction alignment усилен. Цель: не поощрять “держу кнопку где-то рядом”, а сделать выгодным именно ехать за slider ball.

# Update 2026-04-18: Phase 5 slider-control shaping

Phase 5 continues from:

```text
artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/best_slider_follow.pt
```

and writes to:

```text
artifacts/runs/osu_phase5_slider_control/
```

The reward focus changes from Phase 4.1 acquisition to full slider segment control.

Important changes:

- isolated `slider_head` receives a small Phase 5 deemphasis penalty in training shaping;
- `slider_tick` receives an extra consistency bonus;
- `slider_finish` receives an extra control bonus, scaled by recent inside-follow chain;
- `slider_drop` receives a moderate control penalty;
- sustained inside-follow chains receive more value;
- movement aligned with the slider tangent is rewarded near the follow target;
- movement against the tangent/target is penalized;
- curved/path-change steps are detected from tangent changes and rewarded only when inside-follow is maintained;
- reverse events are detected from sharp tangent flips and tracked in a short reverse window.

This is still shaping, not scripted autoplay. Phase 5 does not add a new observation dimension and does not hardcode a trajectory. It uses existing slider target/tangent/progress signals to make PPO prefer stable segment control over head-tap success.

New training/eval metrics:

- `sl_seg_q`;
- `sl_full`;
- `sl_partial`;
- `sl_rev`;
- `sl_rev_follow`;
- `sl_curve`;
- `sl_curve_good`.

The expected direction is: `sl_seg_q`, `sl_inside_ratio`, `sl_tick_hit_rate`, `sl_finish_rate`, `sl_chain_mean`, and `sl_chain_max` should rise together. If only `sl_head` rises, Phase 5 is not learning the intended behavior.
