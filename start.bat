@echo off
REM One command to run the Proposal Creator on this machine.
cd /d "%~dp0"
if exist keys.env (
  for /f "usebackq tokens=1,* delims==" %%a in ("keys.env") do (
    if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
  )
  echo   Loaded keys.env
) else (
  echo   No keys.env found. Copy keys.env.example to keys.env and paste your key in.
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q --upgrade pip
pip install -q -r requirements.txt uvicorn
echo.
echo   Proposal Creator is running.
echo   Open  http://127.0.0.1:8000
echo   Stop with Ctrl+C
echo.
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
