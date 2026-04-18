# Карта модулей

Проект строится как модульная архитектура цифрового агента. osu-навык — один из skill modules, а не отдельный изолированный прототип.

## Основные зоны

### `src/skills/osu`

Текущий самый развитый прикладной модуль.

Содержит:

- parser `.osu`;
- domain-модели;
- environment;
- judgement/reward logic;
- replay;
- pygame viewer;
- заготовки curriculum/training/evaluation слоёв.

### `src/apps`

Точки входа для запуска конкретных сценариев:

- `train_osu.py`;
- `eval_osu.py`;
- `replay_osu.py`;
- `live_viewer_osu.py`.

### `src/core`

Общие настройки и инфраструктура. Сейчас важнейшая часть для osu-модуля — `src/core/config/paths.py`, где задаются пути к картам, artifacts, checkpoints и replays.

### `src/learning`

Будущий общий слой обучения. В текущем osu pipeline значимая PPO-логика пока находится прямо в `src/apps/train_osu.py`, но структура под общий learning-layer уже заведена.

### `src/agent`

Будущий execution layer:

- planner;
- decision;
- controller;
- runtime.

### `src/girl`

Будущий character/persona layer:

- persona;
- thought;
- state;
- style;
- initiative;
- memory bridge;
- orchestration.

### `src/memory`

Будущие слои памяти:

- session;
- short-term;
- episodic;
- long-term;
- skill memory;
- consolidation.

### `src/world`

Будущие интерфейсы с внешним миром:

- audio;
- browser;
- desktop;
- game IO;
- sensors;
- vision.

## Коротко

- `skills/osu` — текущий обучаемый osu-навык.
- `apps` — запуск train/eval/replay/viewer.
- `core` — общая инфраструктура и пути.
- `learning` — будущая унификация RL/learning кода.
- `agent` — как агент действует.
- `girl` — кто она как персона/оркестратор.
- `memory` — где в будущем должны жить устойчивые навыки и опыт.
- `world` — как агент будет взаимодействовать с внешней средой.
