param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\").Path
)

$venvPath = Join-Path $ProjectRoot ".venv"
$pythonExecutable = Join-Path $venvPath "Scripts\python.exe"
$sentinelPath = Join-Path $venvPath ".editable_installed"

if (-not (Test-Path $pythonExecutable)) {
    Write-Error "Virtual environment python executable not found at $pythonExecutable"
    exit 1
}

if (Test-Path $sentinelPath) {
    Write-Host "Editable install already present; skipping." -ForegroundColor Yellow
    exit 0
}

Push-Location $ProjectRoot
try {
    Write-Host "Ensuring editable install for tia-tags-exporter..." -ForegroundColor Cyan
    & $pythonExecutable -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        throw "pip install -e . failed with exit code $LASTEXITCODE"
    }
    New-Item -ItemType File -Path $sentinelPath -Force | Out-Null
    Write-Host "Editable install completed." -ForegroundColor Green
}
finally {
    Pop-Location
}
