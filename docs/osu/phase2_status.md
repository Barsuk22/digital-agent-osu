# Phase 2 / Timing Refinement — статус

Статус: реализована и закрыта как рабочая timing-refinement база.

Phase 2 не запускает обучение с нуля. Она продолжает уже сильную policy из `best_recoil.pt` и уточняет качество клика во времени.

По результату текущей ветки получен рабочий checkpoint:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
```

Этот checkpoint теперь используется как база для Phase 3.5 / Post-hit Motion Smoothing.

## База обучения

Загрузка весов:

```text
artifacts/runs/osu_phase1_ppo/checkpoints/best_recoil.pt
```

Новая ветка сохранения:

```text
artifacts/runs/osu_phase2_timing/
```

Checkpoints новой ветки:

```text
artifacts/runs/osu_phase2_timing/checkpoints/best_timing.pt
artifacts/runs/osu_phase2_timing/checkpoints/latest_timing.pt
```

## Что добавлено

### Timing metrics

В training log теперь выводятся:

- `tmean` — средняя абсолютная timing error по кликам;
- `tmed` — медианная абсолютная timing error;
- `good_t` — доля кликов в хорошем временном окне;
- `early` — количество ранних кликов;
- `late` — количество поздних кликов;
- `off` — количество кликов вне focus window.

Eval также печатает timing summary после deterministic rollout.

### Timing reward breakdown

В `RewardBreakdown` добавлены отдельные поля:

- `timing_bonus`;
- `timing_penalty`.

Это позволяет видеть, где агент получает bonus за хороший timing, а где получает мягкий penalty за ранний, поздний или off-window click.

### Мягкое refinement-поведение

Timing shaping сделан осторожным:

- хороший timing поощряется;
- near-miss получает небольшой penalty;
- ранние и поздние клики штрафуются постепенно;
- off-window click получает отдельный penalty;
- penalty не должен заставлять агента бояться кликать.

## Что ещё не закрыто

- timing refinement пока работает на активной карте;
- нет отдельного YAML-конфига для timing-параметров;
- ещё нужны сравнительные eval-прогоны между `best_recoil.pt` и `best_timing.pt`;
- multi-map timing validation пока не закрыта.
