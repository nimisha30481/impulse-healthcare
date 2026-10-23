@echo off
rem Stops the DoseWISE dev servers until the next sign-in (or the next 5-minute watchdog check).
rem To turn the watchdog off for good:  schtasks /Delete /TN "DoseWISE servers" /F
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { $_.CommandLine -match 'dev.mjs' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; foreach ($p in 8000,5173) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
echo DoseWISE servers stopped.
