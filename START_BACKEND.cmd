@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
  echo Backend venv missing. Run: python -m venv backend\.venv
  echo Then run: backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  exit /b 1
)
set "WORKSPACE_MODEL_PROVIDER=nanbeige"
set "WORKSPACE_MODEL_TIMEOUT_SECONDS=180"
set "NANBEIGE_BASE_URL=http://127.0.0.1:8080/v1"
set "NANBEIGE_MODEL=nanbeige4.2-3b-local"
"backend\.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
endlocal
