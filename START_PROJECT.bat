@echo off
TITLE HEATSENSE AI - One-Click Launcher
COLOR 0A
cls

echo ===============================================================================
echo              HEATSENSE AI - FULL SYSTEM STARTUP LAUNCHER
echo ===============================================================================
echo [1/4] Checking PostgreSQL database on port 5433...
powershell -Command "if (Get-NetTCPConnection -LocalPort 5433 -ErrorAction SilentlyContinue) { Write-Host '      [OK] PostgreSQL database is active on port 5433.' -ForegroundColor Green } else { Write-Host '      [WARNING] Port 5433 not active. Please ensure PostgreSQL is running.' -ForegroundColor Yellow }"

echo.
echo [2/4] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "HEATSENSE AI - FastAPI Backend (Port 8000)" cmd /k "cd /d %~dp0 && set PYTHONPATH=.;backend&& .venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload"

echo.
echo [3/4] Starting React + Vite Frontend on http://127.0.0.1:5173 ...
start "HEATSENSE AI - Vite Frontend (Port 5173)" cmd /k "cd /d %~dp0\frontend && npm run dev -- --host 127.0.0.1 --port 5173"

echo.
echo [4/4] Waiting 4 seconds for servers to initialize...
timeout /t 4 /nobreak >nul

echo.
echo ===============================================================================
echo              HEATSENSE AI IS NOW RUNNING!
echo ===============================================================================
echo   - Frontend UI:        http://127.0.0.1:5173
echo   - Backend Swagger:    http://127.0.0.1:8000/docs
echo   - Health Endpoint:    http://127.0.0.1:8000/api/v1/health
echo.
echo Test Planner Credentials:
echo   Username: planner_officer
echo   Password: (check .env / DEV_USER_PASSWORD)
echo.
echo Opening browser at http://127.0.0.1:5173 ...
start http://127.0.0.1:5173

echo ===============================================================================
echo Keep the two launched terminal windows open while using the application.
echo To stop, simply close the backend and frontend terminal windows.
echo ===============================================================================
pause

