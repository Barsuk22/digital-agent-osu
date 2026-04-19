# Phase 8.1 / Easy Generalization + Stability Gate

Статус: закрыта 2026-04-19.

Phase 8 и Phase 9 были объединены мягко:

- Phase 8 осталась стадией обучения на easy/generalization curriculum;
- Phase 9 не запускалась отдельной большой фазой, а была встроена как stability gate при выборе best checkpoint и затем подтверждена eval-прогонами.

Так мы не плодим лишнюю фазу ради проверки, но уже сейчас не даем агенту выбрать “лучший” checkpoint по одному случайно удачному прогону.

## Стартовый checkpoint

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Phase 7 остается golden baseline. Phase 8 пишет результаты отдельно и не затирает старую ветку.

## Новая run-директория

```text
artifacts/runs/osu_phase8_easy_generalization/
```

Checkpoint-и:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/latest_easy_generalization.pt
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Replay после eval:

```text
artifacts/runs/osu_phase8_easy_generalization/replays/best_eval_replay.json
```

## Команды

Обучение:

```powershell
python -m src.apps.train_osu
```

Eval:

```powershell
python -m src.apps.eval_osu
```

По умолчанию eval теперь смотрит на:

```text
Sati Akura - Sentimental Love (TV Size) [Myxo's Easy]
```

и берет:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Если Phase 8 checkpoint еще не создан, eval откатывается на Phase 7 `best_multimap.pt`.

## Curriculum

Phase 8 train pool:

```text
1. StylipS - Spica. (TV-size) [Beginner-ka]
2. Suzuki Minori - Dame wa Dame (TV Size) [maikayuii's Beginner]
3. MIMiNARI - Itowanai feat. Tomita Miyu, Ichinose Kana (TV Size) [Teages's Easy]
4. noa - Megane o Hazushite (TV Size) [Easy]
5. ONMYO-ZA - Kouga Ninpouchou [JauiPlaY's Easy]
6. Sati Akura - Sentimental Love (TV Size) [Myxo's Easy]
7. Sati Akura - Chikatto Chika Chika [Easy]
```

Роли внутри цикла:

- `gate`: первые 5 карт из Phase 7, защита от регресса;
- `target`: `Sentimental Love`, главная карта для подтягивания slider-follow;
- `heldout`: `Chikatto Chika Chika`, проверка переноса на похожую easy-карту.

Один цикл теперь равен 7 update. Лимит:

```text
updates = 700
```

То есть примерно 100 полных циклов по новому curriculum.

## Best selection

Новый режим:

```text
cycle_easy_generalization_gate_v1
```

Он использует старую Phase 7 формулу как базу, но добавляет:

- бонус за качество новых easy-карт;
- бонус за сохранение старого gate pool;
- штраф за просадку `hit_rate` на старых картах;
- штраф за просадку `sl_seg_q` на старых картах;
- штраф за плохой `Sentimental Love`;
- штраф за рост `dpx`, если агент снова начинает “пробегать” сквозь слайдеры вместо ведения по голове.

Главный смысл: best checkpoint должен быть не самым шумно-удачным, а самым стабильным.

## Пороговые ориентиры

Для старого Phase 7 gate pool:

```text
hit_rate >= 0.94
sl_seg_q >= 0.84
```

Для `Sentimental Love`:

```text
hit_rate >= 0.88
sl_seg_q >= 0.72
dpx <= 64
```

Для среднего slider-follow по циклу:

```text
dpx soft cap = 46
```

Это не жесткая остановка обучения, а критерии для выбора best checkpoint.

## Stress-only eval

Эти карты не участвуют в best selection:

```text
Sati Akura - INTERNET YAMERO [Easy]
Sati Akura - Animal [Even if it's ugly, that's the way I want it.]
```

Они нужны только как стресс-тест. На них можно смотреть, появляются ли отдельные удачные паттерны, но они не должны ломать easy-моторику.

## Что считать успехом Phase 8.1

Phase 8.1 можно считать успешной, если:

- старые Phase 7 карты остаются почти идеальными;
- `Sentimental Love` перестает быть “50 на 50” и выходит хотя бы в уверенный средний уровень;
- `Chikatto` остается стабильной;
- `dpx` на easy-картах не возвращается к 55-70;
- `sl_inside_ratio`, `sl_finish_rate`, `sl_seg_q` не проседают;
- agent начинает чаще собирать короткие chains/doubles/triples без лишних кликов;
- hard/stress карты могут оставаться плохими, но отдельные правильные фрагменты должны встречаться чаще.

## Итог Phase 8.1

Финальный best:

```text
best cycle score = 12.486
best checkpoint = artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Лучший training cycle:

```text
[cycle 0099] score=12.486 mean_sel=8.269 min_sel=6.030 mean_hit=0.995
sl_inside=0.980 sl_fin=0.952 sl_q=0.985 dpx=25.1 spin_miss=1
```

Состояние ключевых карт на closing cycle:

```text
Spica:            sel=14.805 hit=1.000 miss=0 sl=0.975 fin=0.895 q=0.974 dpx=28.0
Suzuki:           sel=10.582 hit=1.000 miss=0 sl=1.000 fin=1.000 q=1.000 dpx=21.7
MIMiNARI:         sel=7.326  hit=1.000 miss=0 sl=1.000 fin=1.000 q=1.000 dpx=20.0
noa:              sel=6.373  hit=1.000 miss=0 sl=0.980 fin=1.000 q=0.989 dpx=23.4
ONMYO-ZA:         sel=6.418  hit=0.997 miss=1 sl=0.962 fin=0.977 q=0.968 dpx=30.0
Sentimental Love: sel=6.345  hit=0.977 miss=3 sl=0.964 fin=0.811 q=0.971 dpx=28.2
Chikatto:         sel=6.030  hit=0.992 miss=1 sl=0.982 fin=0.983 q=0.991 dpx=24.7
```

Главный итог: `Sentimental Love` перестала быть 50/50 case, `Chikatto` осталась стабильной, старый gate pool удержан, а средний `dpx` на easy-картах опустился в здоровую область.

## Phase 9 gate-report

Phase 9 оформлена как короткий отчет/gate-run, а не отдельная training-фаза.

Eval на `best_easy_generalization.pt`:

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

Вывод:

- Phase 9 пройдена;
- checkpoint принят как основа для Phase 10;
- поведение не выглядит случайным: низкие misses и высокий slider-follow повторяются на gate, target и held-out картах;
- timing drift часто ранний, это не блокер закрытия Phase 8.1, но полезная задача для следующих фаз.

## Следующий шаг

Следующая стадия:

```text
Phase 10 / Skill Memory Init
```

Цель: начать сохранять устойчивые успешные паттерны:

- slider follow;
- reverse slider;
- short chain;
- spinner control;
- simple jump/double.
