# -*- coding: utf-8 -*-
"""HL Studio — nhận cả THƯ MỤC video/ảnh trên máy (không phải tải lên qua trình duyệt, đọc thẳng file gốc).

- list_folder: liệt kê video + ảnh trong thư mục (có thể cả thư mục con), sắp theo tên tự nhiên (VID_2, VID_10…)
- import_path: đưa một file vào thư viện: video được chuyển mã H.264 ngay từ file gốc (không nạp cả file vào RAM)
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import media_ai

VIDEO_EXT = media_ai.VIDEO_EXT
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".jfif"}
NOWIN = media_ai.NOWIN


def _nat(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def list_folder(path: str, sub: bool = True) -> dict:
    p = Path((path or "").strip().strip('"'))
    if not p.is_dir():
        raise RuntimeError("Không thấy thư mục này")
    it = p.rglob("*") if sub else p.iterdir()
    vids, imgs = [], []
    for f in it:
        try:
            if not f.is_file() or f.name.startswith((".", "~$")):
                continue
            ext = f.suffix.lower()
            row = {"path": str(f), "name": f.name, "rel": str(f.relative_to(p)), "size": f.stat().st_size}
            if ext in VIDEO_EXT:
                vids.append(row)
            elif ext in IMAGE_EXT:
                imgs.append(row)
        except Exception:  # noqa: BLE001
            continue
        if len(vids) + len(imgs) > 400:
            break
    vids.sort(key=lambda r: (_nat(r["name"]), _nat(r["rel"])))
    imgs.sort(key=lambda r: (_nat(r["name"]), _nat(r["rel"])))
    return {"folder": str(p), "videos": vids, "images": imgs, "bytes": sum(r["size"] for r in vids + imgs)}


def _sha(f: Path) -> str:
    h = hashlib.sha1()
    with f.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def import_path(path: str, media_dir: Path, models_dir: Path, ffmpeg: str | None, log, cut: bool = True) -> dict:
    f = Path((path or "").strip().strip('"'))
    if not f.is_file():
        raise RuntimeError("Không thấy tệp " + f.name)
    ext = f.suffix.lower()
    if ext in IMAGE_EXT:
        return media_ai.save_media(f.read_bytes(), f.name, media_dir, models_dir, ffmpeg, log, cut)
    if ext not in VIDEO_EXT:
        raise RuntimeError("Không phải video/ảnh: " + f.name)
    if not ffmpeg:
        raise RuntimeError("Không có ffmpeg để đọc video")
    media_dir.mkdir(parents=True, exist_ok=True)
    h = _sha(f)
    import dung_muot  # giữ số hình/giây gốc + chống rung
    return {**dung_muot.prepare(ffmpeg, f, media_dir, h, log), "name": f.name, "src": str(f)}
