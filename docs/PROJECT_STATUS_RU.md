# Текущий статус проекта

## Актуализация: Phase 3.5

Phase 2 / Timing Refinement и Phase 3 / Aim Stability Refinement теперь считаются реализованной рабочей веткой refinement: она стартовала от `best_recoil.pt`, сохранялась отдельно в `artifacts/runs/osu_phase2_timing/` и дала checkpoint `best_timing.pt`, который можно использовать как сильную базу для следующей полировки.

Текущая активная стадия — **Phase 3.5 / Post-hit Motion Smoothing**. Это не новая попытка обучить агента играть с нуля. Это короткий и осторожный fine-tuning от:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
```

Результаты сохраняются в отдельную ветку:

```text
artifacts/runs/osu_phase3_motion_smoothing/
```

Новые checkpoints:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/best_smooth.pt
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/latest_smooth.pt
```

Цель Phase 3.5 — убрать остаточный post-hit recoil: резкий отскок после клика, лишний jerk в первые кадры после попадания и случайную болтанку вместо мягкого выхода к следующей цели. У агента уже есть базовая обучаемость, timing refinement и aim stability; сейчас фокус именно на качестве моторики.

## Кратко

`digital_agent_osu_project` — модульный проект цифрового агента. osu-навык является отдельным skill module внутри более широкой архитектуры, где в будущем должны появляться память, skill memory, orchestration, world interfaces и другие навыки.

osu skill module уже не находится на уровне черновой песочницы. Базовая обучаемость достигнута: PPO-агент обучается на настоящей osu-карте, взаимодействует с объектами, сохраняет checkpoints, проходит eval и даёт replay для просмотра.

Текущая стадия разработки — Phase 3.5 / Post-hit Motion Smoothing поверх уже сильной timing/aim policy `best_timing.pt`.

## Статус фаз

### Phase 0 / Foundation

Статус: закрыта.

Закрывающие признаки:

- parser читает `.osu` карты;
- environment даёт observation и принимает action;
- judgement считает попадания, промахи, combo и accuracy;
- replay записывается и воспроизводится;
- pygame viewer показывает карту и действия агента.

### Phase 1 / Initial Learning / Base PPO Learning

Статус: закрыта по смыслу как этап достижения базовой обучаемости.

Закрывающие признаки:

- есть PPO training loop;
- policy обучается через rollout и reward;
- агент играет по реальной карте;
- есть попадания по объектам;
- checkpoints сохраняются и загружаются;
- eval использует deterministic policy;
- результат eval сохраняется в replay.

### Phase 1.5 / Movement Polishing

Статус: базовая recoil/movement polishing ветка закрыта как стартовая база для следующего refinement.

Фокус:

- motion smoothing;
- anti-recoil после hit;
- снижение резких импульсов движения;
- улучшение useful click ratio;
- развитие flow между объектами;
- humanlike movement polishing;
- дальнейшее reward shaping.

### Phase 2 / Timing Refinement

Статус: реализована и закрыта как рабочая timing-refinement база.

Фокус:

- загрузка весов из `best_recoil.pt`;
- отдельный run folder `artifacts/runs/osu_phase2_timing/`;
- timing metrics в train/eval;
- мягкий timing bonus/penalty;
- отдельный reward breakdown для timing.

### Phase 3 / Aim Stability Refinement

Статус: реализована и закрыта вместе с Phase 2 как рабочая aim-stability база.

Фокус:

- pre-hit positioning;
- near/far/settled/unstable click distinction;
- micro-stability около цели;
- post-hit exit quality;
- отдельные aim и exit metrics.

## Состояние osu skill module

### Parser

Реализован parser для `.osu` файлов. Он извлекает metadata, difficulty, timing points, hit objects, audio/background filenames и строит внутренние модели для circles, sliders и spinners.

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
- miss handling.

Логика достаточно функциональна для обучения, но не претендует на полную точность osu! lazer.

### Training

`src/apps/train_osu.py` содержит полноценный PPO pipeline:

- Actor-Critic model;
- Normal distribution policy;
- rollout buffer;
- GAE;
- PPO update;
- reward shaping;
- checkpoint save/load;
- fine-tuning ветку Phase 2/3 для timing и aim stability refinement;
- текущую Phase 3.5 ветку для post-hit motion smoothing.

### Eval и replay

`src/apps/eval_osu.py` сначала загружает phase3 smoothing checkpoint, выполняет deterministic rollout, сохраняет replay, печатает timing/aim summary и показывает результат через viewer. Если `best_smooth.pt` ещё не создан, eval откатывается к `best_timing.pt`, затем к `best_recoil.pt`.

`src/apps/replay_osu.py` открывает сохранённый eval replay.

`src/apps/live_viewer_osu.py` использует простую `SimpleChasePolicy` для live-визуализации среды. Это демонстрационный viewer-runner, а не основной PPO eval.

## Checkpoint-ветки

Базовая ветка:

- `best.pt`;
- `latest.pt`.

Recoil fine-tune ветка:

- `best_recoil.pt`;
- `latest_recoil.pt`.

Phase 2/3 ветка:

- `artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt`;
- `artifacts/runs/osu_phase2_timing/checkpoints/latest_timing.pt`.

Разделение важно: timing/aim refinement стартует от `best_recoil.pt`, но сохраняется отдельно и не затирает ни `best.pt`, ни `best_recoil.pt`.

## Активные ограничения

- карты и медиа не лежат в репозитории;
- часть YAML-конфигов пока является заготовками;
- `train_osu.py` сейчас содержит много конфигурации прямо в `TrainConfig`;
- тестовая структура есть, но сами тесты в основном ещё не наполнены;
- slider geometry и renderer упрощены;
- multi-map generalization ещё не закрыта;
- skill memory ещё не подключена к osu-поведению.

## Ближайшие направления

- стабилизировать Phase 3.5 smoothing fine-tune ветку;
- сравнить `best_timing.pt` и `best_smooth.pt` на eval/replay;
- расширить eval-метрики и сохранить их в metrics/logs;
- аккуратно вынести параметры Phase 2/3 и Phase 3.5 в конфиги;
- аккуратно вынести часть параметров в конфиги;
- добавить тесты для parser, judgement и replay;
- перейти к нескольким easy-картам;
- подготовить stability gate для будущего skill extraction.
