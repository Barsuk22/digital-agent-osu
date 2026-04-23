# osu!lazer Runtime Configuration

## Main Config Sections

### `policyBridge`

- `mode`: `zeromq` or `onnx`
- `address`: ZeroMQ address for Python mode
- `modelPath`: ONNX file path for ONNX mode
- `observationSize`: expected observation vector size
- `timeoutMs`: IPC timeout for ZeroMQ mode

### `timing`

- `tickRateHz`: controller loop frequency
- `startupDelayMs`: delay before auto-start
- `diagnosticTicks`: number of ticks in automatic probes
- `diagnosticInitialMapTimeMs`: synthetic start point for probe runs
- `startTriggerMode`: `delay` or `hotkey`
- `startHotkey`: current manual start hotkey
- `audioOffsetMs`: timing compensation for map/audio start
- `inputDelayMs`: timing compensation for input
- `captureDelayMs`: reserved compensation for capture delay

### `control`

- `enableMouseMovement`: applies cursor movement
- `enableMouseClicks`: applies click input
- `cursorSpeedScale`: converts policy deltas into runtime cursor speed
- `clickThreshold`: base click threshold
- `sliderHoldThreshold`: hold threshold while slider is active
- `spinnerHoldThreshold`: hold threshold while spinner is active

## Known Good Starting Points

For current Spica probes, the strongest baseline so far is:

- `diagnosticInitialMapTimeMs = 1800`
- `audioOffsetMs = -60`
- `inputDelayMs = 30`
- `cursorSpeedScale = 12.0`

See:

`artifacts/runs/osu_lazer_runtime_calibration/configs/t1800_a-60_i30_s12_00.json`

## Map-Specific Profiles

Generate a profile for a known alias:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.create_osu_lazer_runtime_profile --map sentimental_love_easy --mode live_probe --policy-runtime onnx
```
