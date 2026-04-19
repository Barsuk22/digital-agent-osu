# Roadmap разработки

Актуально на 2026-04-19.

Этот roadmap описывает текущее положение проекта по состоянию кода и обучения.

## Где проект сейчас

osu skill module прошел закрытие Phase 7 / Multi-Map Generalization. Агент стабильно играет несколько beginner/easy карт, показывает перенос на held-out `Chikatto`, удерживает sliders, timing и spinner behavior.

Текущий golden checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Следующий большой фокус: **Phase 8 / Easy Generalization & Pattern Formation**.

## Закрыто

### Phase 0 / Foundation

Сделано:

- `.osu` parser;
- osu-like environment;
- action space `dx, dy, click_strength`;
- observation с текущим временем, курсором и upcoming objects;
- judgement для circles, sliders и spinners;
- replay frames;
- pygame viewer.

### Phase 1 / Initial Learning / Base PPO Learning

Сделано:

- PPO training loop;
- Actor-Critic policy;
- rollout buffer и GAE;
- reward shaping;
- checkpoint loading/saving;
- eval через deterministic policy;
- replay после eval.

### Phase 2 / Timing Refinement + Phase 3 / Aim Stability

Сделано:

- timing metrics и timing reward breakdown;
- near/far/settled/unstable click distinction;
- pre-hit stability;
- post-hit exit quality;
- отдельная refinement checkpoint ветка.

### Phase 3.5 / Post-hit Motion Smoothing

Сделано:

- снижение post-hit recoil;
- smoothing metrics;
- мягкий выход к следующей цели.

### Phase 4.1 / Slider Follow Fix

Сделано:

- активное состояние slider в observation;
- reward за follow;
- диагностика hold/follow/drop behavior.

### Phase 5 / Slider Control

Сделано:

- segment-level slider metrics;
- `sl_seg_q`, `sl_full`, `sl_partial`;
- reverse/curve diagnostics;
- более устойчивое slider-follow поведение.

### Phase 6 / Spinner Control

Сделано:

- spinner observation/reward/diagnostics;
- spinner-capable checkpoint line.

### Spica Main Fine-Tune

Сделано:

- перенос spinner-capable policy обратно на основную карту;
- single-map baseline перед multi-map.

### Phase 7 / Multi-Map Generalization

Сделано:

- обучение на 5 beginner/easy картах;
- корректный cycle-based best checkpoint selection;
- concise console logging;
- tight slider-follow reward patch;
- `dpx` в training log;
- финальный `best cycle score = 12.342`.

Подробности:

```text
docs/osu/phase7_multimap_generalization_status.md
```

## Активная следующая стадия

### Phase 8 / Easy Generalization & Pattern Formation

Статус: планируется.

Старт:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Фокус:

- расширить easy/generalization pool;
- довести `Sentimental Love` до уверенного slider-follow;
- сохранить старые Phase 7 карты как regression gate;
- начать формировать короткие паттерны: doubles, triples, short chains;
- hard/dense карты держать как stress-only eval.

Подробности:

```text
docs/osu/phase8_easy_generalization_plan.md
```

## Дальше

### Phase 9 / Stability Gate

Цель: проверить повторяемость поведения, а не единичные удачные прогоны.

Направления:

- multi-seed eval;
- сравнение нескольких deterministic запусков;
- gate по старому train pool и held-out pool;
- анализ деградации между checkpoint ветками.

### Phase 10 / Skill Memory Init

Цель: начать сохранять устойчивые успешные паттерны.

Кандидаты:

- slider-follow segment;
- short chain;
- reverse slider;
- spinner control;
- simple jump/double.

### Phase 11+ / Skill System, Speed & Complexity

Цель: двигаться к более сложным картам только после стабильного easy/generalization фундамента.

Направления:

- skill selector;
- pattern ranking;
- gradual BPM/AR/OD increase;
- плотные карты вроде `INTERNET YAMERO` как отдельный curriculum;
- hard-карты после промежуточной лестницы, не сразу.

## Принцип проекта

Агент должен учиться через среду, reward и policy update. Документация не должна описывать его как scripted bot или как уже готового универсального osu-игрока. Phase 7 закрыта как beginner/easy multi-map milestone, но не как финальная универсальная игра в osu.
