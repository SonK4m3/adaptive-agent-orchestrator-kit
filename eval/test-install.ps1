param([Parameter(Mandatory=$true)][string]$ScratchRoot)
$ErrorActionPreference = 'Stop'
$kit = Split-Path $PSScriptRoot -Parent
$ScratchRoot = [IO.Path]::GetFullPath($ScratchRoot)
if (Test-Path -LiteralPath $ScratchRoot) { throw 'Use a new scratch directory' }
$skills = Join-Path $ScratchRoot 'skills'
$backups = Join-Path $ScratchRoot 'backups'
$installed = Join-Path $skills 'adaptive-agent-orchestrator'
& "$kit/install.ps1" -SkillsRoot $skills -BackupRoot $backups
New-Item -ItemType File -Path (Join-Path $installed 'obsolete.txt') -Value 'old-version sentinel' | Out-Null
$output = @(& "$kit/install.ps1" -SkillsRoot $skills -BackupRoot $backups)
$backup = ($output | Where-Object { $_ -like 'Backup: *' }).Substring(8)
if (Test-Path -LiteralPath (Join-Path $installed 'obsolete.txt')) { throw 'Stale file survived upgrade' }
if (-not (Test-Path -LiteralPath (Join-Path $backup 'obsolete.txt'))) { throw 'Backup incomplete' }
# Exact generated paths; preserve both versions and exercise documented rollback.
$savedCurrent = Join-Path $ScratchRoot 'saved-current'
Move-Item -LiteralPath $installed -Destination $savedCurrent
Move-Item -LiteralPath $backup -Destination $installed
if (-not (Test-Path -LiteralPath (Join-Path $installed 'obsolete.txt'))) { throw 'Rollback failed' }
$rejected = 0
try { & "$kit/install.ps1" -SkillsRoot $kit -BackupRoot $backups } catch { $rejected++ }
try { & "$kit/install.ps1" -SkillsRoot $skills -BackupRoot (Join-Path $installed 'nested-backup') } catch { $rejected++ }
if ($rejected -ne 2) { throw 'Overlap guards failed' }
& "$kit/install-roles.ps1" -AgentsRoot (Join-Path $ScratchRoot 'agents')
& "$kit/install-roles.ps1" -AgentsRoot (Join-Path $ScratchRoot 'agents')
Write-Output 'PASS: fresh install, stale-file upgrade, complete backup, rollback, source/backup overlap rejection, role reinstall'
