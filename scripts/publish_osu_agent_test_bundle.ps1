# Builds a friend/test zip: Osu Agent Studio + OsuLazerController (self-contained) + configs.
# No Python / src — training & export are disabled in Studio; Play + agent still work.
# Run from repo root:  powershell -ExecutionPolicy Bypass -File .\scripts\publish_osu_agent_test_bundle.ps1
[CmdletBinding()]
param(
    [string] $OutputRoot = "dist",
    [string] $Version = "",
    [ValidateSet("Avalonia", "WinForms")]
    [string] $Studio = "Avalonia"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (-not $Version) {
    $versionProject = if ($Studio -eq "Avalonia") {
        Join-Path $repoRoot "external\osu_agent_studio_avalonia\OsuAgentStudio.Avalonia.csproj"
    } else {
        Join-Path $repoRoot "external\osu_agent_studio\OsuAgentStudio.csproj"
    }

    [xml] $csproj = Get-Content $versionProject
    $Version = $csproj.Project.PropertyGroup.Version | Select-Object -First 1
    if (-not $Version) { $Version = "1.0.0" }
}

$bundleName = "OsuAgentTestBundle-$Version"
$stage = Join-Path (Join-Path $repoRoot $OutputRoot) $bundleName
if (Test-Path $stage) {
    Remove-Item -Recurse -Force $stage
}
$appDir = Join-Path $stage "app"
$publishController = Join-Path $stage "external\osu_lazer_controller\publish"
$configsSrc = Join-Path $repoRoot "external\osu_lazer_controller\configs"

New-Item -ItemType Directory -Path $appDir -Force | Out-Null
New-Item -ItemType Directory -Path $publishController -Force | Out-Null

$studioProject = if ($Studio -eq "Avalonia") {
    Join-Path $repoRoot "external\osu_agent_studio_avalonia\OsuAgentStudio.Avalonia.csproj"
} else {
    Join-Path $repoRoot "external\osu_agent_studio\OsuAgentStudio.csproj"
}

Write-Host "[publish] OsuAgentStudio ($Studio) -> $appDir"
dotnet publish $studioProject `
    -c Release -r win-x64 --self-contained true `
    -o $appDir `
    /p:PublishSingleFile=false | Write-Host

Write-Host "[publish] OsuLazerController -> $publishController"
dotnet publish (Join-Path $repoRoot "external\osu_lazer_controller\OsuLazerController.csproj") `
    -c Release -r win-x64 --self-contained true `
    -o $publishController `
    /p:PublishSingleFile=false | Write-Host

Write-Host "[copy] configs"
$controllerRoot = Join-Path $stage "external\osu_lazer_controller"
New-Item -ItemType Directory -Path $controllerRoot -Force | Out-Null
Copy-Item -Path $configsSrc -Destination $controllerRoot -Recurse -Force

$dirs = @(
    "data\raw\osu\maps",
    "artifacts\runs\osu_lazer_transfer_precision_accuracy\checkpoints",
    "artifacts\exports\onnx"
)
foreach ($d in $dirs) {
    $p = Join-Path $stage $d
    New-Item -ItemType Directory -Path $p -Force | Out-Null
}

$readme = Join-Path $stage "README_RU.txt"
$readmeText = @"
Osu Agent — тестовый бандл v$Version
================================

Что внутри:
- app\OsuAgentStudio.exe  — лаунчер
- external\osu_lazer_controller\publish\OsuLazerController.exe  — контроллер
- external\osu_lazer_controller\configs\  — runtime JSON
- data\raw\osu\maps\  — положи сюда .osu если нужно? Хотя хуй тебе - не клади, а то сломаешь нахер... Тьфу, от греха подальше
- artifacts\  — чекпоинты / onnx (Они будут обновляца сами. Махия)

Запуск: открой app\OsuAgentStudio.exe из этой папки ($bundleName). Корень должен содержать папку external\ — не переноси только exe в другое место без остального. (логично, да?) Ну а чо, а вдруг додумаешься вынести екзешник в жопу мира)

Studio UI: $Studio.

Обучение в Studio будет неактивно (нет src/). Play / Launch Agent — Вот эти хоть как и хоть куды пользуйся.

Переменная OSUAGENTSTUDIO_PROJECT_ROOT: если положишь полный репозиторий в другую папку, укажи путь на корень с src\ и external\. Не думаю что пригодится тебе

Обновления: см. scripts\update_osu_agent_bundle.ps1 и bundle_manifest.example.json
"@
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText($readme, $readmeText, $utf8Bom)

Write-Host "[copy] updater scripts"
$scriptsOut = Join-Path $stage "scripts"
New-Item -ItemType Directory -Path $scriptsOut -Force | Out-Null
Copy-Item (Join-Path $repoRoot "scripts\update_osu_agent_bundle.ps1") $scriptsOut -Force
Copy-Item (Join-Path $repoRoot "scripts\bundle_manifest.example.json") $scriptsOut -Force

Write-Host "[copy] onnx models"
$onnxSrc = Join-Path $repoRoot "artifacts\exports\onnx"
$onnxOut = Join-Path $stage "artifacts\exports\onnx"
if (Test-Path $onnxSrc) {
    Copy-Item -Path (Join-Path $onnxSrc "*.onnx") -Destination $onnxOut -Force
}

$zipPath = Join-Path (Join-Path $repoRoot $OutputRoot) "OsuAgentTestBundle-$Version.zip"

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force

Write-Host "[done] bundle zip: $zipPath"
