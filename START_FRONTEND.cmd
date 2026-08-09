@echo off
setlocal
cd /d "%~dp0frontend"
if not exist "node_modules" (
  echo Frontend dependencies missing. Run: npm install
  exit /b 1
)
call npm run dev -- --hostname 127.0.0.1 --port 3000
endlocal
