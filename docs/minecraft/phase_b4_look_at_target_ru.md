# Phase B.4 LookAtTarget Skeleton

Цель B.4 - первый эвристический навык взгляда:

```text
current position + yaw/pitch + target point -> yaw_delta/pitch_delta -> look_delta steps -> alignment check
```

Это ещё не PPO. Это deterministic skill skeleton, который потом понадобится для:

- `MoveToTarget`;
- `MineBlock`;
- `FollowPlayer`;
- `Combat`;
- `InteractWithBlock`.

## Smoke

Посмотреть на ближайшего игрока:

```bat
python scripts\minecraft_look_at_smoke.py --target nearest_player --write-debug
```

Посмотреть на ближайший блок:

```bat
python scripts\minecraft_look_at_smoke.py --target nearest_block --write-debug
```

Посмотреть на координаты:

```bat
python scripts\minecraft_look_at_smoke.py --target coords --coords -5 72 10 --write-debug
```

## Успех

Успешный результат:

```text
verdict = look_at_target_ok
abs(yaw_error_degrees) <= tolerance
abs(pitch_error_degrees) <= tolerance
```

По умолчанию tolerance:

```text
3 degrees
```

## Debug

При `--write-debug` файл сохраняется:

```text
artifacts/debug/minecraft/look_at_target.json
```
