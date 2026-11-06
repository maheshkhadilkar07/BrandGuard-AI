@echo off
echo ========================================================
echo Starting BrandGuard AI (Full Stack on http://localhost:8000)
echo ========================================================
start "" http://localhost:8000
cd /d "%~dp0backend"
".venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000
pause
