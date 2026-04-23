# osu!lazer Runtime Deployment

## Current Runtime Modes

- `zeromq`: C# controller + Python policy server.
- `onnx`: C# controller + ONNX Runtime, without Python in the hot path.

## Recommended First Usable Setup

1. Keep using the repository checkout.
2. Use `external/osu_lazer_controller/start_agent.bat` or `start_bridge.ps1`.
3. Start with `runtime.live_probe.json` or `runtime.onnx.live_probe.json`.
4. Move to `runtime.live_play.json` or `runtime.onnx.live_play.json` only after trajectory looks sane.

## Publish The Controller

```powershell
cd D:\Projects\digital_agent_osu_project
powershell -ExecutionPolicy Bypass -File .\external\osu_lazer_controller\publish_controller.ps1
```

Published output goes to `release/osu_lazer_controller` by default.

## ONNX Export

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.export_osu_policy_onnx
```

Default output:

`artifacts/exports/onnx/best_easy_generalization.onnx`

## Typical Launch Commands

Python bridge:

```powershell
powershell -ExecutionPolicy Bypass -File .\external\osu_lazer_controller\start_bridge.ps1 -ConfigPath .\external\osu_lazer_controller\configs\runtime.live_probe.json
```

ONNX bridge:

```powershell
powershell -ExecutionPolicy Bypass -File .\external\osu_lazer_controller\start_bridge.ps1 -ConfigPath .\external\osu_lazer_controller\configs\runtime.onnx.live_probe.json
```
