<#
.SYNOPSIS
  One-time (repeatable) setup: Python virtual environment with pinned packages
  and the frontend packages from package-lock.json.

.PARAMETER Torch
  auto  : CUDA build when an NVIDIA driver is found (>= 580 -> cu130,
          >= 560 -> cu126), otherwise CPU.
  cpu | cu130 | cu126 : force a PyTorch build.
#>
param(
    [ValidateSet('auto', 'cpu', 'cu130', 'cu126')]
    [string]$Torch = 'auto'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Req = Join-Path $Root 'backend\requirements'
$VenvPy = Join-Path $Root '.venv\Scripts\python.exe'

function Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }

function Invoke-Checked([string]$Exe, [string[]]$ArgList) {
    & $Exe @ArgList
    if ($LASTEXITCODE -ne 0) { throw "'$Exe $($ArgList -join ' ')' failed (exit $LASTEXITCODE)" }
}

Step 'Python 3.14'
$Py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $Py = & py -3.14 -c 'import sys; print(sys.executable)' 2>$null
    if ($LASTEXITCODE -ne 0) { $Py = $null }
}
if (-not $Py -and (Get-Command python -ErrorAction SilentlyContinue)) {
    # No quotes inside the code: PowerShell 5.1 and 7 pass them differently.
    $ver = & python -c 'import sys; print(*sys.version_info[:2], sep=chr(46))'
    if ($ver -eq '3.14') { $Py = & python -c 'import sys; print(sys.executable)' }
}
if (-not $Py) { throw 'Python 3.14 bulunamadi. https://www.python.org/downloads/ adresinden kurun.' }
Write-Host "Python: $Py"

Step 'Node.js'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js bulunamadi. https://nodejs.org adresinden LTS (>= 22.12) kurun.'
}
$nodeVer = [version]((& node --version).TrimStart('v'))
if ($nodeVer -lt [version]'22.12.0') { throw "Node.js $nodeVer cok eski; >= 22.12 gerekli." }
Write-Host "Node.js: $nodeVer"

Step 'Python sanal ortami (.venv)'
if (-not (Test-Path $VenvPy)) { Invoke-Checked $Py @('-m', 'venv', (Join-Path $Root '.venv')) }

if ($Torch -eq 'auto') {
    $Torch = 'cpu'
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $driver = & nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>$null |
            Select-Object -First 1
        if ($LASTEXITCODE -eq 0 -and $driver) {
            $major = [int]($driver.Trim().Split('.')[0])
            if ($major -ge 580) { $Torch = 'cu130' } elseif ($major -ge 560) { $Torch = 'cu126' }
            Write-Host "NVIDIA surucusu $driver bulundu."
        }
    }
}
Step "PyTorch ($Torch)"
Invoke-Checked $VenvPy @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', (Join-Path $Req "torch-$Torch.txt"))

Step 'Python paketleri (requirements/lock.txt)'
Invoke-Checked $VenvPy @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', (Join-Path $Req 'lock.txt'))
Invoke-Checked $VenvPy @('-m', 'pip', 'check')

Step 'Poz modeli (resmi Ultralytics surumu, SHA-256 dogrulamali)'
Push-Location (Join-Path $Root 'backend')
try { Invoke-Checked $VenvPy @('-m', 'fight_analyzer.pose.models') } finally { Pop-Location }

Step 'Scorebug OCR modeli (PaddleOCR PP-OCRv5, Apache-2.0, SHA-256 dogrulamali)'
Push-Location (Join-Path $Root 'backend')
try { Invoke-Checked $VenvPy @('-m', 'fight_analyzer.broadcast.ocr_model') } finally { Pop-Location }

Step 'Arayuz paketleri (npm ci)'
Push-Location (Join-Path $Root 'frontend')
try { Invoke-Checked 'npm' @('ci', '--no-audit') } finally { Pop-Location }

Write-Host "`nKurulum tamam. Baslatmak icin: start.cmd" -ForegroundColor Green
