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
