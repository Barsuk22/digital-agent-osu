# osu!lazer Bridge Architecture

Этот документ фиксирует первый рабочий контур переноса RL-агента из симулятора в `osu!lazer`.

## Stage A

```text
[osu!lazer]
    ^
    |
screen/input
    |
[C# External Controller]
    |
observation/action IPC
    |
[Python Policy Server]
```

## Source of truth

Python-часть остаётся эталоном для:

- observation normalization;
- checkpoint loading;
- baseline policy inference;
- совместимости с `best_easy_generalization.pt`.

Общий runtime-модуль лежит в:

```text
src/skills/osu/policy/runtime.py
```

Он используется и eval-пайплайном, и live policy server.

## Observation contract

- observation shape: `59`
- dtype: `float32`
- payload:

```json
{
  "command": "act",
  "obs": [0.0, 0.1, 0.2]
}
```

- action response:

```json
{
  "ok": true,
  "dx": 0.0,
  "dy": 0.0,
  "click_strength": 0.0,
  "latency_ms": 1.23
}
```

## Current implementation status

Уже сделано:

- выделен общий policy runtime;
- добавлен `src/apps/serve_osu_policy.py`;
- добавлен `src/apps/export_osu_lazer_bridge_map.py`;
- создан `external/osu_lazer_controller` skeleton;
- подключён ZeroMQ bridge из C# в Python;
- добавлен WinAPI window discovery;
- добавлен bridge-friendly beatmap JSON export;
- добавлена C# загрузка карты и выбор upcoming объектов;
- добавлен C# map timer;
- добавлен первый observation builder;
- добавлен action applier с dry-run и opt-in real-input режимом;
- добавлен client-area screenshot capture;
- зафиксирован runtime config и trace logging.

Следующие инженерные шаги:

1. подключить реальный IPC transport в C#;
2. добавить окно/ввод;
3. перенести `.osu` parser semantics и runtime geometry;
4. собрать identical observation builder;
5. включить end-to-end loop.
