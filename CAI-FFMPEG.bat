@echo off
chcp 65001 >nul
rem Cai ffmpeg (cong cu ghep video) vao bo Python cua Video Bang Trang. Can mang Internet.
set PY=%~dp0..\video-bang-trang\.venv\Scripts\python.exe
if not exist "%PY%" (
  echo Khong thay Python cua Video Bang Trang tai %PY%
  echo Cach khac: tai ffmpeg tai https://www.gyan.dev/ffmpeg/builds/ ^(ban "essentials"^), giai nen, chep file ffmpeg.exe vao thu muc nay: %~dp0
  pause
  exit /b 1
)
echo Dang tai ffmpeg (khoang 30 MB)...
"%PY%" -m pip install --upgrade imageio-ffmpeg
if errorlevel 1 (
  echo Cai LOI. Chup man hinh nay gui Hoan Le.
  pause
  exit /b 1
)
"%PY%" -c "import imageio_ffmpeg,shutil,os; src=imageio_ffmpeg.get_ffmpeg_exe(); dst=os.path.join(r'%~dp0.','ffmpeg.exe'); shutil.copy(src,dst); print('Da chep ffmpeg vao', dst)"
echo.
echo XONG! Mo app len va bam Xuat video lai.
pause
