# osu!lazer runtime runbook

Актуально на 2026-04-20.

Этот файл фиксирует текущий рабочий запуск переноса RL-агента в `osu!lazer`.

## Что уже проверено

- Python policy server запускается и грузит:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

- C# controller находит окно `osu!`.
- C# controller успешно делает `ping` в Python policy server.
- Bridge map для `Sentimental Love` экспортируется в JSON.
- C# runtime loop запускается по `F8`, отправляет observation в Python и получает action.
- Mouse smoke test проходит.
- Runtime loop выводит tick logs с `dx`, `dy`, `click_strength`, `policy latency`, `loop time`.

Проверенный runtime контур:

```text
osu!lazer
  <-> C# OsuLazerController
  <-> ZeroMQ / NetMQ
  <-> Python policy server
  <-> PyTorch checkpoint
```

## Установка Python IPC зависимости

Из корня проекта:

```powershell
cd D:\Projects\digital_agent_osu_project
pip install pyzmq
```

Проверенный результат:

```text
Successfully installed pyzmq-27.1.0
```

`torch` и `numpy` уже должны быть доступны в текущем Python окружении.

## Экспорт карты для C# bridge

Из корня проекта:

```powershell
cd D:\Projects\digital_agent_osu_project
python -m src.apps.export_osu_lazer_bridge_map --beatmap "D:\Projects\digital_agent_osu_project\data\raw\osu\maps\Sati Akura - Sentimental Love\Sati Akura - Sentimental Love (TV Size) (Nao Tomori) [Myxo's Easy].osu" --out "D:\Projects\digital_agent_osu_project\external\osu_lazer_controller\maps\bridge_map.json"
```

Ожидаемый результат:

```text
[exported] D:\Projects\digital_agent_osu_project\external\osu_lazer_controller\maps\bridge_map.json
[objects] 88
[beatmap] Sati Akura - Sentimental Love (TV Size) [Myxo's Easy]
```

Текущий bridge JSON:

```text
external/osu_lazer_controller/maps/bridge_map.json
```

Важно: после изменения bridge schema файл нужно переэкспортировать. C# loader теперь ожидает расширенный JSON с:

- `time_ms` / `end_time_ms`;
- metadata difficulty;
- timing points;
- slider payload: `duration_ms`, `span_duration_ms`, `repeats`, `pixel_length`, `curve_type`, `control_points`, `sampled_points`;
- spinner payload: `end_time_ms`, `duration_ms`.

Если C# controller пишет, что slider/spinner payload отсутствует, значит запущен старый `bridge_map.json`. Нужно повторить экспорт командой выше.

## Offline проверка bridge JSON

После экспорта можно проверить C# загрузку bridge-файла без запуска `osu!lazer` и без Python policy server:

```powershell
cd D:\Projects\digital_agent_osu_project\external\osu_lazer_controller
dotnet run --project .\OsuLazerController\OsuLazerController.csproj -- --dump-bridge
```

Ожидаемый результат:

```text
[dump] loading bridge map: ...
[beatmap] Sati Akura - Sentimental Love (TV Size) [Myxo's Easy] objects=88 timing_points=...
[objects] sliders=... spinners=...
[first-slider] index=0 time=855.0 end=... duration=... repeats=... samples=...
[obs] t=... len=59 first_kind=... slider_active=... slider_progress=...
```

Эта команда полезна как быстрый sanity-check перед live loop. Если она не проходит, live запуск тоже лучше не начинать.

## Observation parity check

После обычного `--dump-bridge` можно сохранить machine-readable observation dump:

```powershell
cd D:\Projects\digital_agent_osu_project\external\osu_lazer_controller
dotnet run --project .\OsuLazerController\OsuLazerController.csproj -- --dump-obs-json "D:\Projects\digital_agent_osu_project\external\osu_lazer_controller\maps\bridge_obs_dump.json"
```

Затем из корня проекта сравнить C# observation dump с независимой Python-реализацией bridge observation:

```powershell
cd D:\Projects\digital_agent_osu_project
python -m src.apps.compare_osu_lazer_bridge_obs --bridge "D:\Projects\digital_agent_osu_project\external\osu_lazer_controller\maps\bridge_map.json" --dump "D:\Projects\digital_agent_osu_project\external\osu_lazer_controller\maps\bridge_obs_dump.json"
```

Ожидаемый результат:

```text
[parity] observations=... max_abs_diff=...
[parity] OK
```

Эта проверка пока сравнивает C# bridge observation со stateless Python bridge logic. Она не заменяет будущую parity-проверку против полного `OsuEnv/OsuJudge`, потому что `OsuJudge` учитывает action history, head hits, slider hold и spinner spin accumulation.

## Запуск Python policy server

В отдельной PowerShell консоли из корня проекта:

```powershell
cd D:\Projects\digital_agent_osu_project
python -m src.apps.serve_osu_policy
```

Ожидаемый старт:

```text
OSU POLICY SERVER STARTED
Bind: tcp://127.0.0.1:5555
Checkpoint: D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase8_easy_generalization\checkpoints\best_easy_generalization.pt
Device: cuda
Observation dim: 59
Action dim: 3
```

