# Phase 7 / Multi-Map Generalization

Статус: закрыта 2026-04-19.

Phase 7 обучала текущую Spica-capable policy на небольшом наборе easy/beginner карт, чтобы агент перестал быть специалистом одной карты. Главный результат фазы: агент устойчиво играет несколько разных easy-карт, сохраняет timing, держит click/hold дисциплину и снова ведет sliders по slider ball, а не просто нажимает на head и убегает сквозь дорожку.

## Итоговый checkpoint

Финальная ветка Phase 7:

```text
artifacts/runs/osu_phase7_multimap_generalization
```

Основные checkpoint:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/latest_multimap.pt
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Для дальнейшей работы базовым checkpoint считать:

```text
artifacts/runs/osu_phase7_multimap_generalization/checkpoints/best_multimap.pt
```

Финальный лучший cycle score:

```text
best cycle score = 12.342
cycle = 0200
updates = 1000
```

## Старт фазы

Phase 7 стартовала от:

```text
artifacts/runs/osu_spica_main_finetune/checkpoints/golden_spica_main.pt
```

## Training pool

Карты обучения:

```text
StylipS - Spica. (TV-size) (Lanturn) [Beginner-ka].osu
Suzuki Minori - Dame wa Dame (TV Size) (chapter) [maikayuii's Beginner].osu
MIMiNARI - Itowanai feat. Tomita Miyu, Ichinose Kana (TV Size) (Pata-Mon) [Teages's Easy].osu
noa - Megane o Hazushite (TV Size) (Pata-Mon) [Easy].osu
ONMYO-ZA - Kouga Ninpouchou (App) [JauiPlaY's Easy].osu
```

Held-out eval карты, использованные для проверки переноса:

```text
Sati Akura - Sentimental Love (TV Size) (Nao Tomori) [Myxo's Easy].osu
Sati Akura - Chikatto Chika Chika (-Mikan) [Easy].osu
```

Дополнительно вручную проверялись сложные экспериментальные карты:

```text
Sati Akura - Animal [Even if it's ugly, that's the way I want it.]
Sati Akura - INTERNET YAMERO [Easy]
```

Эти две карты не являются критерием закрытия Phase 7. Они существенно сложнее текущего curriculum и должны рассматриваться как разведка будущих фаз.

## Важное исправление best checkpoint

В начале Phase 7 `best_multimap.pt` сохранялся по одному эпизоду. Это было неправильно для multi-map режима: первый сильный результат на одной карте мог заблокировать более здоровые общие политики.

Исправлено:

- best выбирается только после полного цикла по всем train-картам;
- score учитывает средний `sel`, худший `sel`, hit rate, slider inside, slider finish, slider quality и spinner misses;
- режим сохранения зафиксирован как:

```text
cycle_mean_min_slider_v1
```

Если checkpoint не содержит такой best metric mode, `best_reward` сбрасывается, но веса policy/optimizer продолжают загружаться.

## Важное исправление slider-follow

После первого multi-map обучения агент снова начал хорошо попадать, но визуально часть sliders проходил плохо: нажимал на slider head, держал click, но не велся точно по slider ball.

Добавлено усиление tight-follow поведения:

- reward за близкое следование slider ball;
- отдельный tight follow radius;
- штраф за удержание click далеко от slider ball;
- penalty за loose follow и escape;
- усиленный bonus за controlled slider finish;
- в concise log добавлен `dpx` как средняя дистанция до slider ball.

Итог: `dpx` на train/eval картах заметно снизился, а `sl_inside`, `sl_finish`, `sl_seg_q` выросли.

## Финальный train snapshot

Финальный лучший цикл:

```text
[cycle 0200] score=12.342 best=12.326
mean_sel=8.956 min_sel=6.266 mean_hit=0.994
sl_inside=0.985 sl_fin=0.968 sl_q=0.987 spin_miss=0
```

По картам в финальном best cycle:

```text
Spica:   sel=14.854 hit=0.990 miss=1 sl=0.959 fin=0.895 q=0.967
Suzuki:  sel=10.120 hit=1.000 miss=0 sl=1.000 fin=1.000 q=1.000
MIMiNARI: sel=6.964 hit=0.989 miss=1 sl=0.994 fin=0.982 q=0.996
noa:      sel=6.266 hit=0.992 miss=1 sl=0.989 fin=0.986 q=0.994
ONMYO:    sel=6.576 hit=0.997 miss=1 sl=0.984 fin=0.977 q=0.980
```

## Eval snapshot

Финальные eval-прогоны на `best_multimap.pt`.

### Held-out: Chikatto Chika Chika

