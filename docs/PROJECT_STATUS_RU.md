# Текущий статус проекта

Актуально на 2026-04-19.

## Кратко

`digital_agent_osu_project` - модульный проект цифрового агента. osu-навык является отдельным skill module, где агент обучается моторному поведению через reinforcement learning, а не через scripted bot логику.

osu skill module прошел важную точку: **Phase 8.1 / Easy Generalization + Stability Gate закрыта**, а **Phase 9 / Gate Report пройдена**. Агент стабильно играет расширенный beginner/easy pool, удерживает старые gate-карты, подтянул `Sentimental Love` и показал перенос на новую held-out easy карту.

Следующая планируемая стадия: **Phase 10 / Skill Memory Init**.

Phase 8 и Phase 9 были объединены:

- Phase 8 расширила easy/generalization curriculum;
- Phase 9 была встроена как stability gate при выборе best checkpoint и подтверждена eval-прогонами.

## Golden baseline

Phase 7 golden checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Финальный лучший Phase 7 score:

```text
best cycle score = 12.342
best mode = cycle_mean_min_slider_v1
```

## Phase 8.1 итоговая ветка

Старт:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Run directory:

```text
artifacts/runs/osu_phase8_easy_generalization/
```

Checkpoint-и:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/latest_easy_generalization.pt
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Best mode:

```text
cycle_easy_generalization_gate_v1
```

Финальный лучший score Phase 8.1:

```text
best cycle score = 12.486
```

## Главный итог Phase 7

Финальный training cycle:

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

Это не блокер Phase 7. Это главный target для Phase 8.1.

## Статус фаз

| Фаза | Статус | Смысл |
|---|---|---|
| Phase 0 / Foundation | закрыта | parser, environment, judgement, replay, viewer |
| Phase 1 / Base PPO | закрыта | PPO loop, Actor-Critic, checkpoints, eval |
| Phase 1.5 / Movement Polishing | закрыта | базовая моторика и recoil |
| Phase 2 / Timing Refinement | закрыта | timing windows и click timing |
| Phase 3 / Aim Stability | закрыта | pre-hit stability |
| Phase 3.5 / Post-hit Motion Smoothing | закрыта | мягкий выход после hit |
| Phase 4.1 / Slider Follow Fix | закрыта | уход от “hit head only” |
| Phase 5 / Slider Control | закрыта | полный slider segment control |
| Phase 6 / Spinner Control | закрыта | spinner моторика |
| Spica Main Fine-Tune | закрыта | single-map baseline |
| Phase 7 / Multi-Map Generalization | закрыта | стабильный beginner/easy multi-map pool |
| Phase 8.1 / Easy Generalization + Stability Gate | закрыта | новый easy pool + встроенный stability gate |
| Phase 9 / Gate Report | пройдена | eval-проверка стабильности Phase 8.1 checkpoint |
| Phase 10 / Skill Memory Init | планируется | сохранение устойчивых успешных паттернов |

## Phase 8.1 curriculum

```text
1. StylipS - Spica. (TV-size) [Beginner-ka]
2. Suzuki Minori - Dame wa Dame (TV Size) [maikayuii's Beginner]
3. MIMiNARI - Itowanai feat. Tomita Miyu, Ichinose Kana (TV Size) [Teages's Easy]
4. noa - Megane o Hazushite (TV Size) [Easy]
5. ONMYO-ZA - Kouga Ninpouchou [JauiPlaY's Easy]
6. Sati Akura - Sentimental Love (TV Size) [Myxo's Easy]
7. Sati Akura - Chikatto Chika Chika [Easy]
```

Роли:

- `gate`: первые 5 карт, старый Phase 7 regression gate;
- `target`: `Sentimental Love`;
- `heldout`: `Chikatto`.

## Stress-only

Эти карты используются только как стресс-тест, не как критерий закрытия Phase 8.1:

```text
Sati Akura - INTERNET YAMERO [Easy]
Sati Akura - Animal [Even if it's ugly, that's the way I want it.]
```

На них нормально видеть много misses. Сейчас важно не сломать easy-моторику.

## Phase 9 gate-report

Проверка на `best_easy_generalization.pt`:

```text
Chikatto:          hits=133 miss=0 sl_inside=0.997 dpx=23.2 sl_seg_q=0.997
Sentimental Love:  hits=124 miss=3 sl_inside=0.951 dpx=32.5 sl_seg_q=0.961
Spica:             hits=84  miss=4 sl_inside=0.985 dpx=22.8 sl_seg_q=0.980
Suzuki:            hits=85  miss=1 sl_inside=1.000 dpx=26.7 sl_seg_q=1.000
MIMiNARI:          hits=91  miss=0 sl_inside=1.000 dpx=23.4 sl_seg_q=1.000
noa:               hits=120 miss=0 sl_inside=0.983 dpx=20.5 sl_seg_q=0.993
ONMYO-ZA:          hits=359 miss=2 sl_inside=0.980 dpx=28.4 sl_seg_q=0.981
YOASOBI held-out:  hits=129 miss=0 sl_inside=0.923 dpx=40.0 sl_seg_q=0.952
```

Вывод: Phase 9 пройдена. Агент играет не случайно: slider-follow стабилен, misses низкие, старый gate pool не потерян, перенос на новую easy карту появился. Замечание: timing drift часто ранний, это стоит учитывать в следующих фазах.

## Ближайшая цель

1. Зафиксировать `best_easy_generalization.pt` как основу для следующей стадии.
2. Начать Phase 10 / Skill Memory Init.
3. Сохранить первые устойчивые паттерны: slider follow, reverse slider, short chain, spinner control, simple jump/double.
4. Не переходить резко к hard/dense curriculum до появления базовой skill memory.
