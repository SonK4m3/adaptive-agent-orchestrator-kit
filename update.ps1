param([switch]$CheckOnly, [switch]$Offline, [string]$StageDir)
$ErrorActionPreference = 'Stop'
$updateArgs = @()
if ($CheckOnly) { $updateArgs += '--check' }
if ($Offline) { $updateArgs += '--offline' }
if ($StageDir) { $updateArgs += @('--stage-dir', $StageDir) }
$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) { & py -3 (Join-Path $PSScriptRoot 'scripts/update.py') @updateArgs }
else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw 'Python 3.11+ is required.' }
    & python (Join-Path $PSScriptRoot 'scripts/update.py') @updateArgs
}
exit $LASTEXITCODE
