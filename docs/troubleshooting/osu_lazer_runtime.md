# osu!lazer Runtime Troubleshooting

## Controller Cannot Find The Game Window

- Make sure `osu!lazer` is running.
- Check `window.executablePath` in the selected config.
- Keep the game in windowed or borderless mode while calibrating.
- Let the controller bring the game to foreground.

## ONNX Mode Fails To Start

- Export the model first:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.export_osu_policy_onnx
```

- Confirm that `policyBridge.modelPath` points to the exported file.

## Python Mode Fails To Start

- Confirm Python path inside `start_bridge.ps1`.
- Install missing packages:

```powershell
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m pip install torch numpy pyzmq onnx onnxruntime
```

## Cursor Moves But Plays Poorly

- This is usually calibration, not a broken bridge.
- Start with movement-only probe.
- Run analysis:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.analyze_osu_lazer_runtime
```

- Then run sweep:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.sweep_osu_lazer_offsets --base-config .\external\osu_lazer_controller\configs\runtime.live_probe.json --initial-times "1800" --audio-offsets "-60,0,60" --input-delays "-30,0,30" --cursor-speeds "12.0"
```
