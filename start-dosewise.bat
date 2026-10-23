@echo off
rem Starts DoseWISE (backend :8000 + frontend :5173) in the background; both restart if they stop.
rem A Windows scheduled task "DoseWISE servers" also runs this check at sign-in and every 5 minutes.
rem Logs: logs\backend.log and logs\frontend.log. To stop everything: stop-dosewise.bat
cd /d "%~dp0"
wscript.exe "%~dp0scripts\run-hidden.vbs"
echo DoseWISE is starting: website http://localhost:5173  -  API http://localhost:8000/api/docs
