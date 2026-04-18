# Phase 0 / Foundation — статус

Статус: закрыта.

Phase 0 была стадией построения честной osu-like среды, в которой агент может действовать, получать judgement и reward, а результат можно просмотреть через replay/viewer.

## Реализовано

### Parser

- чтение `.osu`;
- metadata и difficulty settings;
- timing points;
- circles;
- sliders;
- spinners;
- combo index и combo number;
- поиск audio/background рядом с картой.

### Environment

- текущее время `time_ms`;
- курсор `cursor_x`, `cursor_y`;
- action space `dx, dy, click_strength`;
- upcoming objects;
- distance и time-to-hit для observation;
- завершение эпизода после обработки объектов;
- запись replay frames.

### Judgement и reward

- `300 / 100 / 50 / miss`;
- проверка радиуса через CircleSize;
- timing windows через OD;
- combo и accuracy;
- miss expiration;
- базовая slider-логика;
- базовая spinner-логика.

### Viewer и replay

- pygame viewer;
- отображение карты, объектов, курсора и хвоста;
- эффекты кликов и judgement popups;
- combo/accuracy HUD;
- сохранение и загрузка replay JSON.

## Упрощения

- slider path приближённый, не 1:1 с osu! lazer;
- passthrough sliders пока обрабатываются упрощённо;
- viewer не является точным renderer osu! lazer;
- нет модели input lag;
- нет полной human-like моторной модели на уровне среды.

## Итог

Foundation-слой достаточно готов для RL-обучения и уже используется в PPO pipeline. Phase 0 не является активной стадией проекта, кроме точечных исправлений и уточнений.