```text
hits=126 miss=1 clicks=102
tmed=14.8 good_t=0.951 near=0.990 far=0.000
sl_head=57 sl_fin=45 sl_tick=0.800 sl_drop=12
sl_inside_ratio=0.890 sl_follow_dist_mean=38.9
sl_finish_rate=0.789 sl_seg_q=0.930
spin_clear=1 spin_miss=0
```

Статус: успешно. Карта считается хорошим held-out подтверждением Phase 7.

### Train gate: Spica

```text
hits=99 miss=0 clicks=27
tmed=10.5 good_t=0.963 near=0.963 far=0.000
sl_head=20 sl_fin=19 sl_tick=0.911 sl_drop=1
sl_inside_ratio=0.933 sl_follow_dist_mean=33.0
sl_finish_rate=0.950 sl_seg_q=0.947
spin_miss=0
```

Статус: успешно. Single-map baseline не разрушен.

### Train gate: Suzuki

```text
hits=85 miss=1 clicks=37
tmed=8.0 good_t=0.973 near=0.946 far=0.000
sl_head=25 sl_fin=24 sl_tick=1.000 sl_drop=0
sl_inside_ratio=0.981 sl_follow_dist_mean=27.4
sl_finish_rate=1.000 sl_seg_q=0.980
spin_miss=0
```

Статус: успешно.

### Train gate: MIMiNARI

```text
hits=91 miss=0 clicks=87
tmed=12.2 good_t=0.977 near=0.989 far=0.000
sl_head=56 sl_fin=51 sl_tick=1.000 sl_drop=5
sl_inside_ratio=0.978 sl_follow_dist_mean=23.7
sl_finish_rate=0.911 sl_seg_q=0.985
spin_miss=0
```

Статус: успешно.

### Train gate: noa

```text
hits=120 miss=1 clicks=119
tmed=14.6 good_t=0.966 near=1.000 far=0.000
sl_head=70 sl_fin=66 sl_tick=1.000 sl_drop=4
sl_inside_ratio=0.992 sl_follow_dist_mean=23.9
sl_finish_rate=0.943 sl_seg_q=0.994
```

Статус: успешно.

### Train gate: ONMYO-ZA

```text
hits=355 miss=1 clicks=223
tmed=14.7 good_t=0.973 near=0.987 far=0.004
sl_head=99 sl_fin=74 sl_tick=0.930 sl_drop=14
sl_inside_ratio=0.948 sl_follow_dist_mean=32.0
sl_finish_rate=0.841 sl_seg_q=0.958
spin_clear=5 spin_miss=0
```

Статус: успешно.

### Held-out: Sentimental Love

```text
hits=105 miss=6 clicks=87
tmed=18.3 good_t=0.908 near=0.931 far=0.023
sl_head=38 sl_fin=16 sl_tick=0.511 sl_drop=21
sl_inside_ratio=0.695 sl_follow_dist_mean=57.1
sl_finish_rate=0.432 sl_seg_q=0.734
spin_clear=1 spin_miss=0
```

Статус: частично успешно. Timing и попадания стали хорошими, но sliders еще нестабильны. Эту карту стоит использовать как один из первых gate/test cases Phase 8.

## Экспериментальные сложные карты

### Animal hard

```text
hits=118 miss=714
near=0.263 far=0.606
sl_inside_ratio=0.712 sl_follow_dist_mean=47.1
sl_finish_rate=0.439 sl_seg_q=0.722
```

Статус: вне текущего curriculum. Не является провалом Phase 7.

### INTERNET YAMERO easy

```text
hits=225 miss=153
near=0.626 far=0.239
sl_inside_ratio=0.546 sl_follow_dist_mean=72.6
sl_finish_rate=0.133 sl_seg_q=0.554
spin_clear=2 spin_miss=0
```

Статус: слишком сложная и плотная для текущей фазы. Видны отдельные удачные паттерны, но нужна отдельная curriculum-лестница.

## Критерии закрытия

Phase 7 считается закрытой, потому что:

- агент стабильно проходит несколько train-карт;
- Spica baseline не потерян;
- held-out Chikatto проходит почти идеально;
- sliders восстановлены после multi-map degradation;
- best checkpoint выбирается корректно по полному циклу, а не по одиночной карте;
- spinner behavior не разрушен;
- `best_multimap.pt` является рабочей базой для следующей фазы.

## Вывод

Phase 7 закрывает задачу beginner/easy multi-map generalization. Агент еще не готов к резкому переходу на hard/dense карты, но готов к Phase 8: расширению easy/generalization curriculum, особенно вокруг held-out slider cases и более разнообразных паттернов.
