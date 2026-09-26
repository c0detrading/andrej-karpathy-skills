@echo off
rem Starts ONYX hidden in the background now and every time you log in to Windows.
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
set PYW=pythonw
where pythonw >nul 2>nul || set PYW=pyw
echo Installing/updating requirements...
%PY% -m pip install -q -r requirements.txt
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
(
echo Set sh = CreateObject("WScript.Shell"^)
echo sh.CurrentDirectory = "%~dp0"
echo sh.Run "%PYW% -m station", 0, False
) > "%STARTUP%\ONYX.vbs"
curl -s -o nul http://localhost:8000/login || wscript "%STARTUP%\ONYX.vbs"
echo.
echo ONYX now runs in the background and starts automatically when you log in.
echo Open it any time at http://localhost:8000 (or with the Start ONYX shortcut).
echo Log file: %~dp0data\onyx.log
timeout /t 6 >nul
start "" http://localhost:8000
pause
