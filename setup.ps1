param([switch]$Offline)
$ErrorActionPreference = 'Stop'
$setupArgs = @()
if ($Offline) { $setupArgs += '--offline' }
$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) { & py -3 (Join-Path $PSScriptRoot 'scripts/setup.py') @setupArgs }
else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw 'Python 3.11+ is required. Install Python, then run .\setup.ps1 again.' }
    & python (Join-Path $PSScriptRoot 'scripts/setup.py') @setupArgs
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
