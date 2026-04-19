# Digital Agent OSU Project

Модульный проект цифрового агента, в котором osu!-агент выступает отдельным skill module для обучения моторному поведению через reinforcement learning.

Это не scripted bot и не набор заранее записанных движений. Агент получает состояние osu-like среды, выбирает действие `(dx, dy, click_strength)`, получает reward через judgement-систему и обучается policy через PPO.

## Текущий статус

Актуально на 2026-04-19: **Phase 7 / Multi-Map Generalization закрыта**.

Текущий golden checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Финальный лучший cycle score:

```text
best cycle score = 12.342
best mode = cycle_mean_min_slider_v1
```

Phase 7 закрыла beginner/easy multi-map milestone: агент стабильно играет несколько карт, сохраняет timing/click discipline, ведет sliders и не теряет spinner behavior.

Следующая стадия:

```text
Phase 8 / Easy Generalization & Pattern Formation
```

Цель Phase 8 - расширять easy/generalization pool и формировать короткие паттерны, не прыгая сразу в hard/dense карты.

## Итог Phase 7

Финальные eval-прогоны на `best_multimap.pt`:

```text
Chikatto held-out: hits=126 miss=1 sl_inside=0.890 dpx=38.9 sl_seg_q=0.930
Spica:            hits=99  miss=0 sl_inside=0.933 dpx=33.0 sl_seg_q=0.947
Suzuki:           hits=85  miss=1 sl_inside=0.981 dpx=27.4 sl_seg_q=0.980
MIMiNARI:         hits=91  miss=0 sl_inside=0.978 dpx=23.7 sl_seg_q=0.985
noa:              hits=120 miss=1 sl_inside=0.992 dpx=23.9 sl_seg_q=0.994
ONMYO-ZA:         hits=355 miss=1 sl_inside=0.948 dpx=32.0 sl_seg_q=0.958
```

`Sentimental Love` пока частично стабильна и назначена хорошим target-case для Phase 8:

```text
hits=105 miss=6 sl_inside=0.695 dpx=57.1 sl_finish_rate=0.432 sl_seg_q=0.734
```

Сложные экспериментальные карты вроде `Animal hard` и `INTERNET YAMERO [Easy]` не являются критерием закрытия Phase 7. Они показывают будущий разрыв по сложности и должны идти через отдельный curriculum.

## Что реализовано

- `.osu` parser: metadata, difficulty, timing points, circles, sliders, spinners, audio/background/video path resolution.
- osu-like environment: время, курсор, upcoming objects, action space, replay frames.
- Hit/judgement logic: circle judgement, slider head/follow/tick/finish/drop, spinner progress, combo, accuracy.
- PPO training loop в `src/apps/train_osu.py`.
- Checkpoint loading/saving для отдельных фаз.
- Eval pipeline в `src/apps/eval_osu.py`.
- Replay save/load и просмотр через pygame viewer.
- Reward shaping для approach, timing, click discipline, flow, smoothing, sliders и spinners.
- Cycle-based best checkpoint selection для multi-map обучения.
- Concise console logging с ключевыми метриками, включая `dpx` для slider-follow distance.

## Структура проекта

```text
configs/
  osu/                  # настройки judgement/viewer и заготовки конфигов osu
  training/             # заготовки конфигов обучения
data/
  raw/osu/maps/         # локальные osu-карты и медиа, не входят в репозиторий
artifacts/
  runs/                 # checkpoints, replays, logs, metrics
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

## Основные команды

Запуск из корня проекта:

```powershell
cd D:\Projects\digital_agent_osu_project
```

Training:

```powershell
python -m src.apps.train_osu
```

На момент закрытия Phase 7 лимит обновлений достигнут (`updates=1000`), поэтому повторный запуск текущей Phase 7 конфигурации может сразу завершиться. Для Phase 8 нужна отдельная run branch/config.

Eval:

```powershell
python -m src.apps.eval_osu
```

Eval конкретного checkpoint:

```powershell
$env:OSU_EVAL_CHECKPOINT='D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase7_multimap_generalization\checkpoints\best_multimap.pt'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_EVAL_CHECKPOINT
```

Eval конкретной карты:

```powershell
$env:OSU_EVAL_MAP='D:\Projects\digital_agent_osu_project\data\raw\osu\maps\...\map.osu'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_EVAL_MAP
```

Replay:

```powershell
python -m src.apps.replay_osu
```

## Карты и медиа

Карты, аудио, фоны, видео, artifacts, exports и checkpoints не хранятся в репозитории.

Локальные `.osu` карты ожидаются в:

```text
data/raw/osu/maps/
```

Активные пути задаются в:

```text
src/core/config/paths.py
```

## Документация

- [docs/PROJECT_STATUS_RU.md](docs/PROJECT_STATUS_RU.md) - текущий статус проекта и фаз.
- [docs/RUNNING_RU.md](docs/RUNNING_RU.md) - запуск train/eval/replay и объяснение checkpoints.
- [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md) - общий план развития osu skill module.
- [docs/osu/curriculum_plan.md](docs/osu/curriculum_plan.md) - текущий curriculum snapshot.
- [docs/osu/phase7_multimap_generalization_status.md](docs/osu/phase7_multimap_generalization_status.md) - закрытие Phase 7.
- [docs/osu/phase8_easy_generalization_plan.md](docs/osu/phase8_easy_generalization_plan.md) - план следующей фазы.

## Куда проект движется

Ближайшее развитие:

- зафиксировать Phase 7 checkpoint как baseline;
- создать отдельную Phase 8 run branch;
- добавить больше easy/near-easy карт;
- довести held-out slider maps до стабильности;
- сохранить старый Phase 7 pool как regression gate;
- постепенно переходить к более плотным паттернам;
- hard/dense карты включать только после промежуточной лестницы сложности.
