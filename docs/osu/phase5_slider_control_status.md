# Phase 5 / Slider Control

Phase 5 is the next slider stage after Phase 4.1 / Slider Follow Fix.

It is not a restart and not a rewrite of the osu PPO pipeline. It fine-tunes from:

```text
artifacts/runs/osu_phase4_slider_follow_fix/checkpoints/best_slider_follow.pt
```

New artifacts are written to:

```text
artifacts/runs/osu_phase5_slider_control/
artifacts/runs/osu_phase5_slider_control/checkpoints/latest_slider_control.pt
artifacts/runs/osu_phase5_slider_control/checkpoints/best_slider_control.pt
artifacts/runs/osu_phase5_slider_control/replays/best_eval_replay.json
```

## Goal

Phase 4.1 made sliders alive: the policy learned to hit slider heads, hold click more often, track the slider ball sometimes, collect some ticks, and occasionally finish.

Phase 5 shifts the objective from "enter the slider" to "control the slider segment":

- less relative value for only hitting the slider head;
- more value for sustained follow;
- more value for tick consistency and finish;
- more pressure against drops;
- better direction following along the slider tangent;
- better behavior on curves and direction changes;
- explicit reverse-window diagnostics and shaping.

## Reward Changes

The training shaping now de-emphasizes isolated `slider_head` by subtracting a small Phase 5 head penalty. The env/judge still reports the head hit normally, but Phase 5 training reward no longer lets a head tap dominate the slider objective.

The main positive slider value is moved toward:

- `slider_tick` consistency;
- `slider_finish`;
- continuous inside-follow chains;
- progress while holding;
- distance reduction to the current slider ball;
- movement aligned with the current target and slider tangent;
- curve control;
- reverse-window recovery.

Phase 5 also adds mild penalties for:

- `slider_drop`;
- holding far away without tracking;
- stalling while holding;
- moving against the target or tangent;
- losing control on curved/reverse windows.

These penalties are intentionally moderate. The goal is to guide PPO, not to make active sliders toxic again.

## Curves And Reverse

No observation-dim change was added for Phase 5. The phase reuses the existing active-slider block:

- slider ball target position;
- distance to target;
- inside-follow;
- progress;
- tangent;
- follow radius.

Curved and reverse behavior are inferred from tangent changes over active slider steps:

- curved steps: tangent changes enough between consecutive active steps;
- reverse events: tangent direction flips sharply;
- reverse window: a short window after a detected reverse event.

This keeps the policy input stable while adding training and eval diagnostics for curved/reverse control.

## New Metrics

Phase 5 keeps the Phase 4.1 metrics and adds segment-control diagnostics:

- `sl_seg_q` - mean inside-follow quality per slider segment;
- `sl_full` - finished segments with enough sustained follow quality;
- `sl_partial` - segments with some follow or finish but not full-quality control;
- `sl_rev` - detected reverse events;
- `sl_rev_follow` - follow ratio during reverse windows;
- `sl_curve` - detected curved/path-change steps;
- `sl_curve_good` - inside-follow ratio on curved/path-change steps.

Existing useful Phase 4.1 metrics remain important:

- `sl_inside_ratio`;
- `sl_follow_dist_mean`;
- `sl_follow_gain`;
- `sl_tick_hit_rate`;
- `sl_finish_rate`;
- `sl_chain_mean`;
- `sl_chain_max`;
- `sl_track_good`;
- `sl_track_bad`;
- `sl_wrong_dir`;
- `sl_stall`.

## Expected First Logs

Do not expect immediate perfect slider mastery. The first useful signs are:

- `sl_click_hold_steps` stays alive without exploding click spam too much;
- `sl_inside_ratio` and `sl_seg_q` rise together;
- `sl_follow_dist_mean` trends down or stays near the Phase 4.1 improved range;
- `sl_tick_hit_rate` becomes less rare;
- `sl_fin` and `sl_finish_rate` appear more often than in Phase 4.1 eval;
- `sl_chain_mean` and `sl_chain_max` rise;
- `sl_curve_good` becomes nonzero;
- on maps with repeats, `sl_rev` and `sl_rev_follow` become meaningful.

If `sl_head` stays high but `sl_seg_q`, `sl_tick_hit_rate`, `sl_finish_rate`, and `sl_chain_*` do not improve, Phase 5 is not achieving its purpose.
