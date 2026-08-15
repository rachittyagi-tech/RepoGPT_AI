@echo off
REM ============================================================
REM RepoGPT AI - Backend Quick Start
REM Double-click this file to install deps (if needed) and run
REM the FastAPI server. Keep this .bat file inside the "backend"
REM folder, next to main.py and requirements.txt.
REM ============================================================

echo Starting RepoGPT AI backend...
echo.

REM Install/update dependencies (safe to run every time)
pip install -r requirements.txt

echo.
echo ============================================================
echo Server starting at: http://127.0.0.1:8000
echo Swagger docs at:    http://127.0.0.1:8000/docs
echo Press CTRL+C to stop the server.
echo ============================================================
echo.

uvicorn main:app --reload --host 127.0.0.1 --port 8000

pause
