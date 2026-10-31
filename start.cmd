@echo off
title Biomedical Health Intelligence Launcher
color 0A

echo ================================================================================
echo 🧬 BIOMEDICAL HEALTH INTELLIGENCE ^& CLINICAL RAG SYSTEM
echo ================================================================================
echo.
echo [1/2] 🚀 Launching Backend API (FastAPI with --reload on port 8001)...
start "Biomedical API (FastAPI :8001 [AUTO-RELOAD])" cmd /k "title Biomedical API (:8001) && cd /d "%~dp0" && python -m uvicorn querry:app --host 127.0.0.1 --port 8001 --reload"

echo [2/2] 🚀 Launching Frontend Dashboard (Angular with live-reload on port 4200)...
start "Biomedical Dashboard (Angular :4200 [LIVE-RELOAD])" cmd /k "title Biomedical Dashboard (:4200) && cd /d "%~dp0frontend" && npm start"

echo.
echo ================================================================================
echo 🎉 BOTH SERVICES ARE LAUNCHING WITH LIVE AUTO-RELOAD ENABLED!
echo ================================================================================
echo.
echo   🔗 Backend API:     http://127.0.0.1:8001
echo   📖 API Docs:        http://127.0.0.1:8001/docs
echo   💻 Angular App:     http://localhost:4200
echo.
echo Any changes you make to Python or Angular code will hot-reload automatically
echo without needing to restart the terminals.
echo ================================================================================
echo.

:: Wait 3 seconds and open the web dashboard in your default browser
timeout /t 3 /nobreak >nul
start http://localhost:4200
