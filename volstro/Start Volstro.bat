@echo off
title Volstro Pipeline
cd /d "%~dp0"
rem Already running? Just open it.
curl -s -o nul http://localhost:8100/login && (start "" http://localhost:8100 & exit /b)
set PY=python
where python >nul 2>nul || set PY=py
echo Installing/updating requirements...
%PY% -m pip install -q -r requirements.txt
echo Starting Volstro - keep this window open. Close it to stop.
start "" cmd /c "timeout /t 5 >nul & start http://localhost:8100"
%PY% -m pipeline
pause
