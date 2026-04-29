# Minecraft Agent Phase A Status

Статус: базовый каркас создан.

Дата: 2026-04-29.

## Что добавлено

- Отдельный домен `src/skills/minecraft`, рядом с `src/skills/osu`.
- Конфиг Фазы A: `configs/minecraft/phase_a.yaml`.
- Типы наблюдений и действий Minecraft.
- `NullMinecraftConnector` для dry-run тестов без запуска Minecraft.
- `ObservationBuilder` с поддержкой frame stack.
- `ActionController` с безопасной нормализацией low-level actions.
- Базовый `RewardSystem`.
- `TrainingRunner` для dry-run цикла.
- `EvaluationRunner` для smoke-проверки.
- `CheckpointManager` для manifest/checkpoint директории.
- `DebugViewer` для записи observation JSON.
- Unit-тесты каркаса.

## Изоляция от OSU

Minecraft-модуль не импортируется из OSU-модуля и не меняет существующие OSU конфиги, раннеры, чекпоинты или release-сборку.

Артефакты Minecraft идут в отдельные пути:

```text
artifacts/checkpoints/minecraft
artifacts/logs/minecraft
artifacts/debug/minecraft
artifacts/runs/minecraft
data/minecraft
```

`artifacts/` уже игнорируется git, поэтому dry-run выводы не попадут в коммит.

## Проверка

Команда:

```text
python -m pytest tests\unit\minecraft\test_phase_a_scaffold.py -q
```

Результат:

```text
4 passed
```

Smoke eval:

```text
EvaluationSummary(run_id='minecraft_phase_a_null_smoke', connector='null', steps=2, total_reward=0.02, passed=True)
```

## Следующий шаг

Фаза A.2:

1. выбрать конкретную реализацию bridge: Mineflayer, мод или серверный API;
2. реализовать внешний процесс, который говорит по JSON-lines TCP;
3. получить live observation из клиента или сервера;
4. отправить безопасное тестовое действие;
5. записать debug observation/video/screenshot.

## Phase A.2 Transport Scaffold

Добавлен универсальный TCP bridge-слой:

- `TcpMinecraftConnector`;
- `MinecraftBridgeConfig`;
- `make_minecraft_connector`;
- JSON-lines protocol docs;
- example config для live bridge;
- mock TCP bridge unit-тест.

Документ протокола:

```text
docs/minecraft/bridge_protocol_ru.md
```

Smoke-команда:

```text
python scripts/minecraft_phase_a_smoke.py --connector null --steps 5
```

Для будущего live bridge:

```text
python scripts/minecraft_phase_a_smoke.py --connector tcp --host 127.0.0.1 --port 4711 --steps 5
```

## Phase A.3 Mineflayer Bridge

Статус: транспортный bridge добавлен.

Добавлено:

- Node.js bridge-процесс в `external/minecraft_mineflayer_bridge`;
- `package.json`;
- `src/bridge.js`;
- `README_RU.md`;
- Windows launcher `scripts/run_minecraft_mineflayer_bridge.bat`;
- Python config `configs/minecraft/phase_a_mineflayer_bridge.yaml`;
- документация `docs/minecraft/mineflayer_bridge_ru.md`;
- поддержка `command`-based low-level actions в Python `MinecraftAction`;
- `nearby_players` в Python observation model;
- unit-тесты сериализации command actions и Mineflayer-like observation snapshot.

Проверки:

```text
python -m pytest tests\unit\minecraft -q
9 passed
```

```text
node --check external\minecraft_mineflayer_bridge\src\bridge.js
```

```text
python scripts\minecraft_phase_a_smoke.py --connector null --steps 5
ok: true
```

## Phase B.1 Manual Control Smoke

Статус: начальный manual-control слой добавлен.

Добавлено:

- `src/skills/minecraft/actions/manual_control.py`;
- `scripts/minecraft_manual_control_smoke.py`;
- `docs/minecraft/phase_b1_manual_control_ru.md`;
- unit-тесты manual action mapping.

Примеры:

```text
python scripts/minecraft_manual_control_smoke.py --action move_forward
python scripts/minecraft_manual_control_smoke.py --action look_right --look-degrees 15
python scripts/minecraft_manual_control_smoke.py --action jump
python scripts/minecraft_manual_control_smoke.py --action stop
```

## Phase B.2 Movement Probe

Статус: scripted movement probe добавлен.

Добавлено:

- `src/skills/minecraft/actions/movement_probe.py`;
- `scripts/minecraft_movement_probe.py`;
- `docs/minecraft/phase_b2_movement_probe_ru.md`;
- unit-тесты movement probe.

Команда:

```text
python scripts/minecraft_movement_probe.py --write-debug
```

Успешный verdict:

```text
body_controls_ok
```

## Phase B.3 Body Primitives

Статус: reusable body primitives добавлены.

Добавлено:

- `src/skills/minecraft/actions/body_primitives.py`;
- `scripts/minecraft_body_primitives_smoke.py`;
- `docs/minecraft/phase_b3_body_primitives_ru.md`;
- unit-тесты body primitives.

Primitives:

```text
observe
stop_all
look_delta
move_impulse
measure_delta
step_forward_and_measure
turn_and_step
```

Smoke:

```text
python scripts/minecraft_body_primitives_smoke.py --primitive turn_and_step --write-debug
```

## Phase B.4 LookAtTarget Skeleton

Статус: эвристический skeleton добавлен.

Добавлено:

- `src/skills/minecraft/skills/look_at.py`;
- `scripts/minecraft_look_at_smoke.py`;
- `docs/minecraft/phase_b4_look_at_target_ru.md`;
- unit-тесты геометрии и controller loop.

Smoke:

```text
python scripts/minecraft_look_at_smoke.py --target nearest_player --write-debug
python scripts/minecraft_look_at_smoke.py --target nearest_block --write-debug
```
