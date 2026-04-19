# Digital Agent OSU Project

Модульный проект цифрового агента, где osu!-агент выступает отдельным skill module для обучения моторному поведению через reinforcement learning.

Это не scripted bot и не набор заранее записанных движений. Агент получает состояние osu-like среды, выбирает действие `(dx, dy, click_strength)`, получает reward через judgement-систему и обучается policy через PPO.

## Текущий статус

Актуально на 2026-04-19.

Phase 7 / Multi-Map Generalization закрыта.
Phase 8.1 / Easy Generalization + Stability Gate закрыта.
Phase 9 / Gate Report пройдена как короткая проверка стабильности.

Лучший Phase 7 checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Финальный Phase 7 score:

```text
best cycle score = 12.342
best mode = cycle_mean_min_slider_v1
```

Следующая планируемая стадия:

```text
Phase 10 / Skill Memory Init
```

Phase 8 и Phase 9 были объединены: Phase 8 обучила расширенный easy/generalization curriculum, а Phase 9 была встроена как stability gate при выборе best checkpoint и подтверждена отдельными eval-прогонами.

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

`Sentimental Love` пока частично стабильна и стала главным target-case для Phase 8.1:

```text
hits=105 miss=6 sl_inside=0.695 dpx=57.1 sl_finish_rate=0.432 sl_seg_q=0.734
```

`Animal hard` и `INTERNET YAMERO [Easy]` остаются stress-only eval. Они не являются критерием закрытия easy/generalization стадии.

## Phase 8.1

Статус: закрыта 2026-04-19.

Стартовая база:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Новая run-директория:

```text
artifacts/runs/osu_phase8_easy_generalization/
```

Checkpoint-и:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/latest_easy_generalization.pt
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Best mode:

```text
cycle_easy_generalization_gate_v1
```

Curriculum:

```text
1. StylipS - Spica. (TV-size) [Beginner-ka]
2. Suzuki Minori - Dame wa Dame (TV Size) [maikayuii's Beginner]
3. MIMiNARI - Itowanai feat. Tomita Miyu, Ichinose Kana (TV Size) [Teages's Easy]
4. noa - Megane o Hazushite (TV Size) [Easy]
5. ONMYO-ZA - Kouga Ninpouchou [JauiPlaY's Easy]
6. Sati Akura - Sentimental Love (TV Size) [Myxo's Easy]
7. Sati Akura - Chikatto Chika Chika [Easy]
```

Роли:

- `gate`: первые 5 карт, старый Phase 7 regression gate;
- `target`: `Sentimental Love`;
- `heldout`: `Chikatto Chika Chika`.

Финальный best:

```text
best cycle score = 12.486
best checkpoint = artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Phase 9 gate-report на `best_easy_generalization.pt`:

```text
Chikatto:          hits=133 miss=0 sl_inside=0.997 dpx=23.2 sl_seg_q=0.997
Sentimental Love:  hits=124 miss=3 sl_inside=0.951 dpx=32.5 sl_seg_q=0.961
Spica:             hits=84  miss=4 sl_inside=0.985 dpx=22.8 sl_seg_q=0.980
Suzuki:            hits=85  miss=1 sl_inside=1.000 dpx=26.7 sl_seg_q=1.000
MIMiNARI:          hits=91  miss=0 sl_inside=1.000 dpx=23.4 sl_seg_q=1.000
noa:               hits=120 miss=0 sl_inside=0.983 dpx=20.5 sl_seg_q=0.993
ONMYO-ZA:          hits=359 miss=2 sl_inside=0.980 dpx=28.4 sl_seg_q=0.981
YOASOBI held-out:  hits=129 miss=0 sl_inside=0.923 dpx=40.0 sl_seg_q=0.952
```

Вывод: easy/generalization перенос подтвержден. `Sentimental Love` больше не является 50/50 case, `Chikatto` и новая held-out easy карта проходят уверенно, старый gate pool удержан без критического регресса. Главная заметка на будущее: timing drift часто ранний, поэтому timing calibration стоит держать отдельной задачей следующих фаз.

## Phase 10

Статус: планируется.

Цель: начать сохранять устойчивые успешные паттерны как первые элементы skill memory.

Кандидаты:

- slider follow;
- reverse slider;
- short chain;
- spinner control;
- simple jump/double.

## Основные команды

Из корня проекта:

```powershell
cd D:\Projects\digital_agent_osu_project
```

Training:

```powershell
python -m src.apps.train_osu
```

Eval:

```powershell
python -m src.apps.eval_osu
```

Replay:

```powershell
python -m src.apps.replay_osu
```

Eval конкретного checkpoint:

```powershell
$env:OSU_EVAL_CHECKPOINT='D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase8_easy_generalization\checkpoints\best_easy_generalization.pt'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_EVAL_CHECKPOINT
```

Eval конкретной карты:

```powershell
$env:OSU_EVAL_MAP='D:\Projects\digital_agent_osu_project\data\raw\osu\maps\...\map.osu'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_EVAL_MAP
```

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
- Phase 8.1 stability gate с ролями `gate`, `target`, `heldout`.

## Структура проекта

```text
configs/
  osu/
  training/
data/
  raw/osu/maps/
artifacts/
  runs/
docs/
  osu/
  dev/
src/
  apps/
  core/config/paths.py
  skills/osu/
  learning/
  agent/
  girl/
  memory/
  world/
tests/
```

## Карты и медиа

Карты, аудио, фоны, видео, artifacts, exports и checkpoints не хранятся в репозитории.

Локальные `.osu` карты ожидаются здесь:

```text
data/raw/osu/maps/
```

Известные пути задаются в:

```text
src/core/config/paths.py
```

## Документация

- [docs/PROJECT_STATUS_RU.md](docs/PROJECT_STATUS_RU.md)
- [docs/RUNNING_RU.md](docs/RUNNING_RU.md)
- [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md)
- [docs/osu/curriculum_plan.md](docs/osu/curriculum_plan.md)
- [docs/osu/reward_design.md](docs/osu/reward_design.md)
- [docs/osu/phase7_multimap_generalization_status.md](docs/osu/phase7_multimap_generalization_status.md)
- [docs/osu/phase8_easy_generalization_plan.md](docs/osu/phase8_easy_generalization_plan.md)
