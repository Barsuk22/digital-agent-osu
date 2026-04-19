# Phase 8 / Easy Generalization & Pattern Formation

Статус: план следующей фазы.

Phase 8 должна стартовать от закрытого Phase 7 checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Цель Phase 8: не прыгать сразу в hard-карты, а расширить устойчивость агента на новые easy/near-easy карты, где уже есть другие slider формы, более длинные цепочки, чуть более разные BPM и первые плотные паттерны.

## Почему не сразу hard

Phase 7 показала, что агент хорошо играет текущий easy/beginner pool и часть held-out карт. Но экспериментальные карты вроде `Animal hard` и `INTERNET YAMERO` показывают отдельный разрыв:

- на очень плотных картах резко растут misses;
- `near` падает, `far` растет;
- sliders могут быть частично поняты, но finish/tick quality падает;
- агент иногда цепляет удачные фрагменты, но не держит полную карту.

Это нормальный результат. Текущая policy уже имеет базовую моторику, но ей нужна постепенная лестница сложности.

## Основные цели

1. Удержать качество Phase 7 на старом gate pool.
2. Довести held-out `Sentimental Love` до стабильного slider-follow.
3. Добавить несколько новых easy-карт с разными slider формами.
4. Начать формировать короткие паттерны: doubles, triples, короткие chains, repeat motions.
5. Не разрушить click discipline: не возвращаться к лишним кликам.
6. Не разрушить slider tight-follow: следить за `dpx`, `sl_inside`, `sl_seg_q`.

## Предлагаемый training pool

База из Phase 7 должна остаться как regression gate, но не обязательно занимать весь training budget:

```text
StylipS - Spica. (TV-size) [Beginner-ka]
Suzuki Minori - Dame wa Dame (TV Size) [maikayuii's Beginner]
MIMiNARI - Itowanai feat. Tomita Miyu, Ichinose Kana (TV Size) [Teages's Easy]
noa - Megane o Hazushite (TV Size) [Easy]
ONMYO-ZA - Kouga Ninpouchou [JauiPlaY's Easy]
```

Кандидаты для добавления:

```text
Sati Akura - Sentimental Love (TV Size) [Myxo's Easy]
Sati Akura - Chikatto Chika Chika [Easy]
```

`Sentimental Love` особенно полезна: hits/timing уже хорошие, но slider finish пока слабее, чем на train-картах.

## Held-out / stress eval

Для проверки переноса держать отдельный eval set:

```text
несколько easy-карт вне train pool
INTERNET YAMERO [Easy] как stress-only, не как обязательный gate
Animal hard как curiosity/stress-only, не как критерий успеха
```

Hard/dense карты не должны решать best checkpoint selection на Phase 8. Иначе есть риск сломать стабильную easy-моторику ради шума.

## Метрики, за которыми смотреть

Главные:

```text
hit / miss
good_t / tmed
near / far
clicks / useful
sl_inside_ratio
sl_follow_dist_mean / dpx
sl_finish_rate
sl_tick
sl_drop
sl_seg_q
sl_full / sl_partial
spin_miss
```

Для новой фазы особенно важны:

- `dpx` не должен возвращаться к 55-70 на easy-картах;
- `sl_seg_q` должен оставаться высоким;
- `click_released_steps` должен оставаться около нуля во время slider-heavy maps;
- `far` должен оставаться низким;
- на старом Phase 7 gate pool не должно быть регресса.

## Возможный критерий best checkpoint

Phase 7 best mode:

```text
cycle_mean_min_slider_v1
```

Для Phase 8 можно сохранить его как базу, но добавить сильнее held-out/generalization component. Возможный следующий режим:

```text
cycle_easy_generalization_v1
```

Идея score:

- средний selection score по train pool;
- худший selection score по train pool;
- средний slider quality;
- штраф за рост `dpx`;
- штраф за `far`;
- небольшой бонус за held-out Sentimental/Chikatto, если eval встроен в цикл;
- hard/stress карты не участвуют в best score.

## Рекомендуемый порядок

1. Сначала зафиксировать Phase 7 checkpoint как golden.
2. Создать отдельную run directory для Phase 8.
3. Стартовать от `best_multimap.pt`.
4. Добавить `Sentimental Love` и `Chikatto` в curriculum мягко, без hard-карт.
5. Прогнать короткий training.
6. Сравнить:
   - старый Phase 7 gate pool;
   - Sentimental Love;
   - Chikatto;
   - 1-2 unseen easy карты.
7. Только после стабильного easy переноса думать о плотных картах вроде `INTERNET YAMERO`.

## Ожидаемый результат

Phase 8 считается успешной, если:

- старые Phase 7 карты остаются почти идеальными;
- `Sentimental Love` поднимается с частичного прохождения до уверенного slider-follow;
- held-out easy карты показывают высокий timing и низкий `far`;
- агент начинает переносить короткие паттерны, а не только отдельные hit objects;
- hard/stress карты могут оставаться плохими, но отдельные удачные фрагменты становятся чаще.
