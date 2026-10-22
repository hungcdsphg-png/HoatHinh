@echo off
rem Tao bieu tuong "Xuong Video San Pham" ngoai Desktop
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Xuong Video San Pham.lnk');$s.TargetPath='%~dp0MO-APP.bat';$s.WorkingDirectory='%~dp0';$s.IconLocation='%~dp0app.ico';$s.WindowStyle=7;$s.Description='Xuong Video San Pham';$s.Save()"
echo Da tao bieu tuong "Xuong Video San Pham" ngoai Desktop.
pause
