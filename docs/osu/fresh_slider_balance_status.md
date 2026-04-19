# Fresh Slider Balance Training

This phase is a clean PPO restart for the osu agent after the old checkpoints were moved away.

The goal is not another fine-tune from a possibly overfit policy. The goal is to relearn the whole balanced behavior from random initialization:

- hit circles with cleaner timing;
- avoid useless click spam;
- keep aim/control stable;
- acquire slider heads;
- hold sliders after the head;
- follow slider body with progress and alignment;
- collect ticks and finish sliders;
- avoid learning either extreme: early release or sticky noisy hold.

## Run Paths

`python -m src.apps.train_osu` now starts:

```text
phase_name: fresh_slider_balance
run_dir: artifacts/runs/osu_fresh_slider_balance
latest: artifacts/runs/osu_fresh_slider_balance/checkpoints/latest_fresh_slider_balance.pt
best: artifacts/runs/osu_fresh_slider_balance/checkpoints/best_fresh_slider_balance.pt
```

No source checkpoint is loaded by default:

```text
FRESH START: no checkpoint loaded
```

This deliberately avoids carrying over click-spam, early-release, or sticky-hold habits from previous experiments.

## Observation Dim

The observation vector has been expanded by three slider-normalized features:

- distance to current slider follow target divided by follow radius;
- distance to slider ball divided by follow radius;
- remaining slider progress.

This is safe for fresh training because no old checkpoint compatibility is required. Eval uses the same observation encoding.

## Reward Balance

The reward combines the lessons from the previous runs:

- click discipline and timing are active from the start;
- raw retaps and excessive click budgets are penalized;
- slider head reward is de-emphasized so the agent cannot farm only the start;
- post-head hold, body progress, inside-follow, ticks, and finish remain valuable;
- early release is penalized in slider context;
- hold quality gates distinguish useful body tracking from sticky noisy hold.

The important distinction is:

```text
Good: hold while close/inside, moving along the slider, gaining progress.
Bad: hold or retap while far, stalled, noisy, or not improving follow.
```

## Fresh Anti-Passivity Pass

The first fresh run became clean but too safe: clicks collapsed to single digits, spam disappeared, approach stayed high, but hits, useful clicks, slider heads, and slider partials stayed near zero.

This pass adds a small early curriculum scaffold:

- reward a click attempt only when the object is close enough and in a reasonable timing window;
- give extra early credit for first real hits and slider-head contact;
- mildly reduce far/off-window click penalties only inside that same plausible attempt window;
- penalize skipped actionable opportunities a little, instead of blindly penalizing low click count;
- fade the scaffold over the first `fresh_interaction_updates`, so later training is still governed by normal clean execution and slider-control rewards.

The log field `fresh_i` is the net scaffold reward. Early on it should be active; later it should naturally shrink toward zero.

## Early Metrics

In the first updates from random initialization, expect noisy logs. The first useful signal is not perfect slider mastery. Watch trends:

- `clicks` should not explode permanently above `250-300`;
- `clicks` should also not collapse permanently into `1-10`;
- `spam` should trend down as timing improves;
- `fresh_i` should be positive for real attempts and negative when the agent parks near objects but refuses to click;
- `useful` should climb toward `0.35+`, then `0.40+`;
- `hits`, `hit_rate`, and `sl_head` should start appearing before slider-body mastery;
- `good_t` should improve while `early/off` fall;
- `aim` should avoid living below `-10`;
- `sl_head_to_hold` should become nonzero early;
- `sl_post_head_hold_ratio` should climb toward `0.45-0.55+`;
- `sl_follow` / `sl_inside_ratio` should eventually move above `0.40`, then `0.50+`;
- `sl_tick_hit_rate`, `sl_finish_rate`, `sl_seg_q`, and `sl_full` should rise after basic hit/head behavior stabilizes.

If the agent becomes clean but releases early, increase slider release/hold shaping. If it becomes sticky and dirty, tighten hold quality and spam penalties slightly, not the core slider completion rewards.
