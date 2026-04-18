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

### Phase 3.5 / Post-hit Motion Smoothing

Это текущая зона работы после получения `best_timing.pt`.

Фокус:

- загрузка из `artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt`;
- сохранение в `artifacts/runs/osu_phase3_motion_smoothing/`;
- уменьшение резкого отскока после hit;
- снижение post-hit jerk;
- сохранение полезного выхода к следующей цели;
- отдельные метрики `smooth_r`, `rpx`, `rjerk`, `badrec`, `smooth`.

## Закрытая refinement-ветка

### Phase 2 / Timing Refinement + Phase 3 / Aim Stability Refinement

Эта ветка реализована и считается рабочей базой для Phase 3.5.

Фокус:

- загрузка из `best_recoil.pt`;
- сохранение в `artifacts/runs/osu_phase2_timing/`;
- timing metrics и timing reward breakdown;
- near/far/settled/unstable click distinction;
- pre-hit stability;
- post-hit exit quality;
- сохранение старых Phase 1 checkpoints без перезаписи.

## Дальше

### Phase 2 / Timing Quality

Статус: реализована и закрыта как часть Phase 2/3 refinement ветки.

Цель: улучшить точность кликов во времени и уменьшить ранние/поздние нажатия.

Планируемые направления:

- более явные timing-метрики;
- reward вокруг hit window;
- штрафы за off-window click;
- сравнение deterministic eval между checkpoint-ветками.

### Phase 3 / Aim Stability

Статус: реализована и закрыта как часть Phase 2/3 refinement ветки.

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
