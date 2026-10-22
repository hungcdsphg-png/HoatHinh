@echo off
rem Mo app kem cua so den de xem loi (dung khi app khong len)
cd /d "%~dp0"
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0..\video-bang-trang\.venv\Scripts\python.exe" set "PY=%~dp0..\video-bang-trang\.venv\Scripts\python.exe"
if not defined PY if exist "G:\video-bang-trang\.venv\Scripts\python.exe" set "PY=G:\video-bang-trang\.venv\Scripts\python.exe"
if not defined PY for %%P in (python.exe) do if not "%%~$PATH:P"=="" set "PY=%%~$PATH:P"
if not defined PY set "PY=python"
title HL Studio - cua so kiem tra
"%PY%" "%~dp0server.py"
pause
