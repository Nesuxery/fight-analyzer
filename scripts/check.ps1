<#
.SYNOPSIS
  Run all project checks: backend tests, contract schema freshness, frontend
  type generation, typecheck, lint and production build.
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$VenvPy = Join-Path $Root '.venv\Scripts\python.exe'
$failed = @()

function Check([string]$Name, [string]$Dir, [string]$Exe, [string[]]$ArgList) {
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    Push-Location $Dir
    try { & $Exe @ArgList } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { $script:failed += $Name }
}

$backend = Join-Path $Root 'backend'
$frontend = Join-Path $Root 'frontend'
Check 'JSON Schema guncel mi' $backend $VenvPy @('-m', 'fight_analyzer.contracts.export', '--check')
Check 'Backend testleri' $backend $VenvPy @('-m', 'pytest', '-q')
Check 'TS tipleri guncel mi' $frontend 'npm' @('run', '--silent', 'check:types')
Check 'TypeScript' $frontend 'npm' @('run', '--silent', 'typecheck')
Check 'Lint' $frontend 'npm' @('run', '--silent', 'lint')
Check 'Frontend birim testleri' $frontend 'npm' @('run', '--silent', 'test')
Check 'Uretim derlemesi' $frontend 'npm' @('run', '--silent', 'build')

if ($failed.Count) {
    Write-Host "`nBASARISIZ: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "`nTum kontroller gecti." -ForegroundColor Green
