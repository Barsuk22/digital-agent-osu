# Digital Agent OSU Project

Модульный проект цифрового агента, в котором osu!-агент выступает отдельным skill module для обучения моторному поведению через reinforcement learning.

Это не scripted bot и не набор заранее записанных движений. Агент получает состояние osu-like среды, выбирает действие `(dx, dy, click_strength)`, получает reward через judgement-систему и обучается policy через PPO.

## Текущее состояние

Проект уже прошёл стадию первичной foundation-песочницы. Базовая обучаемость osu-агента достигнута: PPO-цикл реально запускается, агент играет по настоящей `.osu` карте, попадает по объектам, сохраняет checkpoints, проходит eval и может быть просмотрен через replay.

Активная стадия сейчас: полировка поведения и моторики. Основной фокус уже не в том, чтобы «заставить агента хоть как-то двигаться», а в улучшении качества игры: сглаживание движения, anti-recoil после попаданий, humanlike movement, дисциплина кликов и дальнейшее развитие reward shaping.

## Что уже реализовано

- `.osu` parser: metadata, difficulty, timing points, circles, sliders, spinners, audio/background path resolution.
- osu-like environment: время, курсор, upcoming objects, action space, replay frames.
- Hit/judgement logic: `300 / 100 / 50 / miss`, radius check, timing windows, combo, accuracy.
- Базовая slider-логика: head hit, follow reward, ticks, finish/drop.
- Базовая spinner-логика: прогресс вращения и оценка результата.
- PPO training loop в `src/apps/train_osu.py`.
- Checkpoint loading/saving для базовой и fine-tune веток.
- Eval pipeline в `src/apps/eval_osu.py`.
- Replay save/load и просмотр через pygame viewer.
- Reward shaping для approach, timing/click discipline, flow, jerk/overspeed penalties и anti-recoil fine-tuning.

## Фазы

- **Phase 0 / Foundation** — закрыта. Есть parser, environment, judgement, replay и viewer.
- **Phase 1 / Initial Learning / Base PPO Learning** — закрыта по смыслу как базовый этап. Агент уже обучается через PPO и показывает базовое взаимодействие с реальной картой.
- **Текущая стадия** — polishing / Phase 1.5. Идёт донастройка качества движения: плавность, anti-recoil, полезность кликов, выход после попадания к следующей цели, более человекоподобная моторика.

Важно: это не означает, что агент уже играет идеально или стабильно на широком наборе карт. Это означает, что стадия «первого запуска обучения» пройдена, а текущая работа сместилась к качеству поведения.

## Структура проекта

```text
configs/
  osu/                  # настройки judgement/viewer и заготовки конфигов osu
  training/             # заготовки конфигов обучения
data/
  raw/osu/maps/         # локальные osu-карты и медиа, не входят в репозиторий
artifacts/
  runs/osu_phase1_ppo/  # checkpoints, replays, logs, metrics
docs/
  osu/                  # спецификации и статусы osu-модуля
  dev/                  # roadmap и dev-документы
src/
  apps/                 # точки входа train/eval/replay/viewer
  core/config/paths.py  # централизованные пути проекта
  skills/osu/           # osu skill module
  learning/             # общий слой будущей RL/learning архитектуры
  agent/                # будущий execution/control слой
  girl/                 # будущая персона/оркестрация цифрового агента
  memory/               # будущие слои памяти и skill memory
  world/                # будущие интерфейсы с внешним миром
tests/                  # заготовленная структура тестов
```

## Основные точки входа

```bash
python -m src.apps.train_osu
```

Запускает PPO fine-tuning. Текущая конфигурация стартует от базового checkpoint `best.pt` или `latest.pt` и сохраняет отдельную recoil/fine-tune ветку.

```bash
python -m src.apps.eval_osu
```

Загружает текущий `best_recoil.pt`, прогоняет deterministic policy по активной карте, сохраняет `best_eval_replay.json` и открывает просмотр replay.

```bash
python -m src.apps.replay_osu
```

Открывает последний сохранённый eval replay.

```bash
python -m src.apps.live_viewer_osu
```

Запускает viewer с простой демонстрационной `SimpleChasePolicy`. Это полезно для проверки среды и визуализации, но это не PPO-agent eval.

Подробности по запуску и checkpoint-файлам: [docs/RUNNING_RU.md](docs/RUNNING_RU.md).

## Checkpoints и replay

По умолчанию пути задаются в `src/core/config/paths.py`.

- `artifacts/runs/osu_phase1_ppo/checkpoints/best.pt` — базовый лучший checkpoint Phase 1.
- `artifacts/runs/osu_phase1_ppo/checkpoints/latest.pt` — базовый последний checkpoint Phase 1, если он есть.
- `artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt` — лучший checkpoint текущей fine-tune ветки.
- `artifacts/runs/osu_phase1_ppo/checkpoints/latest_recoil.pt` — последний checkpoint текущей fine-tune ветки.
- `artifacts/runs/osu_phase1_ppo/replays/best_eval_replay.json` — replay после eval.
- `artifacts/runs/osu_phase1_ppo/replays/latest_live_replay.json` — replay после live viewer.

Fine-tuning checkpoint-ветка живёт отдельно от базового лучшего checkpoint. Это сделано намеренно: можно продолжать полировать моторику, не затирая базовую обученную policy.

## Карты и медиа

Карты, аудио, фоны, artifacts, exports и checkpoints не должны храниться в репозитории. Они игнорируются через `.gitignore`.

Локальные `.osu` карты ожидаются в:

```text
data/raw/osu/maps/
```

Активная карта сейчас задаётся в `src/core/config/paths.py` через `PATHS.active_map`.

## Документация

- [docs/PROJECT_STATUS_RU.md](docs/PROJECT_STATUS_RU.md) — текущий статус проекта и фаз.
- [docs/RUNNING_RU.md](docs/RUNNING_RU.md) — запуск train/eval/replay и объяснение checkpoints.
- [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md) — общий план развития osu skill module.
- [docs/osu/phase0_status.md](docs/osu/phase0_status.md) — закрытая foundation-стадия.
- [docs/osu/phase1_status.md](docs/osu/phase1_status.md) — закрытый базовый PPO learning этап и переход к polishing.

## Куда проект движется

Ближайшее развитие связано с качеством поведения, а не с повторным «первым запуском»:

- улучшение reward shaping для движения и кликов;
- сглаживание курсора и снижение резких отскоков после hit;
- anti-recoil fine-tuning;
- более humanlike movement;
- расширение eval-метрик;
- постепенный переход к multi-map generalization;
- дальнейшая интеграция osu-навыка в общую архитектуру цифрового агента и будущую skill memory.
