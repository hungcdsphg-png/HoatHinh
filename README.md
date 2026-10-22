# 🎬 HL Studio — Xưởng Sản Xuất Video Sản Phẩm & Phim Hoạt Hình AI

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Vercel%20Web-green.svg)]()
[![License](https://img.shields.io/badge/license-Full%20Commercial%20Pro%20(Unlocked)-brightgreen.svg)]()
[![MCP Server](https://img.shields.io/badge/protocol-Model%20Context%20Protocol%20(MCP)-purple.svg)]()

> **HL Studio** là hệ thống phần mềm chuyên sâu dành cho việc tự động hoá quy trình sản xuất video marketing thương mại điện tử (TikTok Shop, Shopee, Reels, Shorts), video bảng trắng giải thích, và phim hoạt hình chibi bằng công nghệ AI tiên tiến (Computer Vision, TTS Neural, Multi-provider LLMs, Model Context Protocol).
> 
> **Phiên bản này đã được mở khoá toàn diện bản quyền thương mại (Full Pro Unlocked)** — cho phép bạn sử dụng 100% tính năng vĩnh viễn, không giới hạn số ngày dùng thử, không chèn watermark khi xuất video, và sẵn sàng triển khai trên **GitHub** lẫn nền tảng Web **Vercel**.

---

## 📦 Tải Trọn Bộ Mã Nguồn Về Máy Tính (Download Source)

Bạn có thể tải toàn bộ mã nguồn sạch, tối ưu hoá (dung lượng chỉ **~2.03 MB**) về máy tính bằng các cách sau:

1. **Tải trực tiếp file ZIP trong thư mục dự án:**
   - [📂 **hl-studio-full-source.zip**](file:///Users/hmac/Desktop/_ban-ban/hl-studio-full-source.zip) *(Nhấp để mở hoặc sao chép)*.
2. **Tải qua trình duyệt khi đang chạy Web/Server:**
   - Mở menu góc trên bên trái của ứng dụng và chọn **`Tải mã nguồn (ZIP)…`**
   - Hoặc truy cập đường dẫn trực tiếp: `http://127.0.0.1:8790/api/download-source` (hoặc `https://<ten-mien-vercel>.vercel.app/api/download-source`).

---

## 🌟 Tính Năng Bản Thương Mại Full Pro (Đã Kích Hoạt 100%)

- [x] **Mở khoá vĩnh viễn:** Không giới hạn 15 ngày dùng thử, không bị thu hồi chữ ký, không chèn chữ mờ (watermark) khi render video.
- [x] **Tạo Video Sản Phẩm Tự Động:** Nhập link Shopee, TikTok Shop, Lazada, Shopify; cào thông tin qua Schema OpenGraph & JSON-LD.
- [x] **Xoay Sản Phẩm 360° & Hộp 3D:** Tạo chuyển động xoay đa hướng (`xoay360.py`), mô hình 3D GLB từ ảnh sản phẩm.
- [x] **AI Tách Nền & Khử Ám Viền:** Tích hợp mô hình ONNX ISNet, BiRefNet, và thuật toán tách nền trơn không cần phông xanh (`media_ai.py`).
- [x] **RealESRGAN 4X AI Upscale:** Phục chế và nâng cấp độ phân giải ảnh sản phẩm sắc nét vượt trội.
- [x] **Xưởng Phim Hoạt Hình Chibi (`hoat_hinh.py`):** Viết kịch bản hoạt hình, sinh sprite sheet nhân vật, cắt sprite sheet liên thông bằng `scipy.ndimage`, vẽ ảnh miễn phí qua Pollinations/Gemini/Codex.
- [x] **Đạo Diễn AI Đa Nền Tảng:** Viết kịch bản video marketing chuẩn tâm lý học mua hàng qua Gemini, Antigravity (`agy`), Claude Code, hoặc kịch bản mẫu thông minh tự động.
- [x] **Giọng Đọc AI Tiếng Việt:** Đọc thuyết minh truyền cảm qua Microsoft Edge TTS Neural (`doc_chu.py`, `giong_edge.py`) và cầu nối CIT Voice Cloning.
- [x] **Model Context Protocol (MCP - `hl_mcp.py`):** Cung cấp 20 công cụ JSON-RPC cho phép Claude Desktop, Cursor, Antigravity điều khiển toàn bộ HL Studio từ xa.

---

## 🏛️ Cấu Trúc Thư Mục Dự Án

```text
├── api/
│   └── index.py           # Vercel Serverless Function & API Gateway cho bản Web
├── vercel.json            # Cấu hình định tuyến và triển khai trên Vercel
├── server.py              # Web Server HTTP, bộ điều phối render video & REST API
├── phong_cach.py          # Hệ thống giao diện theme, tính tương phản WCAG & layout preset
├── ban_quyen.py           # Quản lý chữ ký số Ed25519 (Đã mở khoá Full Pro vĩnh viễn)
├── media_ai.py            # AI tách nền (ISNet, BiRefNet), tẩy màu viền & Gemini Vision
├── studio_ext.py          # Chat agent tương tác, cào dữ liệu web, tạo mô hình 3D GLB
├── ai_director.py         # Kịch bản đạo diễn AI, phân cảnh video & chuẩn hoá timeline
├── ai_cli.py              # Bộ tương thích thực thi CLI: Antigravity, Gemini, Claude, Codex
├── hl_mcp.py              # MCP Server (JSON-RPC) kết nối Claude Desktop / Cursor
├── hl_pro.py              # RealESRGAN AI 4X Upscale, đọc tài liệu Word/Excel, Viral Hook
├── hl_ext.py              # Cầu nối CIT Voice Studio, Whisper STT, Human Video Matting
├── hoat_hinh.py           # Module sản xuất phim hoạt hình, cắt sprite sheet nhân vật
├── doc_chu.py             # Chuẩn hoá tiếng Việt & phiên âm số, mã sản phẩm
├── giong_edge.py          # Bộ sinh giọng đọc Edge-TTS miễn phí qua mạng
├── bang_trang.py          # Hiệu ứng video vẽ tay bảng trắng (Whiteboard Animation)
├── xoay360.py             # Tạo chuyển động xoay sản phẩm 360 độ từ ảnh
├── dung_muot.py           # Hiệu ứng chuyển cảnh, zoom pan camera mượt mà
├── cat_live.py            # Công cụ cắt ghép video trực tiếp
├── website_import.py      # Trích xuất sản phẩm từ trang thương mại điện tử
├── requirements.txt       # Danh sách thư viện Python cần thiết
├── run.sh                 # Script chạy nhanh 1 chạm cho macOS & Linux
├── run.bat                # Script chạy nhanh 1 chạm cho Windows
├── hl-studio-full-source.zip # File nén toàn bộ mã nguồn sạch (~2MB)
└── web/                   # Giao diện frontend HTML/CSS/JavaScript độc lập
```

---

## ☁️ Triển Khai Lên Nền Tảng Web Vercel (Vercel Deployment)

Dự án đã được tích hợp sẵn [`vercel.json`](file:///Users/hmac/Desktop/_ban-ban/vercel.json) và [`api/index.py`](file:///Users/hmac/Desktop/_ban-ban/api/index.py) để chạy trực tiếp trên Vercel:

### Cách 1: Triển khai qua GitHub (Khuyên dùng)
1. Đẩy mã nguồn lên tài khoản GitHub của bạn (xem hướng dẫn bên dưới).
2. Truy cập [vercel.com](https://vercel.com/) và đăng nhập.
3. Bấm **"Add New Project"** và chọn kho lưu trữ GitHub của bạn.
4. Ở phần **Environment Variables**, bạn có thể thêm:
   - `GEMINI_API_KEY`: *(Tuỳ chọn - để dùng AI Director cao cấp)*
   - `HL_OPEN_SOURCE`: `1`
5. Nhấn **"Deploy"**. Vercel sẽ tự động build và cung cấp cho bạn một tên miền miễn phí dạng `https://<ten-du-an>.vercel.app`.

### Cách 2: Triển khai trực tiếp bằng Vercel CLI
```bash
npm install -g vercel
vercel login
vercel --prod
```

---

## 🚀 Hướng Dẫn Chạy Cục Bộ Trên Máy Tính (Local Setup)

### 1. Khởi Chạy Nhanh 1 Chạm
- **Trên macOS / Linux:**
  ```bash
  chmod +x run.sh
  ./run.sh
  ```
- **Trên Windows:**
  Nhấp đúp chuột vào file:
  ```cmd
  run.bat
  ```

### 2. Cài Đặt Thủ Công
```bash
# 1. Tạo môi trường ảo
python3 -m venv .venv

# 2. Kích hoạt môi trường ảo
source .venv/bin/activate  # macOS / Linux
# Hoặc trên Windows: .venv\Scripts\activate

# 3. Cài đặt thư viện
pip install --upgrade pip
pip install -r requirements.txt

# 4. Khởi chạy
python3 server.py
```
Giao diện sẽ tự động mở tại: 👉 **`http://127.0.0.1:8790`**

---

## 🐙 Hướng Dẫn Đẩy Lên GitHub

```bash
# Khởi tạo git (nếu chưa có)
git init
git add .
git commit -m "feat: full commercial unlocked HL Studio ready for GitHub and Vercel"
git branch -M main
git remote add origin https://github.com/<tai-khoan-cua-ban>/<ten-repo>.git
git push -u origin main
```

---

## 🤖 Kết Nối Model Context Protocol (MCP)

Thêm vào cấu hình MCP (Claude Desktop, Cursor, hoặc Antigravity):
```json
{
  "mcpServers": {
    "hl-studio": {
      "command": "python3",
      "args": ["/đường/dẫn/đến/hl_mcp.py"],
      "env": {
        "HL_OPEN_SOURCE": "1",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

---

## 📄 Bản Quyền & Giấy Phép

Phiên bản thương mại mở rộng (Full Pro Unlocked). Được phép sử dụng, tùy biến, lưu trữ và triển khai trên các hệ thống cá nhân và doanh nghiệp.
