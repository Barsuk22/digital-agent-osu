param(
  [string]$ConfigPath = "",
  [switch]$SkipPolicyServer,
  [switch]$ForceStartPolicyServer
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "C:\Users\valer\AppData\Local\Programs\Python\Python313\python.exe"
$projectRoot = Resolve-Path (Join-Path $root "..\..")
$resolvedConfigPath = if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
  Join-Path $root "configs\runtime.json"
} else {
  $ConfigPath
}
$config = Get-Content -Path $resolvedConfigPath -Raw | ConvertFrom-Json

function Test-TcpPortOpen {
  param(
    [string]$ServerHost,
    [int]$Port
  )

  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $iar = $client.BeginConnect($ServerHost, $Port, $null, $null)
    $connected = $iar.AsyncWaitHandle.WaitOne(400)
    if (-not $connected) {
      return $false
    }

    $client.EndConnect($iar)
    return $true
  }
  catch {
    return $false
  }
  finally {
    $client.Close()
  }
}

function Get-BridgeEndpoint {
  param([string]$Address)

  if ($Address -match '^tcp://(?<host>[^:]+):(?<port>\d+)$') {
    return @{
      Host = $Matches.host
      Port = [int]$Matches.port
    }
  }

  return $null
}

Write-Host "[bridge] exporting beatmap json..."
& $python -m src.apps.export_osu_lazer_bridge_map `
  --map $config.beatmap.sourceOsuPath `
  --out $config.beatmap.exportJsonPath

$server = $null

if ($config.policyBridge.mode -eq "onnx") {
  if (-not (Test-Path $config.policyBridge.modelPath)) {
    Write-Host "[bridge] exporting ONNX policy..."
    & $python -m src.apps.export_osu_policy_onnx --out $config.policyBridge.modelPath
  }
} else {
  $endpoint = Get-BridgeEndpoint -Address $config.policyBridge.address
  $serverAlreadyRunning = $false
  if ($endpoint) {
    $serverAlreadyRunning = Test-TcpPortOpen -ServerHost $endpoint.Host -Port $endpoint.Port
  }

  if ($SkipPolicyServer) {
    Write-Host "[bridge] skipping Python policy server start by request."
  }
  elseif ($serverAlreadyRunning -and -not $ForceStartPolicyServer) {
    Write-Host "[bridge] policy server already reachable at $($config.policyBridge.address), reusing existing process."
  }
  else {
    Write-Host "[bridge] starting Python policy server..."
    $server = Start-Process `
      -FilePath $python `
      -ArgumentList "-m", "src.apps.serve_osu_policy" `
      -WorkingDirectory $projectRoot `
      -WindowStyle Hidden `
      -PassThru
  }
}

try {
  Start-Sleep -Seconds 3
  Write-Host "[bridge] starting controller..."
  $env:DOTNET_CLI_HOME = "D:\Projects\digital_agent_osu_project\.dotnet_home"
  $env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
  dotnet run --project (Join-Path $root "OsuLazerController.csproj") --no-build -- $resolvedConfigPath
}
finally {
  if ($server -and -not $server.HasExited) {
    Write-Host "[bridge] stopping Python policy server..."
    Stop-Process -Id $server.Id -Force
  }
}
