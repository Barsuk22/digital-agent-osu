# Phase 3.5 / Post-hit Motion Smoothing — статус

Статус: активная fine-tuning стадия.

Эта фаза продолжает уже обученного osu PPO-агента. Она не запускает обучение с нуля и не заменяет Phase 2/3. База для старта:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
```

Новая ветка сохраняется отдельно:

```text
artifacts/runs/osu_phase3_motion_smoothing/
```

Checkpoints новой ветки:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/best_smooth.pt
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/latest_smooth.pt
```

## Зачем нужна фаза

После Phase 2/3 агент уже умеет попадать, держать timing и достаточно уверенно двигаться между объектами. Оставшаяся проблема — небольшой post-hit recoil: после нажатия на объект курсор иногда резко отлетает, делает лишний импульс или уходит от точки попадания не по полезной траектории.

Phase 3.5 фокусируется именно на моторике после попадания:

- уменьшить резкий отскок после hit;
- снизить jerk в первые кадры после попадания;
- сохранить полезный выход к следующей цели;
- не заставить агента бояться двигаться после клика;
- не сломать уже рабочие timing и hit behavior.

## Что добавлено в код

В `src/apps/train_osu.py` включена новая конфигурация:

- `phase_name = "phase3_5_post_hit_motion_smoothing"`;
- загрузка из `PATHS.phase2_best_checkpoint`;
- сохранение в `PATHS.phase3_smooth_*`;
- более осторожные PPO-параметры для fine-tuning;
- расширенное post-hit recoil-window;
- отдельный `smoothing` вклад в reward breakdown.

Новая shaping-логика учитывает:

- дистанцию от точки недавнего попадания;
- jerk после hit;
- слишком сильный отлёт от hit-anchor;
- направление выхода относительно следующей цели;
- мягкий направленный выход как положительный сигнал.

## Метрики

В training log добавлены:

- `smooth_r` — суммарный вклад smoothing reward;
- `rpx` — средняя дистанция от точки недавнего hit;
- `rjerk` — средний post-hit jerk;
- `badrec` — доля плохих recoil-шагов;
- `smooth` — доля мягких выходов к следующей цели.

Эти метрики нужны, чтобы видеть не только hit rate, но и качество движения после попадания.

## Eval / replay

`src/apps/eval_osu.py` теперь сначала ищет:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/best_smooth.pt
```

Если checkpoint ещё не создан, eval использует fallback:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt
```

Replay новой ветки сохраняется в:

```text
artifacts/runs/osu_phase3_motion_smoothing/replays/best_eval_replay.json
```

## Критерий закрытия

Фазу можно считать закрытой, когда `best_smooth.pt` на eval сохраняет хороший hit behavior Phase 2/3 и при просмотре replay заметно снижает post-hit отлёт без ухудшения перехода к следующей цели.
