# Phase B.2 Movement Probe

Цель B.2 - одной командой проверить, что тело агента реально управляется:

```text
observe -> look_right -> move_forward -> stop -> observe -> verdict
```

Это ещё не навык и не обучение. Это scripted probe для проверки транспорта, физики и low-level controls.

## Запуск

Сначала должны быть запущены Minecraft server и Mineflayer bridge.

```bat
python scripts\minecraft_movement_probe.py --write-debug
```

Можно усилить движение:

```bat
python scripts\minecraft_movement_probe.py --move-duration-ms 700 --settle-ms 900 --write-debug
```

## Успех

Успешный результат:

```json
{
  "ok": true,
  "result": {
    "verdict": "body_controls_ok",
    "horizontal_distance": 1.2,
    "yaw_delta": 0.26
  }
}
```

Минимальные gates по умолчанию:

```text
horizontal_distance >= 0.25
abs(yaw_delta) >= 0.05
```

## Debug

При `--write-debug` результат сохраняется:

```text
artifacts/debug/minecraft/movement_probe.json
```

Файл содержит:

- start observation preview;
- end observation preview;
- position delta;
- yaw delta;
- step-by-step action responses.
