# Текущий статус проекта

Актуально на 2026-04-19.

## Кратко

`digital_agent_osu_project` - модульный проект цифрового агента. osu-навык является отдельным skill module, где агент обучается моторному поведению через reinforcement learning, а не через scripted bot логику.

osu skill module прошел важную точку: **Phase 7 / Multi-Map Generalization закрыта**. Агент стабильно играет несколько beginner/easy карт, удерживает timing, click discipline, spinner behavior и снова уверенно ведет sliders после исправления tight-follow.

Текущий golden checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Следующая планируемая стадия:

```text
Phase 8 / Easy Generalization & Pattern Formation
```

## Главный итог Phase 7

Финальный лучший training cycle:

```text
[cycle 0200] score=12.342
mean_sel=8.956 min_sel=6.266 mean_hit=0.994
sl_inside=0.985 sl_fin=0.968 sl_q=0.987 spin_miss=0
```

Финальные eval-прогоны на `best_multimap.pt`:

```text
Chikatto held-out: hits=126 miss=1 sl_inside=0.890 dpx=38.9 sl_seg_q=0.930
Spica:            hits=99  miss=0 sl_inside=0.933 dpx=33.0 sl_seg_q=0.947
Suzuki:           hits=85  miss=1 sl_inside=0.981 dpx=27.4 sl_seg_q=0.980
MIMiNARI:         hits=91  miss=0 sl_inside=0.978 dpx=23.7 sl_seg_q=0.985
noa:              hits=120 miss=1 sl_inside=0.992 dpx=23.9 sl_seg_q=0.994
ONMYO-ZA:         hits=355 miss=1 sl_inside=0.948 dpx=32.0 sl_seg_q=0.958
```

`Sentimental Love` пока частичный перенос:

```text
hits=105 miss=6 sl_inside=0.695 dpx=57.1 sl_finish_rate=0.432 sl_seg_q=0.734
```

Это не блокер закрытия Phase 7. Наоборот, это хороший первый target для Phase 8.

## Статус фаз

### Phase 0 / Foundation

Статус: закрыта.

Сделано:

- parser `.osu`;
- environment;
- judgement;
- replay;
- pygame viewer.

### Phase 1 / Initial Learning / Base PPO Learning

Статус: закрыта.

Сделано:

- PPO training loop;
- Actor-Critic policy;
- rollout buffer / GAE;
- checkpoint save/load;
- deterministic eval;
- replay после eval.

### Phase 1.5 / Movement Polishing

Статус: закрыта как recoil/movement база.

### Phase 2 / Timing Refinement

Статус: закрыта как рабочая timing refinement ветка.

### Phase 3 / Aim Stability

Статус: закрыта как рабочая aim stability ветка.

### Phase 3.5 / Post-hit Motion Smoothing

Статус: закрыта.

Цель была убрать резкий post-hit recoil и сделать выход к следующей цели более мягким.

### Phase 4.1 / Slider Follow Fix

Статус: закрыта.

Цель была исправить ситуацию, где агент берет slider head, но не формирует устойчивый follow.

### Phase 5 / Slider Control

Статус: закрыта.

Цель была перейти от "hit head and hold" к управлению полным slider segment.

### Phase 6 / Spinner Control

Статус: закрыта.

Цель была добавить устойчивую spinner-моторику и диагностику.

### Spica Main Fine-Tune

Статус: закрыта как single-map baseline перед multi-map.

### Phase 7 / Multi-Map Generalization

Статус: закрыта.

Закрывающие признаки:

- агент играет несколько easy/beginner карт;
- Spica baseline не разрушен;
- held-out `Chikatto` проходит почти идеально;
- sliders восстановлены после multi-map degradation;
- best checkpoint выбирается по полному cycle score;
- spinner behavior не разрушен.

Подробности:

```text
docs/osu/phase7_multimap_generalization_status.md
```

### Phase 8 / Easy Generalization & Pattern Formation

Статус: следующая планируемая стадия.

Цель:

- расширить easy/generalization pool;
- довести `Sentimental Love` до уверенного slider-follow;
- сохранить Phase 7 gate pool почти идеальным;
- начать формировать короткие паттерны;
- не использовать hard/dense карты как обязательный gate.

План:

```text
docs/osu/phase8_easy_generalization_plan.md
```

## Состояние osu skill module

### Parser

Parser читает `.osu` файлы, metadata, difficulty, timing points, hit objects, audio/background/video events и строит внутренние модели circles/sliders/spinners.

### Environment

`OsuEnv` поддерживает:

- шаг симуляции;
- время;
- позицию курсора;
- action `dx, dy, click_strength`;
- observation с upcoming objects;
- reward через `OsuJudge`;
- done condition;
- replay frames.

### Judgement

`OsuJudge` поддерживает:

- circle judgement;
- slider head/follow/tick/finish/drop;
- spinner progress;
- combo;
- accuracy;
- miss handling;
- подробные метрики для train/eval.

Логика функциональна для RL-обучения, но не претендует на полную точность osu! lazer.

### Training

`src/apps/train_osu.py` содержит PPO pipeline и текущую Phase 7 конфигурацию. На момент закрытия Phase 7 лимит `updates=1000` достигнут, поэтому повторный запуск может сразу завершаться без новых update.

### Eval и replay

`src/apps/eval_osu.py` умеет загружать checkpoint, выполнять deterministic rollout, сохранять replay и печатать summary. Для явного выбора checkpoint и карты используются:

```powershell
$env:OSU_EVAL_CHECKPOINT='...'
$env:OSU_EVAL_MAP='...'
python -m src.apps.eval_osu
```

## Активные ограничения

- карты и медиа не лежат в репозитории;
- часть YAML-конфигов остается заготовками;
- значимая часть параметров обучения пока в `TrainConfig`;
- тестовая структура есть, но покрытие еще неполное;
- slider geometry и renderer упрощены;
- Phase 8 еще не реализована как отдельная training branch;
- skill memory еще не подключена к osu-поведению.

## Ближайшие направления

1. Зафиксировать Phase 7 `best_multimap.pt` как golden baseline.
2. Создать отдельную Phase 8 run branch/config.
3. Стартовать Phase 8 от `best_multimap.pt`.
4. Добавить `Sentimental Love` и `Chikatto` в более широкий easy curriculum.
5. Держать старый Phase 7 pool как regression gate.
6. Использовать `INTERNET YAMERO` и `Animal hard` только как stress-only eval, не как критерий успеха.
7. После Phase 8 думать о плотных картах и более сложных паттернах.
