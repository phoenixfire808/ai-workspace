@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
  echo Backend venv missing. Run: python -m venv backend\.venv
  echo Then run: backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  exit /b 1
)
set "WORKSPACE_MODEL_PROVIDER=ollama"
set "WORKSPACE_MODEL_TIMEOUT_SECONDS=180"
set "OLLAMA_BASE_URL=http://127.0.0.1:11434"
"backend\.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
endlocal
