# Current Curriculum Snapshot

As of 2026-04-19, the osu curriculum has reached a usable single-map baseline on:

```text
StylipS - Spica. (TV-size) (Lanturn) [Beginner-ka].osu
```

Closed/current completed stages:

- Phase 5 / Slider Control produced stable slider-follow behavior.
- Phase 6 / Spinner Control added spinner observation, reward, diagnostics, and a spinner-capable checkpoint line.
- Spica Main Fine-Tune transferred the spinner-capable policy back to the main map and created an independent Spica checkpoint line.

Current baseline checkpoint:

```text
artifacts/runs/osu_spica_main_finetune/checkpoints/best_spica_main.pt
artifacts/runs/osu_spica_main_finetune/checkpoints/golden_spica_main.pt
```

Representative eval:

```text
hits=94 miss=0 clicks=27 good_t=0.889
sl_inside_ratio=0.823 sl_seg_q=0.839 spin_miss=0
```

Next recommended curriculum stage:

- Phase 7 / Multi-Map Generalization.
- Start from `best_spica_main.pt`.
- Keep Spica as a regression/eval gate.
- Add nearby easy/beginner maps gradually instead of continuing to overfit only Spica.