Ожидаемые runtime логи после работы C# controller:

```text
[server] requests=500 last_latency_ms=... dx=... dy=... click=...
[server] requests=1000 last_latency_ms=... dx=... dy=... click=...
```

Если нужно принудительно выбрать checkpoint:

```powershell
$env:OSU_POLICY_CHECKPOINT='D:\Projects\digital_agent_osu_project\artifacts\runs\osu_phase8_easy_generalization\checkpoints\best_easy_generalization.pt'
python -m src.apps.serve_osu_policy
Remove-Item Env:\OSU_POLICY_CHECKPOINT
```

## Запуск C# controller

В отдельной PowerShell консоли:

```powershell
cd D:\Projects\digital_agent_osu_project\external\osu_lazer_controller
dotnet run --project .\OsuLazerController\OsuLazerController.csproj
```

Удобный вариант для повторных runtime-прогонов без mouse smoke test, с более длинным loop и явным trace path:

```powershell
cd D:\Projects\digital_agent_osu_project\external\osu_lazer_controller
dotnet run --project .\OsuLazerController\OsuLazerController.csproj -- --no-smoke --ticks 900 --trace "D:\Projects\digital_agent_osu_project\external\osu_lazer_controller\logs\runtime_trace_latest.json"
```

Ожидаемый старт:

```text
OsuLazerController starting...
[window] search candidates: osu!(lazer), osu!
[window] found: Handle=..., Title='osu!', Client={X=0,Y=0,Width=1920,Height=1080}
[policy] ping ok: {"ok": true, "cmd": "pong", ... "obs_dim": 59, "action_dim": 3, ...}
[capture] ok: 1920x1080
[beatmap] Sati Akura - Sentimental Love (TV Size) [Myxo's Easy] objects=88
[mouse] smoke circle start
[mouse] smoke circle end
[loop] ready at 60 Hz
[loop] keep osu! focused
[loop] press F8 to start map clock, F9 to stop loop
```

После фокуса на `osu!lazer` нажать:

```text
F8 - старт map clock и runtime loop
F9 - остановка loop
```

Ожидаемый loop log:

```text
[loop] map clock started
[mapper] playfield rect = {X=240,Y=0,Width=1440,Height=1080}
[tick 0000] t=...ms cx=... cy=... sx=... sy=... dx=... dy=... click=... down=... sl=... sp=... policy=...ms loop=...ms
```

`down` показывает текущее состояние левой кнопки мыши, `sl` - активный slider block в observation, `sp` - активный spinner block.

Click handling сейчас работает через состояние кнопки:

- обычный click threshold: `click >= 0.75`;
- slider hold threshold: active slider и `click >= 0.45`;
- spinner hold threshold: active spinner и `click >= 0.45`;
- на остановке loop controller отпускает кнопку, если она была зажата.

После завершения loop controller сохраняет runtime trace:

```text
external/osu_lazer_controller/logs/runtime_trace_latest.json
```

В trace попадают:

- loop time;
- IPC/policy latency;
- cursor playfield/screen position;
- action `dx/dy/click_strength`;
- mouse down state;
- active slider/spinner flags;
- slider target/progress/distance/inside-follow;
- spinner progress/distance-to-center;
- first upcoming object kind/time-to-hit.

Этот файл является текущей основной диагностикой для сравнения live runtime с simulator behavior.

## Текущие ограничения MVP

- `ScreenCapture` пока проверяет client area, но не делает реальный pixel capture.
- C# не парсит `.osu` напрямую, а читает `bridge_map.json`.
- `bridge_map.json` теперь содержит расширенные slider/spinner данные, но его нужно переэкспортировать после изменения schema.
- `ObservationBuilder` собирает вектор длиной 59 и уже заполняет базовый slider/spinner runtime state, но это еще не полная parity с Python `OsuJudge`.
- `RuntimeLoop` по умолчанию ограничен `RuntimeDummyTicks`, но для ручных прогонов можно задавать `--ticks N`.
- Click handling уже использует `LeftDown` / `LeftUp` transitions и базовые hold thresholds для sliders/spinners, но thresholds еще не откалиброваны под Lazer.
- Playfield mapping пока базовый `512x384 -> 4:3 client rect`, без calibration offsets.

## Что делать следующим

Следующий лучший шаг - довести observation до совместимости с Python simulator, но сделать это без переписывания всего C# parser сразу.

Рекомендуемый порядок:

1. Расширить bridge export JSON: добавить slider duration, end time, repeats, pixel length, control points, curve type, spinner end time.
2. Расширить C# domain models под эти поля.
3. Перенести минимальную slider/spinner runtime geometry, нужную именно для `obs_to_numpy()`.
4. Добавить parity test: для одной карты и набора времен сравнить Python observation и C# observation.
5. Только после parity test запускать следующий end-to-end loop.

Это даст самый большой прирост качества, потому что сейчас policy получает правильную длину observation, но не всю обучающую семантику.
