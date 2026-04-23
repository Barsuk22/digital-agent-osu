# osu!lazer Runtime Calibration

Этот цикл нужен, чтобы довести live-runtime до поведения, близкого к offline симулятору.

## Быстрый цикл

1. Запустить безопасный или probe-режим bridge.
2. Получить свежий `warmup_trace_*.json` в логах controller.
3. Прогнать анализатор:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.analyze_osu_lazer_runtime
```

4. Открыть свежий `*_analysis.json`.
5. Подкрутить конфиг и повторить прогон.

Если нужно сравнить два прогона напрямую:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.compare_osu_lazer_analyses --baseline "<baseline_analysis.json>" --candidate "<candidate_analysis.json>"
```

Автоматический sweep по offset и speed:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.sweep_osu_lazer_offsets --base-config .\external\osu_lazer_controller\configs\runtime.live_probe.json --initial-times "1800,1890,1980" --audio-offsets "0" --input-delays "0" --cursor-speeds "12.0,14.0"
```

## Что крутить первым

Если высокий `edge_clamp_ratio`:

- уменьшать `cursorSpeedScale`;
- проверить, что playfield mapping не уводит курсор в край;
- потом повторить probe.

Если большой `reference_cursor_distance_px.mean`:

- сначала менять `audioOffsetMs`;
- потом `inputDelayMs`;
- потом `captureDelayMs`.

Если плохой `reference_click_match_ratio`:

- подстраивать `clickThreshold`;
- затем `sliderHoldThreshold`;
- затем `spinnerHoldThreshold`.

Если низкий `effective_fps.mean` или высокий `policy_latency_ms.p95`:

- смотреть на захват окна и фоновые процессы;
- перед долгими live-тестами держать Python bridge в стабильной среде;
- позже можно переносить inference в ONNX.

## Рекомендуемый порядок режимов

1. `runtime.json`
2. `runtime.live_probe.json`
3. `runtime.live_click_probe.json`
4. `runtime.live_move.json`
5. `runtime.live_play.json`

## Цель калибровки

На простых easy-картах bridge должен прийти к таким признакам:

- низкий `edge_clamp_ratio`;
- стабильный `reference_cursor_distance_px`;
- хорошее совпадение по `click_match`;
- отсутствие развала на slider hold;
- control loop не ниже примерно `50 FPS`.
