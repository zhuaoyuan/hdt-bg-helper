# Builds the diagnostic logger against the newest installed official HDT and optionally deploys it.
#   .\build.ps1            build only
#   .\build.ps1 -Deploy    build, then copy the DLL into %APPDATA%\HearthstoneDeckTracker\Plugins
# Close HDT before deploying: HDT keeps loaded plugin DLLs locked.
param([switch]$Deploy)

$ErrorActionPreference = 'Stop'
$dotnet = 'C:\Program Files\dotnet\dotnet.exe'
$root = Join-Path $env:LOCALAPPDATA 'HearthstoneDeckTracker'

$app = Get-ChildItem $root -Directory -Filter 'app-*' |
	Sort-Object { [version]($_.Name -replace '^app-', '') } -Descending |
	Select-Object -First 1
if (-not $app) { throw "No official HDT app-* directory under $root" }
Write-Host "HDT: $($app.FullName)"

$proj = Join-Path $PSScriptRoot 'HdtDiagLogger\HdtDiagLogger.csproj'
& $dotnet build $proj -c Release "-p:HdtDir=$($app.FullName)"
if ($LASTEXITCODE -ne 0) { throw "build failed" }

$dll = Join-Path $PSScriptRoot 'HdtDiagLogger\bin\Release\net472\HdtDiagLogger.dll'
if ($Deploy) {
	$plugins = Join-Path $env:APPDATA 'HearthstoneDeckTracker\Plugins'
	New-Item -ItemType Directory -Force $plugins | Out-Null
	Copy-Item $dll $plugins -Force
	Write-Host "Deployed to $plugins"
}
