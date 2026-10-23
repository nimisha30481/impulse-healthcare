@echo off
rem Usage: keep-running.bat backend|frontend  -- restarts the server whenever it exits.
set ROOT=%~dp0..
:loop
rem Skip starting if something is already serving the port (e.g. a Claude preview server).
if "%1"=="backend" (
  netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul || "%ROOT%\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "%ROOT%\backend" --host 127.0.0.1 --port 8000
) else (
  netstat -ano | findstr /r /c:":5173 .*LISTENING" >nul || npm --prefix "%ROOT%\frontend" run dev
)
timeout /t 10 /nobreak >nul
goto loop
