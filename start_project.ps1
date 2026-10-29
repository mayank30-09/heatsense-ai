<#
.SYNOPSIS
    HEATSENSE AI - PowerShell Full Stack Launcher
.DESCRIPTION
    Checks database connectivity on port 5433, starts FastAPI backend and Vite frontend
    in independent processes, and launches the browser.
#>

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "             HEATSENSE AI - FULL SYSTEM STARTUP LAUNCHER (PowerShell)" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan

$root = $PSScriptRoot
Set-Location $root

# 1. Check PostgreSQL on port 5433
Write-Host "`n[1/4] Checking PostgreSQL database on port 5433..." -ForegroundColor White
$pg = Get-NetTCPConnection -LocalPort 5433 -ErrorAction SilentlyContinue
if ($pg) {
    Write-Host "      [OK] PostgreSQL is active on port 5433." -ForegroundColor Green
} else {
    Write-Host "      [WARNING] Port 5433 is not listening. Ensure PostgreSQL / PostGIS container or service is started." -ForegroundColor Yellow
}

# 2. Start FastAPI Backend in new window
Write-Host "`n[2/4] Starting FastAPI Backend on http://127.0.0.1:8000 ..." -ForegroundColor White
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='.;backend'; Set-Location '$root'; Write-Host '--- HEATSENSE AI BACKEND (Port 8000) ---' -ForegroundColor Cyan; .venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload"

# 3. Start React + Vite Frontend in new window
Write-Host "`n[3/4] Starting React + Vite Frontend on http://127.0.0.1:5173 ..." -ForegroundColor White
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; Write-Host '--- HEATSENSE AI FRONTEND (Port 5173) ---' -ForegroundColor Green; npm run dev -- --host 127.0.0.1 --port 5173"

# 4. Wait and launch browser
Write-Host "`n[4/4] Waiting 4 seconds for services to initialize..." -ForegroundColor White
Start-Sleep -Seconds 4

Write-Host "`n===============================================================================" -ForegroundColor Cyan
Write-Host "             HEATSENSE AI IS NOW RUNNING!" -ForegroundColor Green
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "  - Frontend UI:        http://127.0.0.1:5173" -ForegroundColor White
Write-Host "  - Backend Swagger:    http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  - Health Endpoint:    http://127.0.0.1:8000/api/v1/health" -ForegroundColor White
Write-Host "`nOpening browser at http://127.0.0.1:5173 ..." -ForegroundColor White

Start-Process "http://127.0.0.1:5173"

