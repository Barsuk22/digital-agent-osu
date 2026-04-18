# Phase 3 / Aim Stability Refinement — статус

Статус: реализована и закрыта как рабочая aim-stability refinement ветка вместе с Phase 2.

Phase 3 здесь не означает обучение aim с нуля. Базовая policy уже умела двигаться и попадать; задача этой стадии была в том, чтобы сделать связь позиции курсора и клика стабильнее.

Текущий результат этой стадии — `best_timing.pt` в phase2 run folder. Он считается сильной базой для следующей полировки моторики:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
```

Следующий активный этап после Phase 3 — Phase 3.5 / Post-hit Motion Smoothing, где фокус переносится с попадания и timing на плавность выхода после hit.

## База обучения

Как и Phase 2, эта стадия стартует от:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt
```

Новые artifacts сохраняются в:

```text
artifacts/runs/osu_phase2_timing/
```

Название run-папки оставлено `osu_phase2_timing`, потому что Phase 2 и Phase 3 реализованы как один аккуратный refinement-этап поверх recoil checkpoint.

## Что добавлено

### Pre-hit positioning refinement

Перед кликом reward теперь различает:

- курсор уже близко и стабилен;
- курсор близко, но пролетает через объект слишком резко;
- курсор находится около цели в срочном окне, но продолжает лишнюю болтанку.

### Aim discipline

При click-событии учитывается:

- distance at click;
- near click;
- far click;
- settled click;
- unstable click.

Близкий и спокойный click получает небольшой bonus. Дальний или нестабильный click получает penalty.

### Post-hit exit quality

Существующая flow/anti-recoil логика разделена понятнее:

- `flow` отвечает за полезное движение к следующей цели;
- `post_hit_exit` отвечает за качество выхода после попадания и anti-recoil behavior.

Хороший выход к следующему объекту получает bonus. Резкий бесполезный отскок или движение не туда получает penalty.

### Aim metrics

В training log теперь есть:

- `dclick` — средняя дистанция до цели в момент клика;
- `near` — доля near clicks;
- `far` — доля far clicks;
- `stable` — доля стабильных pre-hit шагов;
- `exit` — доля хороших post-hit exits;
- `aim` — суммарный aim shaping вклад;
- `exit_r` — суммарный post-hit exit reward.

Eval также печатает `dclick`, `near` и `far`.

## Что ещё не закрыто

- aim stability пока проверяется на активной карте;
- нет отдельного набора regression eval-карт;
- micro-stability задаётся через простые speed/distance penalties, а не через отдельную модель моторики;
- slider-specific aim stability ещё требует отдельной стадии.
