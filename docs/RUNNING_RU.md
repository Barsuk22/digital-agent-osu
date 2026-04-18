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
# Phase 4.1 / Slider Follow Fix

Запуск обучения:

```powershell
python -m src.apps.train_osu
```

По умолчанию обучение стартует не с нуля, а из:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/best_smooth.pt
```

Новые checkpoint сохраняются сюда:

```text
artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/latest_slider_follow.pt
artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/best_slider_follow.pt
```

Запуск eval:

```powershell
python -m src.apps.eval_osu
```

Eval сначала ищет:

```text
artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/best_slider_follow.pt
```

Если его еще нет, явно откатывается на phase3/phase2 fallback. Replay для новой ветки сохраняется в:

```text
artifacts/runs/osu_phase4_slider_follow_fix/replays/best_eval_replay.json
```

Открыть replay:

```powershell
python -m src.apps.replay_osu
```

Проверить, что slider-follow достижим в env/judge без PPO:

```powershell
python -m src.apps.debug_slider_follow
```

Команда сохраняет компактный trace первого slider в:

```text
artifacts/runs/osu_phase4_slider_follow_fix/metrics/slider_follow_debug_trace.json
```

В логах Phase 4.1 нужно смотреть не только hit rate, но и `sl_inside_ratio`, `sl_follow_dist_mean`, `sl_follow_gain`, `sl_progress_gain`, `sl_finish_rate`, `sl_tick_hit_rate`.

Для диагностики tap-vs-hold поведения смотри:

- `sl_click_hold_steps`;
- `sl_click_release_count`;
- `sl_post_head_hold_ratio`;
- `sl_click_released_ratio`;
- `sl_geom_inside_ratio`;
- `sl_time_to_first_inside`;
- `sl_target_align`.

После head-to-hold диагностики добавлены:

- `sl_head_to_hold`;
- `sl_release_after_head`;
- `sl_hold_steps_mean`;
- `sl_first_hold_delay`;
- `sl_near_hold_ratio`;
- `sl_near_released_ratio`.

В Phase 4.1 обычный click/head/circle threshold остается строгим (`0.75`), а hold во время уже активного slider использует отдельный более мягкий порог (`0.45`). Это нужно только для обучения sustained hold и не должно менять circle timing.

Для диагностики path-tracking после того, как hold начал оживать, смотри:

- `sl_track_good`;
- `sl_track_bad`;
- `sl_stall`;
- `sl_wrong_dir`;
- `sl_chain_mean`;
- `sl_chain_max`;
- `sl_prog_hold`;
- `sl_prog_inside`;
- `sl_d_hold`;
- `sl_d_inside`.

# Phase 5 / Slider Control

`python -m src.apps.train_osu` теперь запускает Phase 5 / Slider Control.

Это отдельная фаза после Phase 4.1. Она стартует не с нуля, а из:

```text
artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/best_slider_follow.pt
```

Новые артефакты сохраняются отдельно:

```text
artifacts/runs/osu_phase5_slider_control/
artifacts/runs/osu_phase5_slider_control/checkpoints/latest_slider_control.pt
artifacts/runs/osu_phase5_slider_control/checkpoints/best_slider_control.pt
artifacts/runs/osu_phase5_slider_control/replays/best_eval_replay.json
```

Eval теперь сначала ищет:

```text
artifacts/runs/osu_phase5_slider_control/checkpoints/best_slider_control.pt
```

Если Phase 5 checkpoint еще не создан, eval откатывается на Phase 4.1, затем phase3/phase2/base fallback.

Debug sanity:

```powershell
python -m src.apps.debug_slider_follow
```

Trace сохраняется в:

```text
artifacts/runs/osu_phase5_slider_control/metrics/slider_control_debug_trace.json
```

В логах Phase 5 дополнительно смотри:

- `sl_seg_q` - качество ведения slider segments;
- `sl_full` - full-quality slider completions;
- `sl_partial` - частичные completions;
- `sl_rev` - detected reverse events;
- `sl_rev_follow` - follow ratio во время reverse window;
- `sl_curve` - curved/path-change steps;
- `sl_curve_good` - quality на curved/path-change steps.

Главная цель Phase 5: не просто высокий `sl_head`, а рост `sl_inside_ratio`, `sl_tick_hit_rate`, `sl_finish_rate`, `sl_chain_mean`, `sl_chain_max` и `sl_seg_q` без разрушения circle timing.
