# Spica Main Fine-Tune Status

This document records the current main-map checkpoint line after Phase 6 / Spinner Control.

## Status

Status: closed as the current working single-map baseline.

Active map:

```text
StylipS - Spica. (TV-size) (Lanturn) [Beginner-ka].osu
```

The map is selected through:

```text
PATHS.active_map -> PATHS.beginner_ka_map
```

## Checkpoint Line

The Spica main fine-tune starts from the completed spinner-capable checkpoint:

```text
artifacts/runs/osu_phase6_spinner_control/checkpoints/latest_spinner_control.pt
```

It writes its own independent checkpoints:

```text
artifacts/runs/osu_spica_main_finetune/checkpoints/latest_spica_main.pt
artifacts/runs/osu_spica_main_finetune/checkpoints/best_spica_main.pt
artifacts/runs/osu_spica_main_finetune/checkpoints/golden_spica_main.pt
```

This separation is intentional. The old Phase 6 spinner curriculum reward scale should not compete with the Spica reward scale. `best_spica_main.pt` is judged only against Spica-main rewards.

`golden_spica_main.pt` is a frozen copy of the best Spica checkpoint at the moment this stage was closed. Use it as the rollback-safe reference for the current single-map baseline.

## Closing Evidence

Representative training logs after the transition:

```text
update 0023: reward=259.687 hit_rate=1.000 clicks=99  useful=0.879 hits=87 miss=0
update 0025: reward=260.954 hit_rate=1.000 clicks=121 useful=0.686 hits=83 miss=0
```

Slider state at update 0025:

```text
sl_inside_ratio=0.810
sl_follow_dist_mean=28.3
sl_finish_rate=0.684
sl_tick_hit_rate=0.767
sl_seg_q=0.826
sl_full=13
sl_partial=7
```

Spinner state at update 0025:

```text
spin_hold=1.000
spin_good_rad=0.966
spin_drad=8.7
spin_step=0.897
spin_prog=1.71
spin_miss=0
```

Eval snapshot from `python -m src.apps.eval_osu` while the Spica branch was active:

```text
checkpoint=artifacts/runs/osu_spica_main_finetune/checkpoints/latest_spica_main.pt
hits=94
miss=0
clicks=27
good_t=0.889
early=2
late=0
off=0
near=0.963
far=0.000
sl_inside_ratio=0.823
sl_follow_dist_mean=31.9
sl_finish_rate=0.650
sl_tick=0.848
sl_seg_q=0.839
sl_full=13
sl_partial=7
spin_hold=1.000
spin_good_rad=1.000
spin_drad=1.1
spin_step=0.986
spin_prog=1.85
spin_miss=0
```

A live/manual run during ongoing training also cleared the current main map cleanly.

## Interpretation

The current policy is good enough to treat Spica Beginner-ka as passed for the current project stage:

- circle hit rate is effectively stable;
- miss count is zero in the representative eval;
- slider following is alive and high quality for this map;
- the short spinner no longer breaks the run;
- click count in eval is clean and no longer reflects the earlier training click spam.

Known limitations:

- this is still a single-map baseline, not multi-map generalization;
- train-time click timing metrics remain noisy because training samples stochastic policy behavior;
- the eval spinner helper/controller remains part of deterministic eval behavior and should be mirrored carefully in any future live osu! lazer bridge;
- `spin_clear` may remain `0` while `spin_part=1` on the short Spica spinner, but `spin_miss=0` and eval behavior are acceptable for this stage.

## Next Stage

The next natural stage is not more Spica-only reward chasing. Recommended next work:

- freeze or preserve `best_spica_main.pt` as the current main-map baseline;
- add a small validation/eval gate for this checkpoint;
- start Phase 7 / multi-map generalization from `best_spica_main.pt`;
- keep spinner curriculum checkpoints as fallback training bases, not as Spica-best competitors.
