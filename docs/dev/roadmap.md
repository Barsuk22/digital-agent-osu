# Roadmap разработки

Этот roadmap описывает текущее положение проекта по состоянию кода, а не идеальный долгосрочный план.

## Где проект сейчас

osu skill module уже вышел за пределы черновой foundation-стадии. Базовый цикл обучения через PPO работает: агент взаимодействует с реальной `.osu` картой, получает reward, сохраняет checkpoints и может быть оценён через eval/replay.

Текущий фокус: полировка поведения и моторики.

## Закрыто

### Phase 0 / Foundation

Статус: закрыта.

Сделано:

- `.osu` parser;
- osu-like environment;
- action space `dx, dy, click_strength`;
- observation с текущим временем, курсором и upcoming objects;
- judgement для circles, sliders и spinners;
- replay frames;
- pygame viewer.

### Phase 1 / Initial Learning / Base PPO Learning

Статус: закрыта по смыслу как этап достижения базовой обучаемости.

Сделано:

- PPO training loop;
- Actor-Critic policy;
- rollout buffer и GAE;
- reward shaping для приближения, попаданий, дисциплины кликов и базовой моторики;
- загрузка базового checkpoint;
- сохранение `best.pt` / `latest.pt` на базовой ветке и отдельной fine-tune ветки;
- eval через deterministic policy;
- сохранение replay после eval.

## Активная стадия

### Phase 1.5 / Movement Polishing

Это текущая зона работы.

Фокус:

- плавность движения;
- снижение jerk и overspeed;
- anti-recoil после попаданий;
- мягкий выход от текущего объекта к следующему;
- улучшение useful click ratio;
- сохранение fine-tune checkpoint-ветки отдельно от базового checkpoint;
- развитие reward shaping без превращения агента в scripted bot.

## Дальше

### Phase 2 / Timing Quality

Цель: улучшить точность кликов во времени и уменьшить ранние/поздние нажатия.

Планируемые направления:

- более явные timing-метрики;
- reward вокруг hit window;
- штрафы за off-window click;
- сравнение deterministic eval между checkpoint-ветками.

### Phase 3 / Aim Stability

Цель: связать позицию курсора и клик более стабильно.

Планируемые направления:

- штрафы за click вне радиуса;
- устойчивое удержание около цели перед hit;
- анализ движения сразу после попаданий;
- снижение случайных микродвижений.

### Phase 4+ / Skills и Generalization

Дальнейшие этапы:

- более полная slider-поддержка;
- spinner behavior;
- обучение на нескольких картах;
- pattern formation;
- stability gate;
- skill extraction;
- skill memory и выбор навыков.

## Принцип проекта

Агент должен учиться через среду, reward и policy update. Документация не должна описывать его как scripted bot или как уже готового универсального osu-игрока.
