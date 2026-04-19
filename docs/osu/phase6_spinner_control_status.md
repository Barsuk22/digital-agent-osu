# Phase 6 / Spinner Control

Phase 6 is the spinner specialization stage after Phase 5 / Slider Control.

It fine-tunes from:

```text
artifacts/runs/osu_phase5_slider_control/checkpoints/best_slider_control.pt
```

New artifacts are written to:

```text
artifacts/runs/osu_phase6_spinner_control/
artifacts/runs/osu_phase6_spinner_control/checkpoints/latest_spinner_control.pt
artifacts/runs/osu_phase6_spinner_control/checkpoints/best_spinner_control.pt
artifacts/runs/osu_phase6_spinner_control/replays/best_eval_replay.json
artifacts/runs/osu_phase6_spinner_control/metrics/spinner_control_debug_trace.json
```

## Goal

Previous phases could parse, display, and score spinners, but the policy did not have enough state to learn spinner behavior reliably. Phase 6 teaches the policy to:

- move toward a useful spinner radius before the spinner starts;
- hold click during the spinner;
- rotate around the playfield center instead of sitting near the center;
- keep a stable radius while spinning;
- accumulate angular progress consistently;
- avoid stalls, click releases, and direction flips;
- convert spinner progress into `spinner_clear` instead of `spinner_miss`.

## Observation Changes

`OsuObservation` now includes `spinner: SpinnerStateView`.

The spinner block exposes:

- active/primary spinner flags;
- normalized spinner progress and spin count;
- target spin count;
- time to spinner end;
- spinner center;
- distance to center and radius error;
- current angle as sin/cos;
- measured angular velocity.

The checkpoint loader already supports partial first-layer expansion, so Phase 6 can load Phase 5 weights and initialize the new spinner inputs without discarding the learned aim/timing/slider behavior.

## Reward Changes

The judge now gives dense spinner reward for:

- maintaining click during an active spinner;
- staying near a useful circular radius;
- accumulating angular delta;
- spinning fast enough without collapsing into the center.

The training shaper adds Phase 6-specific reward for:

- pre-positioning near the spinner ring;
- holding click through the spinner;
- good radius control;
- angular progress and spin count gain;
- consistent direction;
- final `spinner_clear` and `spinner_partial`.

It also penalizes:

- releasing click during the spinner;
- stalling while holding;
- unstable direction flips;
- large radius error;
- final `spinner_miss`.

## Diagnostics

Training logs now include:

- `spin_r` - total Phase 6 spinner shaping reward;
- `spin_active` - active spinner steps;
- `spin_hold` - active-step hold ratio;
- `spin_good_rad` - ratio of active steps near the target spinner radius;
- `spin_drad` - mean radius error;
- `spin_step` - ratio of active steps with angular movement;
- `spin_delta` - mean angular delta per active sample;
- `spin_prog` - total spin gain during the episode;
- `spin_stall` - holding without meaningful angular movement;
- `spin_flip` - direction consistency failures;
- `spin_clear`, `spin_part`, `spin_miss` - outcome counts.

The deterministic sanity script:

```text
python -m src.apps.debug_spinner_control
```

saves a trace to:

```text
artifacts/runs/osu_phase6_spinner_control/metrics/spinner_control_debug_trace.json
```

## Expected First Signs

Early Phase 6 training should be judged by spinner metrics, not only total reward. Useful movement is:

- `spin_hold` quickly approaches high values;
- `spin_good_rad` rises while `spin_drad` falls;
- `spin_step` and `spin_prog` become nonzero;
- `spin_stall` and `spin_flip` trend down;
- `spin_miss` starts giving way to `spin_part`, then `spin_clear`.

If `spin_hold` is high but `spin_step` stays near zero, the agent is holding without rotating. If `spin_step` rises but `spin_good_rad` stays low, the agent is moving but not learning a stable spinner ring.

## Closure And Main-Map Transfer

Phase 6 produced a spinner-capable checkpoint line in:

```text
artifacts/runs/osu_phase6_spinner_control/checkpoints/latest_spinner_control.pt
artifacts/runs/osu_phase6_spinner_control/checkpoints/best_spinner_control.pt
```

After the spinner curriculum, the active map was returned to:

```text
StylipS - Spica. (TV-size) (Lanturn) [Beginner-ka].osu
```

The project then created a separate Spica main fine-tune line:

```text
artifacts/runs/osu_spica_main_finetune/checkpoints/latest_spica_main.pt
artifacts/runs/osu_spica_main_finetune/checkpoints/best_spica_main.pt
```

The separate line is important because spinner-curriculum reward and Spica reward are not directly comparable. The current main-map status is documented in:

```text
docs/osu/spica_main_finetune_status.md
```

Representative Spica eval after transfer:

```text
hits=94 miss=0 clicks=27 good_t=0.889
sl_inside_ratio=0.823 sl_seg_q=0.839 sl_full=13 sl_partial=7
spin_hold=1.000 spin_good_rad=1.000 spin_step=0.986 spin_miss=0
```

For the current stage, Phase 6 can be treated as closed: spinner support no longer blocks the main Beginner-ka map, and the next useful step is multi-map generalization rather than more spinner-only training.
