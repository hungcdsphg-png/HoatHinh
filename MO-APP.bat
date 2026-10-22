@echo off
rem Mo HL Studio (cua so app, khong can trinh duyet)
cd /d "%~dp0"

rem Neu da dung file .exe (TAO-APP-EXE.bat) thi uu tien chay no
if exist "%~dp0bin\XuongVideoSanPham.exe" (
  start "" "%~dp0bin\XuongVideoSanPham.exe"
  exit /b 0
)

rem Tim Python (pythonw de khong hien cua so den): .venv rieng -> Video Bang Trang -> he thong
set "PYW="
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PYW=%~dp0.venv\Scripts\pythonw.exe"
if not defined PYW if exist "%~dp0..\video-bang-trang\.venv\Scripts\pythonw.exe" set "PYW=%~dp0..\video-bang-trang\.venv\Scripts\pythonw.exe"
if not defined PYW if exist "G:\video-bang-trang\.venv\Scripts\pythonw.exe" set "PYW=G:\video-bang-trang\.venv\Scripts\pythonw.exe"
if not defined PYW if exist "D:\video-bang-trang\.venv\Scripts\pythonw.exe" set "PYW=D:\video-bang-trang\.venv\Scripts\pythonw.exe"
if not defined PYW for %%P in (pythonw.exe) do if not "%%~$PATH:P"=="" set "PYW=%%~$PATH:P"

if not defined PYW (
  echo Chua cai dat. Hay chay CAI-DAT.bat mot lan truoc.
  pause
  exit /b 1
)
start "" "%PYW%" "%~dp0server.py"
exit /b 0
