# Mineflayer Bridge

Фаза A.3 добавляет отдельный Node.js bridge-процесс:

```text
Minecraft server 1.20.1 <-> Mineflayer bot AgentGirl <-> TCP JSON-lines bridge <-> Python agent
```

Bridge лежит здесь:

```text
external/minecraft_mineflayer_bridge
```

## Что он делает

- Поднимает TCP server на `127.0.0.1:4711`.
- Подключает `AgentGirl` к `localhost:25565`.
- Использует Minecraft version `1.20.1`.
- Работает в offline auth mode.
- Принимает JSON-lines команды от Python.
- Возвращает observation snapshot.
- Выполняет движения короткими импульсами.
- Отпускает все control states при `stop`, `close`, ошибке и завершении.

## Observation snapshot

Минимально возвращаются:

- `tick`;
- `time`;
- `position`;
- `yaw`;
- `pitch`;
- `hp`;
- `hunger` / `food`;
- `selected_slot`;
- `item_in_hand`;
- `inventory`;
- `nearby_entities`;
- `nearby_players`;
- `nearby_blocks`;
- `connection_state`;
- `events`.

## Actions

Python отправляет `type=action`, а в `payload.command` одно из:

```text
noop
move_forward
move_back
move_left
move_right
jump
sneak
sprint
look_delta
chat
stop
```

Пример:

```json
{"type":"action","payload":{"command":"move_forward","duration_ms":120}}
```

Поворот камеры:

```json
{"type":"action","payload":{"command":"look_delta","camera_yaw_delta":10,"camera_pitch_delta":0}}
```

Дельты камеры задаются в градусах. Bridge переводит их в radians для Mineflayer.

## Запуск

1. Запусти локальный Minecraft server `1.20.1` на `localhost:25565`.
2. Убедись, что сервер допускает offline auth, если используется `MC_AUTH=offline`.
3. Из корня проекта запусти:

```bat
scripts\run_minecraft_mineflayer_bridge.bat
```

4. В другом терминале:

```bat
python scripts\minecraft_phase_a_smoke.py --connector tcp --host 127.0.0.1 --port 4711 --steps 5
```

## Конфиг

Python config:

```text
configs/minecraft/phase_a_mineflayer_bridge.yaml
```

Node env defaults:

```text
BRIDGE_HOST=127.0.0.1
BRIDGE_PORT=4711
MC_HOST=localhost
MC_PORT=25565
MC_USERNAME=AgentGirl
MC_VERSION=1.20.1
MC_AUTH=offline
```

## Границы Фазы A.3

В этой фазе нет:

- PPO;
- новых навыков;
- screen vision;
- UI-интеграции;
- release-сборки.

Это только транспорт между Python и Minecraft.
