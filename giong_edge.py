# -*- coding: utf-8 -*-
"""
Giọng đọc Edge (miễn phí, cần mạng) — CHẠY ĐỘC LẬP, không cần Video Bảng Trắng.
Dùng gói edge-tts. Khi máy không có VieNeu / CIT, app vẫn đọc được bằng giọng này.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

VOICES = [
    ("vi-VN-HoaiMyNeural", "Hoài My (nữ)"),
    ("vi-VN-NamMinhNeural", "Nam Minh (nam)"),
]


def available() -> bool:
    try:
        import edge_tts  # type: ignore  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def synth(text: str, voice: str, out_mp3: Path, rate: str = "+0%", pitch: str = "+0Hz") -> Path:
    import edge_tts  # type: ignore
    voice = voice or "vi-VN-HoaiMyNeural"

    async def run():
        com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await com.save(str(out_mp3))

    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(run())
        loop.close()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Giọng Edge cần mạng Internet. Lỗi: {e}")
    if not out_mp3.exists() or out_mp3.stat().st_size < 400:
        raise RuntimeError("Giọng Edge không tạo được tiếng (kiểm tra mạng).")
    return out_mp3
