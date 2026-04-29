# Minecraft Bridge Protocol

Это минимальный протокол между Python-агентом и внешним Minecraft-транспортом.

Транспорт может быть любым:

- Mineflayer bridge;
- Fabric/Forge mod;
- локальный серверный bridge;
- тестовый mock server.

Python-слой не зависит от конкретного транспорта. Он отправляет JSON-lines сообщения по TCP и получает JSON-lines ответы.

## Соединение

По умолчанию:

```text
host: 127.0.0.1
port: 4711
encoding: utf-8
framing: one JSON object per line
```

## Запросы

### ping

```json
{"type":"ping","payload":{}}
```

Ответ:

```json
{"ok":true,"payload":{"message":"ok"}}
```

### reset

```json
{"type":"reset","payload":{}}
```

Ответ должен вернуть первое наблюдение.

### observe

```json
{"type":"observe","payload":{}}
```

Ответ должен вернуть текущее наблюдение.

### action

```json
{
  "type": "action",
  "payload": {
    "forward": 1.0,
    "strafe": 0.0,
    "jump": false,
    "sneak": false,
    "sprint": false,
    "attack": false,
    "use": false,
    "drop": false,
    "hotbar_slot": null,
    "camera_yaw_delta": 2.0,
    "camera_pitch_delta": 0.0
  }
}
```

Ответ должен вернуть новое наблюдение после применения действия.

Начиная с Mineflayer bridge, preferred action payload использует `command`:

```json
{"type":"action","payload":{"command":"move_forward","duration_ms":120}}
```

Поддерживаемые команды:

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

Для `look_delta` дельты камеры передаются в градусах:

```json
{"type":"action","payload":{"command":"look_delta","camera_yaw_delta":10,"camera_pitch_delta":-2}}
```

### close

```json
{"type":"close","payload":{}}
```

## Формат observation payload

Минимальный payload:

```json
{
  "tick": 1,
  "hp": 20.0,
  "hunger": 20.0,
  "armor": 0.0,
  "air": 300.0,
  "position": [0.0, 64.0, 0.0],
  "yaw": 0.0,
  "pitch": 0.0,
  "selected_slot": 0,
  "item_in_hand": "minecraft:air",
  "biome": "plains",
  "time_of_day": 1000,
  "inventory": [],
  "nearby_blocks": [],
  "nearby_entities": [],
  "events": []
}
```

## Ошибки

Ошибка возвращается так:

```json
{"ok":false,"error":"reason"}
```

Python-коннектор превратит такой ответ в `BridgeProtocolError`.
