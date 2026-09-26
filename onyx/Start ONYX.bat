@echo off
title ONYX
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
echo Installing/updating requirements...
%PY% -m pip install -q -r requirements.txt
echo Starting ONYX - keep this window open. Close it to stop.
start "" cmd /c "timeout /t 5 >nul & start http://localhost:8000"
%PY% -m uvicorn station.app:app --port 8000
pause
