@echo off
rem Restarts only the DoseWISE backend (e.g. after backend\.env changes). The supervisor brings it
rem back within a few seconds; if the supervisor isn't running, this starts everything.
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
wscript.exe "%~dp0scripts\run-hidden.vbs"
echo Backend restarting... it will be back at http://localhost:8000/api/docs in about 10 seconds.
