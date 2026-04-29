# Mineflayer Bridge для Minecraft Agent

Этот bridge - отдельный Node.js процесс между Minecraft server и Python-агентом.

Он:

- подключает Mineflayer-бота `AgentGirl` к локальному Minecraft server;
- поднимает JSON-lines TCP server на `127.0.0.1:4711`;
- принимает команды от Python;
- возвращает observation snapshot;
- делает low-level actions короткими безопасными импульсами;
- отпускает все клавиши при `stop`, `close`, ошибке или завершении.

## Требования

- Node.js 18+.
- Локальный Minecraft server `1.20.1`.
- Offline-mode сервер, если используется `auth=offline`.

## Установка

Из папки bridge:

```bat
cd external\minecraft_mineflayer_bridge
npm install
```

## Запуск

Сначала запусти Minecraft server на:

```text
localhost:25565
```

Потом:

```bat
npm start
```

Или из корня проекта:

```bat
scripts\run_minecraft_mineflayer_bridge.bat
```

## Настройки через env

```text
BRIDGE_HOST=127.0.0.1
BRIDGE_PORT=4711
MC_HOST=localhost
MC_PORT=25565
MC_USERNAME=AgentGirl
MC_VERSION=1.20.1
MC_AUTH=offline
BLOCK_RADIUS=3
ENTITY_RADIUS=16
MAX_PULSE_MS=500
DEFAULT_PULSE_MS=120
```

## Проверка из Python

Из корня проекта:

```bat
python scripts\minecraft_phase_a_smoke.py --connector tcp --host 127.0.0.1 --port 4711 --steps 5
```

Ожидаемо:

- Python проверяет `ping`;
- получает `reset/observe`;
- отправляет короткие `noop`, `move_forward`, `look_delta`;
- bridge возвращает live observation.
