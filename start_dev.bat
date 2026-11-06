@echo off
echo ========================================================
echo Starting BrandGuard AI in Development Mode
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo ========================================================
start "BrandGuard Backend" cmd /k "cd /d ""%~dp0backend"" && "".venv\Scripts\python.exe"" -m uvicorn app.main:app --reload --port 8000"
start "BrandGuard Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
ping 127.0.0.1 -n 4 >nul
start "" http://localhost:5173
