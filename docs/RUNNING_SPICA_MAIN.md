# Running Spica Main Fine-Tune

This file is the current clean run note for the Spica main baseline. It supplements the older Russian running document, which still contains historical phase notes.

## Active Command

Run training from the project root:

```powershell
python -m src.apps.train_osu
```

The active map is:

```text
StylipS - Spica. (TV-size) (Lanturn) [Beginner-ka].osu
```

It is selected in:

```text
src/core/config/paths.py
PATHS.active_map -> PATHS.beginner_ka_map
```

## Checkpoints

When no Spica checkpoint exists, training starts from:

```text
artifacts/runs/osu_phase6_spinner_control/checkpoints/latest_spinner_control.pt
```

Spica checkpoints are saved to:

```text
artifacts/runs/osu_spica_main_finetune/checkpoints/latest_spica_main.pt
artifacts/runs/osu_spica_main_finetune/checkpoints/best_spica_main.pt
artifacts/runs/osu_spica_main_finetune/checkpoints/golden_spica_main.pt
```

`golden_spica_main.pt` is the frozen current-stage baseline. Training may continue to update `latest_spica_main.pt` and `best_spica_main.pt`, but the golden checkpoint should remain the stable rollback target for the Spica stage.

## Eval

Run:

```powershell
python -m src.apps.eval_osu
```

Eval first loads:

```text
artifacts/runs/osu_spica_main_finetune/checkpoints/latest_spica_main.pt
```

and saves replay to:

```text
artifacts/runs/osu_spica_main_finetune/replays/best_eval_replay.json
```

Representative current eval:

```text
hits=94 miss=0 clicks=27 good_t=0.889
sl_inside_ratio=0.823 sl_seg_q=0.839
spin_hold=1.000 spin_good_rad=1.000 spin_miss=0
```

## Replay

Run:

```powershell
python -m src.apps.replay_osu
```

Replay first opens:

```text
artifacts/runs/osu_spica_main_finetune/replays/best_eval_replay.json
```

## Status

Spica Beginner-ka is currently considered passed for this stage. Preserve `best_spica_main.pt` as the current main-map baseline and use it as the recommended starting point for the next multi-map generalization stage.
