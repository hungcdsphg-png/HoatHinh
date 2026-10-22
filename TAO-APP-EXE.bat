@echo off
rem Dung file XuongVideoSanPham.exe (cua so app co logo rieng). Chi can chay 1 lan.
chcp 65001 >nul
cd /d "%~dp0"
where dotnet >nul 2>nul
if errorlevel 1 (
  echo Khong thay .NET SDK tren may. Tai .NET SDK tai https://dotnet.microsoft.com/download roi chay lai file nay.
  echo Trong luc cho, van mo app duoc bang MO-APP.bat
  pause
  exit /b 1
)
echo Dang dung app, lan dau mat 1-2 phut (tai thu vien WebView2)...
dotnet publish "%~dp0launcher\XuongVideoSanPham.csproj" -c Release -r win-x64 --self-contained false -p:PublishSingleFile=false -o "%~dp0bin"
if errorlevel 1 (
  echo.
  echo Dung app LOI. Chup man hinh nay gui Hoan Le.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\HL Studio.lnk');$s.TargetPath='%~dp0bin\XuongVideoSanPham.exe';$s.WorkingDirectory='%~dp0bin';$s.IconLocation='%~dp0bin\XuongVideoSanPham.exe,0';$s.Description='HL Studio - Hoan Le';$s.Save()"
echo.
echo XONG! Bieu tuong "HL Studio" ngoai Desktop da tro sang file .exe moi.
echo Mo app len, chuot phai vao bieu tuong tren thanh tac vu ^> "Ghim vao thanh tac vu" neu muon.
start "" "%~dp0bin\XuongVideoSanPham.exe"
pause
