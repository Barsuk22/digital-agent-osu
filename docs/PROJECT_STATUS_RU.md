# Текущий статус проекта

## Кратко

`digital_agent_osu_project` — модульный проект цифрового агента. osu-навык является отдельным skill module внутри более широкой архитектуры, где в будущем должны появляться память, skill memory, orchestration, world interfaces и другие навыки.

osu skill module уже не находится на уровне черновой песочницы. Базовая обучаемость достигнута: PPO-агент обучается на настоящей osu-карте, взаимодействует с объектами, сохраняет checkpoints, проходит eval и даёт replay для просмотра.

Текущая стадия разработки — полировка поведения и моторики.

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

Статус: активная стадия.

Фокус:

- motion smoothing;
- anti-recoil после hit;
- снижение резких импульсов движения;
- улучшение useful click ratio;
- развитие flow между объектами;
- humanlike movement polishing;
- дальнейшее reward shaping.

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
- fine-tuning ветку для anti-recoil/motion polishing.

### Eval и replay

`src/apps/eval_osu.py` загружает checkpoint, выполняет deterministic rollout, сохраняет replay и показывает его через viewer.

`src/apps/replay_osu.py` открывает сохранённый eval replay.

`src/apps/live_viewer_osu.py` использует простую `SimpleChasePolicy` для live-визуализации среды. Это демонстрационный viewer-runner, а не основной PPO eval.

## Checkpoint-ветки

Базовая ветка:

- `best.pt`;
- `latest.pt`.

Fine-tune ветка:

- `best_recoil.pt`;
- `latest_recoil.pt`.

Разделение важно: fine-tuning на плавность и anti-recoil может развиваться отдельно от базового лучшего checkpoint. Это позволяет экспериментировать с моторикой, не затирая исходную Phase 1 policy.

## Активные ограничения

- карты и медиа не лежат в репозитории;
- часть YAML-конфигов пока является заготовками;
- `train_osu.py` сейчас содержит много конфигурации прямо в `TrainConfig`;
- тестовая структура есть, но сами тесты в основном ещё не наполнены;
- slider geometry и renderer упрощены;
- multi-map generalization ещё не закрыта;
- skill memory ещё не подключена к osu-поведению.

## Ближайшие направления

- стабилизировать fine-tune ветку;
- расширить eval-метрики;
- сравнивать базовые и recoil checkpoints;
- улучшить reward shaping для timing и click discipline;
- аккуратно вынести часть параметров в конфиги;
- добавить тесты для parser, judgement и replay;
- перейти к нескольким easy-картам;
- подготовить stability gate для будущего skill extraction.
