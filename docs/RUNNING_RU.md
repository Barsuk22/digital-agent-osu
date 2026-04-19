# Запуск проекта

Актуально на 2026-04-19.

Документ описывает текущие команды запуска osu-модуля. Все команды выполняются из корня проекта:

```powershell
cd D:\Projects\digital_agent_osu_project
```

## Текущий статус

Phase 7 / Multi-Map Generalization закрыта.

Текущий основной checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Последний checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/latest_multimap.pt
```

Финальный лучший score:

```text
best cycle score = 12.342
```

Следующая планируемая стадия:

```text
Phase 8 / Easy Generalization & Pattern Formation
```

Подробности:

```text
docs/osu/phase7_multimap_generalization_status.md
docs/osu/phase8_easy_generalization_plan.md
```

## Обучение

Текущая команда:

```powershell
python -m src.apps.train_osu
```

На момент закрытия Phase 7 в `TrainConfig` лимит обновлений достигнут:

```text
updates = 1000
```

Поэтому повторный запуск Phase 7 training может сразу завершиться, сохранить `latest_multimap.pt` и вывести текущий `best cycle score`, не выполняя новых update. Это нормально: фаза завершена.

Для Phase 8 нужно будет создать отдельную run branch/config, чтобы не затирать Phase 7 golden checkpoint.

## Eval

Обычный запуск:

```powershell
python -m src.apps.eval_osu
```

Eval может использовать переменные окружения:

```powershell
$env:OSU_EVAL_CHECKPOINT='D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase7_multimap_generalization\checkpoints\best_multimap.pt'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_EVAL_CHECKPOINT
```

Выбор конкретной карты:

```powershell
$env:OSU_EVAL_MAP='D:\Projects\digital_agent_osu_project\data\raw\osu\maps\...\map.osu'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_EVAL_MAP
```

Можно комбинировать:

```powershell
$env:OSU_EVAL_CHECKPOINT='D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase7_multimap_generalization\checkpoints\best_multimap.pt'
$env:OSU_EVAL_MAP='D:\Projects\digital_agent_osu_project\data\raw\osu\maps\...\map.osu'
python -m src.apps.eval_osu
Remove-Item Env:\OSU_EVAL_CHECKPOINT
Remove-Item Env:\OSU_EVAL_MAP
```

Replay после eval сохраняется в:

```text
artifacts/runs/osu_phase7_multimap_generalization/replays/best_eval_replay.json
```

## Replay

```powershell
python -m src.apps.replay_osu
```

Команда открывает последний сохраненный eval replay.

## Live viewer

```powershell
python -m src.apps.live_viewer_osu
```

Это демонстрационный viewer-runner с простой policy. Он полезен для проверки среды и визуализации, но не является PPO eval текущего агента.

## Карты и медиа

Карты и медиа не входят в репозиторий. Локальные `.osu` файлы, аудио, фоны и видео ожидаются в:

```text
data/raw/osu/maps/
```

Активная карта и известные пути задаются в:

```text
src/core/config/paths.py
```

## Что смотреть в eval

Главные метрики:

- `hits` / `miss`;
- `tmed`, `good_t`, `early`, `late`, `off`;
- `near`, `far`, `dclick`;
- `sl_head`, `sl_fin`, `sl_tick`, `sl_drop`;
- `sl_inside_ratio`;
- `sl_follow_dist_mean`;
- `sl_finish_rate`;
- `sl_seg_q`;
- `sl_full`, `sl_partial`;
- `sl_rev_follow`, `sl_curve_good`;
- `spin_clear`, `spin_part`, `spin_miss`.

Для Phase 7/8 особенно важно:

- `far` около нуля на easy-картах;
- `sl_follow_dist_mean` не возвращается к 55-70 на старом gate pool;
- `sl_inside_ratio` и `sl_seg_q` остаются высокими;
- `sl_click_released_steps` около нуля на slider-heavy картах;
- старые Phase 7 карты не деградируют при переходе к Phase 8.

## Значение текущих checkpoint-файлов

### `best_multimap.pt`

Лучший checkpoint закрытой Phase 7. Выбран по полному cycle score на всех train-картах. Это текущий golden checkpoint.

### `latest_multimap.pt`

Последний checkpoint закрытой Phase 7. На финальном прогоне совпадает по смыслу с завершенной веткой, но для следующей фазы базой лучше считать `best_multimap.pt`.

### Старые checkpoint-ветки

Старые ветки остаются полезной историей и fallback-базами:

```text
artifacts/runs/osu_phase2_timing/
artifacts/runs/osu_phase3_motion_smoothing/
artifacts/runs/osu_phase4_slider_follow_fix/
artifacts/runs/osu_phase5_slider_control/
artifacts/runs/osu_phase6_spinner_control/
artifacts/runs/osu_spica_main_finetune/
```

Их не нужно перезаписывать при Phase 8.

## Важные замечания

- `artifacts/`, `data/raw/`, `exports/`, аудио, видео и checkpoints не должны храниться в git.
- Значимая часть параметров обучения пока находится в `TrainConfig` внутри `src/apps/train_osu.py`.
- Перед Phase 8 нужно завести отдельную run directory и отдельное имя checkpoint, чтобы сохранить Phase 7 как стабильный baseline.
