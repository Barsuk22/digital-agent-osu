# OsuLazerController

Внешний runtime-контроллер для переноса RL-агента osu! в `osu!lazer`.

Что уже есть:

- отдельный `.NET 8` controller;
- ZeroMQ bridge к Python policy server;
- экспорт `.osu` карты в bridge JSON;
- поиск окна, playfield mapping и capture окна;
- observation размерности `59`, совместимый с текущим `obs_to_numpy()`;
- active slider/spinner runtime state, ближе к Python `OsuJudge`;
- dry-run и live input через `SendInput`;
- JSON trace logging.

Конфиги:

- `configs/runtime.json`: безопасная диагностика без движения и кликов;
- `configs/runtime.live_probe.json`: автостарт по задержке, движение включено, клики выключены;
- `configs/runtime.live_click_probe.json`: короткий авто-probe с движением и кликами;
- `configs/runtime.live_click_probe.best.json`: короткий click-probe на текущем лучшем timing profile;
- `configs/runtime.live_move.json`: живой старт по `F8`, движение мыши включено, клики выключены;
- `configs/runtime.live_play.json`: живой старт по `F8`, движение и клики включены.
- `configs/profiles/*.json`: профили, которые можно сгенерировать под конкретную карту.

Сборка:

```powershell
dotnet build .\external\osu_lazer_controller\OsuLazerController.csproj
```

Запуск Python policy server отдельно:

```powershell
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.serve_osu_policy
```

Быстрый запуск безопасной диагностики:

```powershell
.\external\osu_lazer_controller\start_bridge.ps1
```

Живой тест с движением мыши:

```powershell
.\external\osu_lazer_controller\start_bridge.ps1 -ConfigPath .\external\osu_lazer_controller\configs\runtime.live_move.json
```

Автоматический probe с реальным движением, но без кликов:

```powershell
.\external\osu_lazer_controller\start_bridge.ps1 -ConfigPath .\external\osu_lazer_controller\configs\runtime.live_probe.json
```

Короткий автоматический probe с движением и кликами:

```powershell
.\external\osu_lazer_controller\start_bridge.ps1 -ConfigPath .\external\osu_lazer_controller\configs\runtime.live_click_probe.json
```

Живой тест с движением и кликами:

```powershell
.\external\osu_lazer_controller\start_bridge.ps1 -ConfigPath .\external\osu_lazer_controller\configs\runtime.live_play.json
```

Создать runtime-профиль под конкретную карту, например `Sentimental Love`:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.create_osu_lazer_runtime_profile --map sentimental_love_easy --mode live_probe
```

Короткая сводка по calibration/eval:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.report_osu_lazer_runtime_eval
```

Как запускать живой режим:

1. Откройте нужную карту в `osu!lazer`.
2. Запустите bridge с live-конфигом.
3. Когда будете готовы, нажмите `F8` в момент старта карты.

Практически лучше идти так:

1. Сначала `runtime.live_move.json`.
2. Проверить траекторию и тайминг.
3. Только потом переходить к `runtime.live_play.json`.

Анализ свежего runtime trace:

```powershell
cd D:\Projects\digital_agent_osu_project
& 'C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe' -m src.apps.analyze_osu_lazer_runtime
```
