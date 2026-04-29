# Phase B.1 Manual Control Smoke

Цель B.1 - проверить тело агента без PPO и без навыков.

Мы проверяем только low-level controls через уже готовый Mineflayer bridge:

- `noop`;
- `move_forward`;
- `move_back`;
- `move_left`;
- `move_right`;
- `jump`;
- `sneak`;
- `sprint`;
- `look_left`;
- `look_right`;
- `look_up`;
- `look_down`;
- `chat`;
- `stop`.

## Запуск

1. Запусти Minecraft server.
2. Запусти bridge:

```bat
scripts\run_minecraft_mineflayer_bridge.bat
```

3. В другом терминале проверь действие:

```bat
python scripts\minecraft_manual_control_smoke.py --action move_forward
```

Поворот камеры:

```bat
python scripts\minecraft_manual_control_smoke.py --action look_right --look-degrees 15
```

Прыжок:

```bat
python scripts\minecraft_manual_control_smoke.py --action jump
```

Остановить все controls:

```bat
python scripts\minecraft_manual_control_smoke.py --action stop
```

Чат:

```bat
python scripts\minecraft_manual_control_smoke.py --action chat --chat-message "AgentGirl online"
```

## Debug JSON

Чтобы сохранить observation до/после:

```bat
python scripts\minecraft_manual_control_smoke.py --action move_forward --write-debug
```

Файл появится в:

```text
artifacts/debug/minecraft/manual_control_move_forward.json
```

`artifacts/` игнорируется git, поэтому эти debug-дампы безопасны.

## Что считается успехом

- Python получает `health.reachable = true`;
- `before.connection_state` показывает живое состояние bridge;
- `position_valid = true`;
- `sent_action.command` соответствует выбранному действию;
- `after.position` или `after.yaw/pitch` меняется для движения/поворота;
- `stop` отпускает все controls;
- тесты `tests/unit/minecraft` проходят.

Если `position` выглядит как `[null, y, null]`, значит Mineflayer сейчас отдаёт `NaN` для `x/z`.
В этом состоянии движение нельзя считать проверенным: сначала надо добиться `position_valid = true`.
