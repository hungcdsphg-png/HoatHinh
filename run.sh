#!/usr/bin/env bash
# ==============================================================================
# HL Studio - Script khởi động nhanh trên macOS / Linux
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=================================================="
echo "    HL STUDIO - XƯỞNG SẢN XUẤT VIDEO SẢN PHẨM"
echo "=================================================="

# 1. Kiểm tra Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[!] Không tìm thấy Python 3 trên hệ thống."
    echo "    Vui lòng cài đặt Python 3.10+ (ví dụ: brew install python trên macOS hoặc apt install python3 trên Ubuntu)"
    exit 1
fi

echo "[*] Dùng Python: $($PYTHON_CMD --version)"

# 2. Tạo môi trường ảo .venv nếu chưa có
if [ ! -d ".venv" ]; then
    echo "[*] Đang khởi tạo môi trường ảo Python (.venv)..."
    $PYTHON_CMD -m venv .venv
fi

# 3. Kích hoạt môi trường ảo
source .venv/bin/activate

# 4. Cài đặt / cập nhật thư viện
if [ -f "requirements-full.txt" ]; then
    echo "[*] Đang kiểm tra thư viện đầy đủ (requirements-full.txt)..."
    python -m pip install --upgrade pip -q
    python -m pip install -r requirements-full.txt -q
elif [ -f "requirements.txt" ]; then
    echo "[*] Đang kiểm tra thư viện (requirements.txt)..."
    python -m pip install --upgrade pip -q
    python -m pip install -r requirements.txt -q
fi

# 5. Mở khoá mã nguồn mở (không giới hạn bản quyền)
export HL_OPEN_SOURCE=1

echo "=================================================="
echo "[*] Đang khởi chạy máy chủ HL Studio..."
echo "    Truy cập giao diện tại: http://127.0.0.1:8765"
echo "    Bấm Ctrl+C để dừng."
echo "=================================================="

# 6. Khởi động server
python server.py "$@"
