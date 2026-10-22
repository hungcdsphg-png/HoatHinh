@echo off
rem ============================================================
rem   HL STUDIO - CAI GIONG VIENEU (chat luong cao, offline)
rem   Giong tieng Viet tu nhien, 25 giong, chay CPU. ~vai tram MB.
rem   Chay 1 lan. Lan doc dau tien se tu tai mo hinh ve.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
title HL Studio - Cai giong VieNeu
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0..\video-bang-trang\.venv\Scripts\python.exe" set "PY=%~dp0..\video-bang-trang\.venv\Scripts\python.exe"
if not defined PY if exist "G:\video-bang-trang\.venv\Scripts\python.exe" set "PY=G:\video-bang-trang\.venv\Scripts\python.exe"
if not defined PY for %%P in (python.exe) do if not "%%~$PATH:P"=="" set "PY=%%~$PATH:P"
if not defined PY (
  echo Chua cai dat. Hay chay CAI-DAT.bat truoc.
  pause
  exit /b 1
)
echo Dang cai giong VieNeu (vai phut, can mang)...
"%PY%" -m pip install -U vieneu
if errorlevel 1 (
  echo.
  echo Cai LOI. Kiem tra mang roi chay lai. Trong luc do van dung duoc giong Edge.
  pause
  exit /b 1
)
echo.
echo XONG! Mo app, vao muc Giong doc se thay cac giong VieNeu.
echo Lan doc dau tien se tu tai mo hinh (vai phut), cac lan sau nhanh.
pause
