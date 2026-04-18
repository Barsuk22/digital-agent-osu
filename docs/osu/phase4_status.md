# Phase 4 / Slider Intro

Актуальная реализация Phase 4 ведется как Phase 4.1 / Slider Follow Fix.

Основной документ:

```text
docs/osu/phase4_slider_follow_fix_status.md
```

Коротко: предыдущий Slider Intro подтвердил, что head hit работает, но follow behavior не формируется. Новая ветка добавляет явный active-slider state в observation, мягкий slider-follow shaping, более полезный tick/follow/finish signal и отдельные train/eval метрики.

Старт fine-tuning:

```text
artifacts/runs/osu_phase3_motion_smoothing/checkpoints/best_smooth.pt
```

Новая run-папка:

```text
artifacts/runs/osu_phase4_slider_follow_fix/
```

Статус: не закрыто как final slider mastery. Цель текущей фазы — научить policy удерживать follow, собирать ticks и чаще доводить простые sliders до finish без деградации circle gameplay.
 
# Link: Phase 5 / Slider Control

Phase 4.1 remains the slider-follow fix stage. The next implemented stage is Phase 5 / Slider Control:

```text
docs/osu/phase5_slider_control_status.md
```

Phase 5 starts from `artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/best_slider_follow.pt` and writes to `artifacts/runs/osu_phase5_slider_control/`.
