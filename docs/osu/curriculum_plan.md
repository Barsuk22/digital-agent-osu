# Current Curriculum Snapshot

Актуально на 2026-04-19.

osu curriculum дошел до закрытой Phase 7 / Multi-Map Generalization. Агент больше не является только Spica-specialist: он стабильно играет набор beginner/easy карт, сохраняет spinner behavior и снова уверенно ведет sliders после tight-follow исправления.

## Текущий golden checkpoint

Основной checkpoint для следующей фазы:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Последний checkpoint той же ветки:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/latest_multimap.pt
```

Финальный лучший Phase 7 score:

```text
best cycle score = 12.342
best mode = cycle_mean_min_slider_v1
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

## Phase 7 training pool

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

Ее стоит использовать как один из первых ориентиров Phase 8.

## Текущая следующая стадия

Следующая стадия: **Phase 8 / Easy Generalization & Pattern Formation**.

Старт:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Цель:

- не прыгать сразу в hard-карты;
- расширить easy/generalization pool;
- довести `Sentimental Love` до уверенного slider-follow;
- сохранить старый Phase 7 gate pool почти идеальным;
- начать формировать короткие паттерны: doubles, triples, короткие chains;
- использовать hard/dense карты только как stress-only eval.

Подробный план:

```text
docs/osu/phase8_easy_generalization_plan.md
```

## Что не считать провалом

`Animal hard` и `INTERNET YAMERO [Easy]` пока не являются критериями успеха. На них агент уже иногда цепляет отдельные фрагменты, но общая плотность и сложность выше текущего curriculum. Их место - в будущей лестнице сложности, а не в закрывающем gate Phase 7.
