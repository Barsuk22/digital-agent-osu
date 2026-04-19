# Digital Agent OSU Project

## Current osu Baseline

As of 2026-04-19, the current working main-map baseline is the Spica main fine-tune:

```text
artifacts/runs/osu_spica_main_finetune/checkpoints/best_spica_main.pt
artifacts/runs/osu_spica_main_finetune/checkpoints/golden_spica_main.pt
```

It was fine-tuned from the Phase 6 spinner-capable checkpoint and evaluated on:

```text
StylipS - Spica. (TV-size) (Lanturn) [Beginner-ka].osu
```

Representative eval:

```text
hits=94 miss=0 clicks=27 good_t=0.889
sl_inside_ratio=0.823 sl_seg_q=0.839 spin_miss=0
```

Details:

- `docs/osu/spica_main_finetune_status.md`
- `docs/RUNNING_SPICA_MAIN.md`

## Актуальный этап

После Phase 2/3 в проекте появился рабочий `best_timing.pt`: агент продолжает обучаться от сильной recoil/movement базы, уверенно проходит eval на активной карте и сохраняет отдельную timing/aim ветку в `artifacts/runs/osu_phase2_timing/`.

Текущий следующий этап — **Phase 3.5 / Post-hit Motion Smoothing**. Он не переобучает агента с нуля и не затирает `best_recoil.pt` или `best_timing.pt`. Обучение стартует от:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
```

Новая ветка сохраняется отдельно:

```text
artifacts/runs/osu_phase3_motion_smoothing/
```

Основная цель этой стадии — убрать остаточную "отдачу" после hit: резкий отлёт от объекта, лишний jerk сразу после клика и бесполезные микроскачки. Агент уже умеет попадать; теперь полируется плавность выхода после попадания и более humanlike motion.

Модульный проект цифрового агента, в котором osu!-агент выступает отдельным skill module для обучения моторному поведению через reinforcement learning.

Это не scripted bot и не набор заранее записанных движений. Агент получает состояние osu-like среды, выбирает действие `(dx, dy, click_strength)`, получает reward через judgement-систему и обучается policy через PPO.

## Текущее состояние

Проект уже прошёл стадию первичной foundation-песочницы. Базовая обучаемость osu-агента достигнута: PPO-цикл реально запускается, агент играет по настоящей `.osu` карте, попадает по объектам, сохраняет checkpoints, проходит eval и может быть просмотрен через replay.

Активная стадия сейчас: Phase 3.5 / Post-hit Motion Smoothing. Phase 2 / Timing Refinement и Phase 3 / Aim Stability Refinement уже дали рабочий `best_timing.pt`; теперь фокус смещён к плавности выхода после hit и снижению остаточной "отдачи".

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
- **Phase 1.5 / Movement Polishing** — закрыта как recoil/movement база для следующей стадии.
- **Phase 2 / Timing Refinement и Phase 3 / Aim Stability Refinement** — реализованы как рабочая timing/aim ветка. Результат сохраняется в `artifacts/runs/osu_phase2_timing/`.
- **Текущая стадия** — Phase 3.5 / Post-hit Motion Smoothing. Идёт fine-tuning от `best_timing.pt` с отдельным сохранением в `artifacts/runs/osu_phase3_motion_smoothing/`.

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

Загружает текущий smoothing checkpoint `best_smooth.pt`, прогоняет deterministic policy по активной карте, сохраняет `best_eval_replay.json` в phase3 smoothing run folder и открывает просмотр replay. Если `best_smooth.pt` ещё не создан, eval использует `best_timing.pt`, затем `best_recoil.pt` как fallback.

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
- `artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt` — лучший checkpoint Phase 2/3 refinement.
- `artifacts/runs/osu_phase2_timing/checkpoints/latest_timing.pt` — последний checkpoint Phase 2/3 refinement.
- `artifacts/runs/osu_phase1_ppo/replays/best_eval_replay.json` — replay после eval.
- `artifacts/runs/osu_phase2_timing/replays/best_eval_replay.json` — replay после Phase 2/3 eval.
- `artifacts/runs/osu_phase1_ppo/replays/latest_live_replay.json` — replay после live viewer.

Fine-tuning checkpoint-ветки живут отдельно от базовых checkpoints. Это сделано намеренно: можно продолжать полировать timing и aim stability, не затирая `best.pt` и `best_recoil.pt`.

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
- [docs/osu/phase2_status.md](docs/osu/phase2_status.md) — текущий timing refinement.
- [docs/osu/phase3_aim_stabilization_draft.md](docs/osu/phase3_aim_stabilization_draft.md) — текущий aim stability refinement.
- [docs/osu/phase3_5_motion_smoothing_status.md](docs/osu/phase3_5_motion_smoothing_status.md) — активная стадия post-hit motion smoothing.

## Куда проект движется

Ближайшее развитие связано с качеством поведения, а не с повторным «первым запуском»:

- улучшение reward shaping для движения и кликов;
- сглаживание курсора и снижение резких отскоков после hit;
- anti-recoil fine-tuning;
- более humanlike movement;
- расширение eval-метрик;
- постепенный переход к multi-map generalization;
- дальнейшая интеграция osu-навыка в общую архитектуру цифрового агента и будущую skill memory.
