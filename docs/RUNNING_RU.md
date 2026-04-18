# Запуск проекта

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

## Обучение

```bash
python -m src.apps.train_osu
```

Команда запускает PPO fine-tuning на активной карте.

Текущее поведение:

- строит `OsuEnv` по активной `.osu` карте;
- создаёт Actor-Critic model;
- загружает базовый checkpoint;
- выполняет rollout;
- считает PPO update;
- печатает метрики обучения;
- сохраняет fine-tune checkpoints.

По умолчанию `TrainConfig.resume_from_best = True`, поэтому старт идёт от:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/best.pt
```

Если в коде переключить `resume_from_best = False`, старт будет от:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/latest.pt
```

Fine-tune результат сохраняется отдельно:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt
artifacts/runs/osu_phase1_ppo/checkpoints/latest_recoil.pt
```

## Eval

```bash
python -m src.apps.eval_osu
```

Команда:

- загружает активную карту;
- загружает checkpoint `PATHS.best_checkpoint`;
- выполняет deterministic rollout без обучения;
- сохраняет replay;
- открывает viewer для просмотра результата.

Сейчас `PATHS.best_checkpoint` указывает на:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt
```

Replay сохраняется в:

```text
artifacts/runs/osu_phase1_ppo/replays/best_eval_replay.json
```

## Replay

```bash
python -m src.apps.replay_osu
```

Команда открывает сохранённый eval replay:

```text
artifacts/runs/osu_phase1_ppo/replays/best_eval_replay.json
```

Если replay ещё не создан, сначала нужно выполнить:

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

Лучший базовый checkpoint Phase 1. Используется как стартовая точка для текущего fine-tuning, если `resume_from_best = True`.

### `latest.pt`

Последний базовый checkpoint Phase 1. Может использоваться как альтернативная стартовая точка, если `resume_from_best = False`.

### `best_recoil.pt`

Лучший checkpoint текущей fine-tune ветки. Именно он сейчас используется eval-командой через `PATHS.best_checkpoint`.

### `latest_recoil.pt`

Последний checkpoint текущей fine-tune ветки. Используется для продолжения/анализа свежего состояния обучения, но eval по умолчанию берёт `best_recoil.pt`.

### `backup_pre_recoil.pt`

Локальный backup перед recoil fine-tuning. Это artifact, не часть обязательной логики запуска.

## Важные замечания

- Конфиги в `configs/osu/` и `configs/training/` частично являются заготовками. Значимая часть параметров обучения сейчас находится в `TrainConfig` внутри `src/apps/train_osu.py`.
- `artifacts/`, `data/raw/`, `exports/`, аудио и изображения игнорируются git.
- Для запуска нужны локальные зависимости Python, включая `torch`, `numpy` и `pygame`.
- Если активной карты нет на диске, parser не сможет запустить train/eval/viewer.
