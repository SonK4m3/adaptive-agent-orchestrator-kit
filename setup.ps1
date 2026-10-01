$ErrorActionPreference = 'Stop'
$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) { & py -3 (Join-Path $PSScriptRoot 'scripts/setup.py') }
else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw 'Python 3.11+ is required. Install Python, then run .\setup.ps1 again.' }
    & python (Join-Path $PSScriptRoot 'scripts/setup.py')
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
