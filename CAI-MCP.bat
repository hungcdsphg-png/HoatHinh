@echo off
rem Cai may chu MCP "hl-studio" cho Claude Desktop, Claude Code, Antigravity/Gemini, Codex, Cursor
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
if exist "%~dp0..\video-bang-trang\.venv\Scripts\python.exe" set "PY=%~dp0..\video-bang-trang\.venv\Scripts\python.exe"
if not defined PY if exist "G:\video-bang-trang\.venv\Scripts\python.exe" set "PY=G:\video-bang-trang\.venv\Scripts\python.exe"
if not defined PY if exist "D:\video-bang-trang\.venv\Scripts\python.exe" set "PY=D:\video-bang-trang\.venv\Scripts\python.exe"
if not defined PY if exist "C:\video-bang-trang\.venv\Scripts\python.exe" set "PY=C:\video-bang-trang\.venv\Scripts\python.exe"
if not defined PY for %%P in (python.exe) do if not "%%~$PATH:P"=="" set "PY=%%~$PATH:P"
if not defined PY (
  echo Khong tim thay Python. Hay cai Video Bang Trang truoc.
  pause
  exit /b 1
)
"%PY%" "%~dp0cai_mcp.py"
echo.
pause
