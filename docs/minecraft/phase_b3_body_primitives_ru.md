# Phase B.3 Body Primitives

Цель B.3 - сделать маленький reusable API тела агента поверх Mineflayer bridge.

Это всё ещё не навык и не обучение. Это слой, из которого позже будут собираться `LookAtTarget`, `MoveToTarget`, `FollowPlayer` и другие heuristic/PPO skills.

## Primitives

```text
observe
stop_all
look_delta
move_impulse
measure_delta
step_forward_and_measure
turn_and_step
```

## Smoke

Проверить весь мини-набор:

```bat
python scripts\minecraft_body_primitives_smoke.py --primitive turn_and_step --write-debug
```

Только шаг вперёд:

```bat
python scripts\minecraft_body_primitives_smoke.py --primitive step_forward --duration-ms 500 --settle-ms 700
```

Только поворот:

```bat
python scripts\minecraft_body_primitives_smoke.py --primitive look --yaw-degrees 15
```

Остановить controls:

```bat
python scripts\minecraft_body_primitives_smoke.py --primitive stop
```

## Debug

При `--write-debug` файл сохраняется в:

```text
artifacts/debug/minecraft/body_primitive_<name>.json
```

## Что дальше

После B.3 можно начинать B.4:

```text
LookAtDirection / LookAtTarget skeleton
```

И затем:

```text
MoveToPoint / MoveToTarget heuristic skeleton
```
