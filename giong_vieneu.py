# -*- coding: utf-8 -*-
"""
Giọng đọc VieNeu-TTS (offline, CHẠY ĐỘC LẬP — không cần Video Bảng Trắng).
VieNeu-TTS v3 (Apache-2.0, github.com/pnnbao97/VieNeu-TTS) — 25 giọng tiếng Việt, chạy CPU bằng onnxruntime.
Gói 'vieneu' cài theo yêu cầu (CAI-GIONG-VIENEU.bat hoặc nút trong Cài đặt). Mô hình tự tải lần đầu (~vài trăm MB).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_engine = None
DEFAULT_VOICE = "Hải Đăng"


def _home() -> Path:
    try:
        import hl_ext
        return Path(hl_ext.CTX["HOME"])
    except Exception:  # noqa: BLE001
        return Path(os.environ.get("VSP_HOME") or (Path.home() / ".video-san-pham"))


def model_dir() -> Path:
    # bản bán: mô hình gộp sẵn cạnh app (models/huggingface); không có thì lưu ở thư mục dữ liệu
    app_md = Path(__file__).resolve().parent / "models" / "huggingface"
    if (app_md / "hub").is_dir() and any((app_md / "hub").glob("models--*")):
        return app_md
    return _home() / "models" / "huggingface"


def installed() -> bool:
    import importlib.util
    return importlib.util.find_spec("vieneu") is not None


def ready_flag() -> Path:
    return _home() / "vieneu_ready"


def ready() -> bool:
    return installed() and ready_flag().exists()


def voices() -> list[dict]:
    """25 giọng có sẵn (đọc từ gói vieneu, không cần tải mô hình)."""
    try:
        from importlib.resources import files
        d = json.loads((files("vieneu") / "assets" / "voices_v3_turbo.json").read_text(encoding="utf-8"))
        pre = d["presets"]
        names = sorted(pre, key=lambda k: (pre[k].get("featured") is None, pre[k].get("featured") or 0))
        return [{"id": n, "label": f"{'⭐ ' if pre[n].get('featured') else ''}{n}" + (f" — {pre[n].get('description', '')}" if pre[n].get('description') else "")} for n in names]
    except Exception:  # noqa: BLE001
        return [{"id": n, "label": n} for n in (
            "Hải Đăng", "Ngọc Huyền", "Mai Anh", "Thiện Minh", "Trúc Ly", "Thùy Dung", "Quang Sơn",
            "Ngọc Trân", "Minh Đức", "Phạm Tuyên", "Thái Sơn", "Minh Triết", "Mỹ Duyên", "Đức Trí", "Kim Thanh")]


def _get():
    global _engine
    if _engine is None:
        md = model_dir()
        md.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(md)
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from vieneu import Vieneu  # type: ignore
        try:
            import hl_ext
            hl_ext.log("[vieneu] đang nạp mô hình giọng (lần đầu tải về, vài phút)…")
        except Exception:  # noqa: BLE001
            pass
        _engine = Vieneu(precision=os.environ.get("VIENEU_PRECISION", "fp32"))
        ready_flag().write_text("ok", encoding="utf-8")
    return _engine


def synth(text: str, voice: str, out: Path) -> Path:
    eng = _get()
    try:
        audio = eng.infer(text, voice=voice or DEFAULT_VOICE)
    except Exception as e:  # noqa: BLE001
        if "voice" in str(e).lower() and voice != DEFAULT_VOICE:
            audio = eng.infer(text, voice=DEFAULT_VOICE)
        else:
            raise
    eng.save(audio, out)
    return out
