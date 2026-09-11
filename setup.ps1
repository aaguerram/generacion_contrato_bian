# Crea el entorno virtual e instala las últimas versiones (Windows PowerShell).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "→ venv..."
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\python.exe -m pip install -U -r requirements.txt
& .\.venv\Scripts\python.exe -m pip freeze | Out-File -Encoding utf8 requirements.lock.txt

if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "→ .env creado" -ForegroundColor Yellow }

Write-Host "`nListo. Ejemplos:" -ForegroundColor Green
Write-Host '  .\.venv\Scripts\python.exe -m src --service-domain "Current Account" --directorio .\salida\demo'
Write-Host '  .\.venv\Scripts\python.exe -m src --sd "Isued Device Admin" --dir .\salida\demo -v'
