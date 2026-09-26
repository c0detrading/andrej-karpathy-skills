@echo off
rem Stops the background ONYX and removes it from Windows startup.
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ONYX.vbs" 2>nul
curl -s -o nul -X POST -H "Content-Type: application/json" -d "{}" http://localhost:8000/api/shutdown
echo ONYX autostart removed and the background server stopped.
pause
