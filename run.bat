@echo off
chcp 65001 >nul
title HL Studio - Xưởng Video Sản Phẩm

echo ==================================================
echo     HL STUDIO - XƯỞNG SẢN XUẤT VIDEO SẢN PHẨM
echo ==================================================

cd /d "%~dp0"

set "HL_OPEN_SOURCE=1"

rem 1. Kiểm tra Python
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=py -3"
    goto :found_python
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
    goto :found_python
)

echo [!] Không tìm thấy Python trên máy.
echo     Vui lòng cài đặt Python 3.10+ từ https://www.python.org/ (nhớ tích chọn 'Add Python to PATH')
pause
exit /b 1

:found_python
echo [*] Phát hiện Python:
%PY_CMD% --version

rem 2. Tạo .venv nếu chưa có
if not exist ".venv\Scripts\python.exe" (
    echo [*] Đang khởi tạo môi trường ảo .venv...
    %PY_CMD% -m venv .venv
)

rem 3. Kích hoạt .venv
call .venv\Scripts\activate.bat

rem 4. Cài đặt thư viện
if exist "requirements-full.txt" (
    echo [*] Đang kiểm tra thư viện đầy đủ từ requirements-full.txt...
    python -m pip install -r requirements-full.txt -q
) else if exist "requirements.txt" (
    echo [*] Đang kiểm tra thư viện từ requirements.txt...
    python -m pip install -r requirements.txt -q
)

rem 5. Khởi chạy server
echo ==================================================
echo [*] Đang mở ứng dụng HL Studio...
echo     Trình duyệt sẽ tự động mở giao diện tại: http://127.0.0.1:8765
echo ==================================================

python server.py %*

if %ERRORLEVEL% neq 0 (
    echo [!] Server dừng với mã lỗi: %ERRORLEVEL%
    pause
)
