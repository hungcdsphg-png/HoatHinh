@echo off
rem ============================================================
rem   HL STUDIO - CAI DAT 1 LAN (cho may moi / ban ban cho khach)
rem   Tu tim Python, tao moi truong rieng .venv, cai thu vien,
rem   tao bieu tuong ngoai Desktop. Chay lai nhieu lan khong sao.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
title HL Studio - Cai dat
echo.
echo ============================================
echo    HL STUDIO - DANG CAI DAT (1-5 phut)
echo ============================================
echo.

rem --- Phien ban Python can dung (khop voi goi da gop) ---
set "VER=3.12"
if exist "%~dp0python-version.txt" set /p VER=<"%~dp0python-version.txt"

rem --- 1) Tim dung Python %VER% ---
set "PY="
py -%VER% --version >nul 2>nul && set "PY=py -%VER%"
if not defined PY for %%P in (python.exe) do if not "%%~$PATH:P"=="" ( "%%~$PATH:P" --version 2>nul | findstr /c:"%VER%" >nul && set "PY=%%~$PATH:P" )

if not defined PY (
  echo Khong thay Python %VER%. Dang thu cai tu dong bang winget...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo   ^> May chua co winget. Hay tai Python %VER% tai https://www.python.org/downloads/
    echo     NHO TICH o "Add Python to PATH" khi cai, roi chay lai file nay.
    pause
    exit /b 1
  )
  winget install -e --id Python.Python.%VER% --accept-source-agreements --accept-package-agreements
  echo.
  echo   ^> Da cai Python %VER%. DONG cua so nay va chay lai CAI-DAT.bat mot lan nua.
  pause
  exit /b 0
)

echo [1/4] Dung Python: %PY%
%PY% --version

rem --- 2) Tao moi truong rieng .venv (de khong dung cham he thong) ---
echo [2/4] Tao moi truong rieng (.venv)...
if not exist "%~dp0.venv\Scripts\python.exe" (
  %PY% -m venv "%~dp0.venv"
)
set "VPY=%~dp0.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo   ^> Khong tao duoc .venv. Thu cai truc tiep...
  set "VPY=%PY%"
)

rem --- 3) Cai thu vien ---
echo [3/4] Cai thu vien can thiet...
"%VPY%" -m pip install --upgrade pip -q
set "LIBOK="
if exist "%~dp0thu-vien\*.whl" (
  echo   ^> Cai tu goi da gop san ^(khong can mang^)...
  "%VPY%" -m pip install -q --no-index --find-links "%~dp0thu-vien" -r "%~dp0requirements.txt" && set "LIBOK=1"
)
if not defined LIBOK (
  echo   ^> Cai thu vien tu mang...
  "%VPY%" -m pip install -q -r "%~dp0requirements.txt" && set "LIBOK=1"
)
if not defined LIBOK (
  echo.
  echo   ^> Cai thu vien LOI. Kiem tra mang roi chay lai. Neu van loi, chup man hinh gui nguoi ban.
  pause
  exit /b 1
)

rem --- 3b) Giong VieNeu (neu da gop san trong thu-vien) ---
if exist "%~dp0thu-vien\vieneu-*.whl" (
  echo   ^> Cai giong doc VieNeu ^(25 giong, da gop san^)...
  "%VPY%" -m pip install -q --no-index --find-links "%~dp0thu-vien" vieneu
  if errorlevel 1 (
    echo   ^> Chua cai duoc VieNeu offline, thu qua mang...
    "%VPY%" -m pip install -q vieneu
  )
)

rem --- 4) Kiem tra ffmpeg + tao bieu tuong ---
echo [4/4] Hoan tat...
if not exist "%~dp0ffmpeg.exe" if not exist "%~dp0bin\ffmpeg.exe" (
  echo   ^> Luu y: chua thay ffmpeg.exe. Chay CAI-FFMPEG.bat de tai ^(dung de xuat video^).
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\HL Studio.lnk');$s.TargetPath='%~dp0MO-APP.bat';$s.WorkingDirectory='%~dp0';$s.IconLocation='%~dp0web\favicon.png,0';$s.Description='HL Studio';$s.Save()" 2>nul

echo.
echo ============================================
echo    XONG! Bam dup bieu tuong "HL Studio" ngoai Desktop de mo.
echo    ^(Hoac chay MO-APP.bat trong thu muc nay^)
echo ============================================
echo.
echo Lan dau mo app: vao bieu tuong banh rang (Cai dat) ^> dan khoa AI cua ban.
echo Giong doc: co san 25 giong VieNeu (offline) + giong Edge mien phi (can mang).
echo.
set /p OPEN="Mo app luon bay gio? (g=co): "
if /i "%OPEN%"=="g" start "" "%~dp0MO-APP.bat"
exit /b 0
