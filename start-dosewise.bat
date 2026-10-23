@echo off
rem Starts DoseWISE (backend :8000 + frontend :5173) in one minimised window; both restart if they stop.
rem Runs at Windows login via the "DoseWISE servers" shortcut in the Startup folder. Close the window to stop.
cd /d "%~dp0"
start "DoseWISE servers" /min node "%~dp0scripts\dev.mjs" all
