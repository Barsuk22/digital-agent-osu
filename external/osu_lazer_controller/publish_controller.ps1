param(
  [string]$Configuration = "Release",
  [string]$Runtime = "win-x64",
  [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $root "..\..")
$publishDir = if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  Join-Path $projectRoot "release\osu_lazer_controller"
} else {
  $OutputDir
}

$env:DOTNET_CLI_HOME = Join-Path $projectRoot ".dotnet_home"
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"

dotnet publish `
  (Join-Path $root "OsuLazerController.csproj") `
  -c $Configuration `
  -r $Runtime `
  -p:PublishSingleFile=true `
  --self-contained true `
  -o $publishDir

Write-Host "[publish] controller => $publishDir"
