# Запуск проекта

## Текущий запуск: Phase 3.5 / Post-hit Motion Smoothing

Сейчас `python -m src.apps.train_osu` запускает не старую Phase 2/3 ветку, а следующий аккуратный fine-tuning этап для сглаживания движения после попадания.

Команда:

```bash
python -m src.apps.train_osu
```

Загрузка весов:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
```

Сохранение новой ветки:

```text
artifacts/runs/osu_phase3_motion_smoothing/
```

Новые checkpoints:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/best_smooth.pt
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/latest_smooth.pt
```

Подпапки run создаются автоматически:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/
artifacts/runs/osu_phase3_motion_smoothing/logs/
artifacts/runs/osu_phase3_motion_smoothing/metrics/
artifacts/runs/osu_phase3_motion_smoothing/replays/
artifacts/runs/osu_phase3_motion_smoothing/eval/
```

Старые `best.pt`, `best_recoil.pt` и `best_timing.pt` не перезаписываются. `best_reward` для smoothing-ветки начинается заново.

Дополнительные метрики в training log:

- `smooth_r` — суммарный reward сглаживания post-hit движения;
- `rpx` — средняя дистанция от точки недавнего hit в recoil-window;
- `rjerk` — средний jerk после hit;
- `badrec` — доля плохих post-hit отскоков;
- `smooth` — доля мягких выходов к следующей цели.

`eval_osu.py` теперь по умолчанию ищет `best_smooth.pt`. Если его ещё нет, eval откатывается к `best_timing.pt`, затем к `best_recoil.pt`.

Документ описывает текущие команды запуска osu-модуля. Все команды выполняются из корня проекта.

```bash
cd D:\Projects\digital_agent_osu_project
```

## Данные

Карты и медиа не входят в репозиторий. Локальные `.osu` файлы, аудио и фоны должны лежать в:

```text
data/raw/osu/maps/
```

Активная карта выбирается в `src/core/config/paths.py` через `PATHS.active_map`. На текущий момент активным путём является `easy_ka_map` из набора `StylipS - Spica`.

## Обучение Phase 2/3

```bash
python -m src.apps.train_osu
```

Команда запускает PPO fine-tuning текущей стадии:

- Phase 2 / Timing Refinement;
- Phase 3 / Aim Stability Refinement.

Обучение не начинается с нуля. Веса загружаются из:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt
```

Новая ветка сохраняется отдельно:

```text
artifacts/runs/osu_phase2_timing/
```

При старте training создаёт/использует подпапки:

```text
artifacts/runs/osu_phase2_timing/checkpoints/
artifacts/runs/osu_phase2_timing/logs/
artifacts/runs/osu_phase2_timing/metrics/
artifacts/runs/osu_phase2_timing/replays/
artifacts/runs/osu_phase2_timing/eval/
```

Новые checkpoints:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
artifacts/runs/osu_phase2_timing/checkpoints/latest_timing.pt
```

`best_reward` для этой ветки начинается заново. Старые checkpoints Phase 1 и recoil polishing не перезаписываются.

## Training log

В строке update теперь есть дополнительные метрики Phase 2/3:

- `tmean` — средняя абсолютная timing error;
- `tmed` — медианная абсолютная timing error;
- `good_t` — доля кликов в хорошем timing window;
- `early` — ранние клики;
- `late` — поздние клики;
- `off` — клики вне focus window;
- `dclick` — средняя дистанция до цели в момент клика;
- `near` — доля near clicks;
- `far` — доля far clicks;
- `stable` — доля стабильных pre-hit шагов;
- `exit` — доля хороших post-hit exits;
- `time+` / `time-` — timing bonus и penalty;
- `aim` — aim stability reward;
- `exit_r` — post-hit exit reward.

## Eval

```bash
python -m src.apps.eval_osu
```

Команда:

- загружает активную карту;
- по умолчанию загружает `PATHS.phase2_best_checkpoint`;
- выполняет deterministic rollout без обучения;
- сохраняет replay в phase2 run folder;
- печатает timing/aim summary;
- открывает viewer для просмотра результата.

Основной checkpoint eval:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
```

Если `best_timing.pt` ещё не создан, eval использует fallback:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt
```

Replay сохраняется в:

```text
artifacts/runs/osu_phase2_timing/replays/best_eval_replay.json
```

## Replay

```bash
python -m src.apps.replay_osu
```

Команда открывает phase2 eval replay:

```text
artifacts/runs/osu_phase2_timing/replays/best_eval_replay.json
```

Если phase2 replay ещё не создан, `replay_osu.py` может открыть старый phase1 eval replay как fallback. Для актуальной проверки лучше сначала выполнить:

```bash
python -m src.apps.eval_osu
```

## Live viewer

```bash
python -m src.apps.live_viewer_osu
```

Команда запускает viewer с простой `SimpleChasePolicy`. Она нужна для проверки среды и визуализации поведения, но это не основной PPO-agent запуск.

После закрытия viewer replay сохраняется в:

```text
artifacts/runs/osu_phase1_ppo/replays/latest_live_replay.json
```

## Значение checkpoint-файлов

### `best.pt`

Лучший базовый checkpoint Phase 1. Не перезаписывается текущей стадией.

### `latest.pt`

Последний базовый checkpoint Phase 1, если он есть. Не используется как основная база Phase 2/3.

### `best_recoil.pt`

Лучший checkpoint recoil/movement polishing ветки. Это база, от которой была построена Phase 2/3 timing/aim ветка.

### `latest_recoil.pt`

Последний checkpoint recoil/movement polishing ветки.

### `best_timing.pt`

Лучший checkpoint новой Phase 2/3 ветки.

### `latest_timing.pt`

Последний checkpoint новой Phase 2/3 ветки.

### `best_smooth.pt`

Лучший checkpoint текущей Phase 3.5 / Post-hit Motion Smoothing ветки. Он дообучается от `best_timing.pt`.

### `latest_smooth.pt`

Последний checkpoint текущей smoothing-ветки.

## Важные замечания

- Конфиги в `configs/osu/` и `configs/training/` частично являются заготовками. Значимая часть параметров обучения сейчас находится в `TrainConfig` внутри `src/apps/train_osu.py`.
- `artifacts/`, `data/raw/`, `exports/`, аудио и изображения игнорируются git.
- Для запуска нужны локальные зависимости Python, включая `torch`, `numpy` и `pygame`.
- Если активной карты нет на диске, parser не сможет запустить train/eval/viewer.
