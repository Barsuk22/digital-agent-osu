# Current Curriculum Snapshot

Актуально на 2026-04-19.

osu curriculum дошел до закрытой Phase 8.1 / Easy Generalization + Stability Gate. Phase 9 / Gate Report пройдена как короткая проверка стабильности.

## Golden baseline

Phase 7 best:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Финальный Phase 7 score:

```text
best cycle score = 12.342
best mode = cycle_mean_min_slider_v1
```

## Следующая стадия

```text
Phase 10 / Skill Memory Init
```

Стартует от принятого Phase 8.1 checkpoint:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Пишет результаты в:

```text
artifacts/runs/osu_phase8_easy_generalization/
```

Best mode:

```text
cycle_easy_generalization_gate_v1
```

## Закрытые стадии

- Phase 0 / Foundation: parser, env, judgement, replay, viewer.
- Phase 1 / Base PPO Learning: базовая обучаемость через PPO.
- Phase 1.5 / Movement Polishing: начальная моторная полировка.
- Phase 2 / Timing Refinement: timing metrics и timing reward.
- Phase 3 / Aim Stability: click/aim stability.
- Phase 3.5 / Post-hit Motion Smoothing: снижение recoil после hit.
- Phase 4.1 / Slider Follow Fix: оживление slider-follow.
- Phase 5 / Slider Control: устойчивое ведение slider segments.
- Phase 6 / Spinner Control: spinner observation/reward/diagnostics.
- Spica Main Fine-Tune: сильная single-map baseline ветка.
- Phase 7 / Multi-Map Generalization: beginner/easy перенос на несколько карт.
- Phase 8.1 / Easy Generalization + Stability Gate: расширенный easy pool и встроенный stability gate.
- Phase 9 / Gate Report: eval-подтверждение стабильности `best_easy_generalization.pt`.

## Phase 7 training pool

Теперь это regression gate для Phase 8.1:

```text
StylipS - Spica. (TV-size) [Beginner-ka]
Suzuki Minori - Dame wa Dame (TV Size) [maikayuii's Beginner]
MIMiNARI - Itowanai feat. Tomita Miyu, Ichinose Kana (TV Size) [Teages's Easy]
noa - Megane o Hazushite (TV Size) [Easy]
ONMYO-ZA - Kouga Ninpouchou [JauiPlaY's Easy]
```

## Phase 7 итог

Финальные eval-прогоны на `best_multimap.pt`:

```text
Chikatto held-out: hits=126 miss=1 sl_inside=0.890 dpx=38.9 sl_seg_q=0.930
Spica:            hits=99  miss=0 sl_inside=0.933 dpx=33.0 sl_seg_q=0.947
Suzuki:           hits=85  miss=1 sl_inside=0.981 dpx=27.4 sl_seg_q=0.980
MIMiNARI:         hits=91  miss=0 sl_inside=0.978 dpx=23.7 sl_seg_q=0.985
noa:              hits=120 miss=1 sl_inside=0.992 dpx=23.9 sl_seg_q=0.994
ONMYO-ZA:         hits=355 miss=1 sl_inside=0.948 dpx=32.0 sl_seg_q=0.958
```

`Sentimental Love` пока частично стабильна:

```text
hits=105 miss=6 sl_inside=0.695 dpx=57.1 sl_finish_rate=0.432 sl_seg_q=0.734
```

## Phase 8.1 training pool

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

- `gate`: старые 5 карт Phase 7;
- `target`: `Sentimental Love`;
- `heldout`: `Chikatto Chika Chika`.

## Phase 8.1 цели

- Не прыгать сразу в hard-карты.
- Расширить easy/generalization pool.
- Довести `Sentimental Love` до уверенного slider-follow.
- Сохранить старый Phase 7 gate pool почти идеальным.
- Начать формировать короткие паттерны: doubles, triples, short chains.
- Держать hard/dense карты только как stress-only eval.

## Phase 8.1 итог

```text
best cycle score = 12.486
best checkpoint = artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Phase 9 gate-report:

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

Вывод: Phase 8.1 закрыта, Phase 9 пройдена. Curriculum готов к Phase 10.

## Phase 10 / Skill Memory Init

Цель: сохранять устойчивые успешные паттерны, которые уже повторяются на eval.

Первые кандидаты:

- slider follow;
- reverse slider;
- short chain;
- spinner control;
- simple jump/double.

## Stress-only eval

```text
Sati Akura - INTERNET YAMERO [Easy]
Sati Akura - Animal [Even if it's ugly, that's the way I want it.]
```

Эти карты не являются провалом Phase 8.1, даже если misses остаются высокими.
