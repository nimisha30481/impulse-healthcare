@echo off
rem Starts the DoseWISE backend (:8000) and frontend (:5173) in their own minimised windows.
rem Each one restarts automatically if it stops. Close those windows to stop them.
cd /d "%~dp0"
start "DoseWISE backend" /min cmd /c "%~dp0scripts\keep-running.bat" backend
start "DoseWISE frontend" /min cmd /c "%~dp0scripts\keep-running.bat" frontend
