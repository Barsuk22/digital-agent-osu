# Раздача тест-сборки другу (без исходников)

## Что реально отдать

Собранный **.zip** с `OsuAgentStudio` + `OsuLazerController` + `configs` + пустые `data` / `artifacts`. Исходники Python в архив не входят: у друга вкладки обучения и экспорта ONNX будут отключены, **Play / Launch Agent** работают.

## Собрать архив у себя

Из корня репозитория:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\publish_osu_agent_test_bundle.ps1
```

Результат: `dist/OsuAgentTestBundle-<версия>.zip` (версия берётся из `OsuAgentStudio.csproj`).

## Как другу запускать

1. Распаковать zip **целиком** (нужна структура с `external\` рядом с `app\`).
2. Запускать `app\OsuAgentStudio.exe`.
3. Положить модель в `artifacts\exports\onnx\lazer_transfer_generalization.onnx` и при необходимости чекпоинты в `artifacts\runs\...` (как у тебя в проекте).

## Автообновление «одной командой»

Полностью автоматически из интернета без своего сервера обычно делают так:

1. Залить zip в **GitHub Releases** (или облако с прямой ссылкой).
2. Выложить JSON-манифест с полями `version` и `bundleZipUrl` (см. `scripts/bundle_manifest.example.json`).
3. Друг запускает:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update_osu_agent_bundle.ps1 -InstallDir "D:\OsuAgentBundle" -ManifestUrl "https://твой-хост/bundle_manifest.json"
```

Ты после изменений: снова `publish_osu_agent_test_bundle.ps1`, новый релиз, обновляешь `version` + `bundleZipUrl` в манифесте — у друга скрипт подтянет новую сборку.

**Важно:** для доверия к обновлениям лучше HTTPS + проверка подписи или как минимум фиксированный домен; в скрипте сейчас только скачивание и распаковка.

## Полный репозиторий у друга (опционально)

Если нужны обучение и экспорт из Studio: склонировать репозиторий или выставить переменную окружения `OSUAGENTSTUDIO_PROJECT_ROOT` на корень с папками `src\` и `external\`.
