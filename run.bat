@echo off
REM Music Finder - Windows launcher (creates the venv on first run)
cd /d "%~dp0"

if not exist ".venv" (
  echo [Music Finder] Creating virtual environment...
  python -m venv .venv || goto :error
  .venv\Scripts\python.exe -m pip install --upgrade pip -q
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt || goto :error
)

echo [Music Finder] http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto :eof

:error
echo [Music Finder] Install failed. Make sure Python 3.10+ is installed and on PATH.
pause
exit /b 1
