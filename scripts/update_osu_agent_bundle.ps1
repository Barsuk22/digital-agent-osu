param(
    [Parameter(Mandatory = $true)]
    [string] $InstallDir,

    [string] $ManifestUrl = "",

    [int] $WaitSeconds = 2
)

if (-not $env:OSU_AGENT_UPDATER_DETACHED) {
    $detachedScript = Join-Path $env:TEMP "osu_agent_update_detached.ps1"
    Copy-Item -LiteralPath $PSCommandPath -Destination $detachedScript -Force

    $env:OSU_AGENT_UPDATER_DETACHED = "1"

    Start-Process powershell.exe -ArgumentList @(
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$detachedScript`"",
        "-InstallDir", "`"$InstallDir`"",
        "-ManifestUrl", "`"$ManifestUrl`"",
        "-WaitSeconds", "$WaitSeconds"
    )

    exit 0
}

Set-Location $env:TEMP

$ErrorActionPreference = "Stop"

$logPath = Join-Path $env:TEMP "osu_agent_updater.log"
Start-Transcript -Path $logPath -Force | Out-Null

try {
    Write-Host "[update] log: $logPath"

    if (-not $ManifestUrl) {
        throw "ManifestUrl is empty"
    }

    if ($WaitSeconds -gt 0) {
        Start-Sleep -Seconds $WaitSeconds
    }

    Write-Host "[update] killing old app processes"

    for ($i = 0; $i -lt 20; $i++) {
        Get-Process OsuAgentStudio -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Get-Process OsuLazerController -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

        Start-Sleep -Milliseconds 500

        $stillRunning =
            (Get-Process OsuAgentStudio -ErrorAction SilentlyContinue) -or
            (Get-Process OsuLazerController -ErrorAction SilentlyContinue)

        if (-not $stillRunning) {
            break
        }
    }

    Start-Sleep -Seconds 2

    $tmp = Join-Path $env:TEMP "osu_agent_bundle_update"
    $extract = Join-Path $tmp "extract"

    if (Test-Path $tmp) {
        Remove-Item -Recurse -Force $tmp
    }

    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    New-Item -ItemType Directory -Path $extract -Force | Out-Null

    $mfPath = Join-Path $tmp "manifest.json"
    Write-Host "[update] downloading manifest"
    Invoke-WebRequest -Uri $ManifestUrl -OutFile $mfPath -UseBasicParsing

    $manifest = Get-Content $mfPath -Raw | ConvertFrom-Json

    $zipPath = Join-Path $tmp "bundle.zip"
    Write-Host "[update] downloading bundle v$($manifest.version)"
    Invoke-WebRequest -Uri $manifest.bundleZipUrl -OutFile $zipPath -UseBasicParsing

    Write-Host "[update] extracting to temp"
    Expand-Archive -Path $zipPath -DestinationPath $extract -Force

    $newExeInExtract = Join-Path $extract "app\OsuAgentStudio.exe"
    if (-not (Test-Path $newExeInExtract)) {
        throw "New exe not found in extracted bundle: $newExeInExtract"
    }

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    Write-Host "[update] cleaning old files"

    $pathsToClean = @(
        "external\osu_lazer_controller\publish",
        "external\osu_lazer_controller\configs",
        "artifacts\exports\onnx",
        "README.txt",
        "README_RU.txt",
        "README_FRIEND_RU.txt",
        "README_FRIEND_RU.md"
    )

    foreach ($relative in $pathsToClean) {
        $target = Join-Path $InstallDir $relative
        if (Test-Path $target) {
            $deleted = $false
            for ($try = 0; $try -lt 10; $try++) {
                try {
                    Remove-Item $target -Recurse -Force -ErrorAction Stop
                    $deleted = $true
                    break
                }
                catch {
                    Write-Host "[update] waiting for unlock: $target"
                    Start-Sleep -Seconds 1
                }
            }

            if (-not $deleted) {
                throw "Could not delete locked path: $target"
            }
        }
    }

    Write-Host "[update] copying new files"
    Copy-Item -Path (Join-Path $extract "*") -Destination $InstallDir -Recurse -Force

    $newExe = Join-Path $InstallDir "app\OsuAgentStudio.exe"

    if (-not (Test-Path $newExe)) {
        throw "Installed exe not found: $newExe"
    }

    Write-Host "[update] starting new version: $newExe"
    Start-Process -FilePath $newExe -WorkingDirectory (Split-Path $newExe)

    Write-Host "[update] done"
}
catch {
    Write-Host "[update] FAILED:"
    Write-Host $_
    Write-Host "Log: $logPath"
    Read-Host "Press Enter to close"
}
finally {
    Stop-Transcript | Out-Null
}