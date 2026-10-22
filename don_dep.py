# -*- coding: utf-8 -*-
"""HL Studio — TỰ DỌN BỘ NHỚ TẠM để ổ cứng không đầy dần.

App chỉ giữ file của video đang làm (dự án đang mở) và dự án anh bấm Lưu. Còn lại xoá:
- ảnh/video đã nhập cho các video cũ (không dự án nào còn dùng) — sau 1 giờ, tránh xoá nhầm lúc đang nhập
- bản video cũ đã được thay bằng bản mới chống rung (-v.mp4 / -p.mp4 cũ)
- file video gốc chép tạm khi kéo thả (đã chuyển mã xong)
- giọng đọc tạm quá 3 ngày
Video đã XUẤT nằm ở thư mục anh chọn, app không bao giờ đụng tới.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

HASH = re.compile(r"[0-9a-f]{16}")


def _size(p: Path) -> int:
    try:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except Exception:  # noqa: BLE001
        return 0


def usage(dirs: list) -> dict:
    tot = sum(_size(Path(d)) for d in dirs)
    return {"mb": round(tot / 1048576, 1)}


def cleanup(media_dir: Path, proj_dir: Path, tts_dir: Path, log, min_age: float = 3600) -> dict:
    now = time.time()
    texts = []
    for f in proj_dir.glob("*.json"):
        try:
            texts.append(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    blob = "\n".join(texts)
    keep = set(HASH.findall(blob))
    removed, freed = 0, 0

    def rm(f: Path):
        nonlocal removed, freed
        try:
            sz = f.stat().st_size
            f.unlink()
            removed += 1
            freed += sz
        except Exception:  # noqa: BLE001
            pass

    for f in list(media_dir.glob("*")) if media_dir.exists() else []:
        if not f.is_file():
            continue
        name = f.name
        if name.endswith((".part.mp4", ".trf")):
            if now - f.stat().st_mtime > 3600:
                rm(f)
            continue
        m = HASH.match(name)
        if not m:
            continue
        h = m.group(0)
        old = now - f.stat().st_mtime > min_age
        if h not in keep:
            if old:
                rm(f)
            continue
        # cùng video nhưng đã có bản mới hơn (-v2 chống rung, -v3 giữ chất lượng gốc): bỏ bản cũ nếu không dự án nào còn trỏ tới
        v3 = (media_dir / f"{h}-v3.mp4").exists()
        if v3 or (media_dir / f"{h}-v2.mp4").exists():
            stale = name in (f"{h}-v.mp4", f"{h}-p.mp4", f"{h}-a.m4a") or name.startswith(f"{h}-v-a16")
            if v3:
                stale = stale or name in (f"{h}-v2.mp4", f"{h}-v2.json", f"{h}2-p.mp4", f"{h}2-a.m4a", f"{h}2-p-mo.json")
            if stale and name not in blob:
                rm(f)
                continue
            # file gốc chép tạm lúc kéo thả (VD abc123.mp4) — đã có bản dựng, không cần nữa
            if re.fullmatch(h + r"\.(mp4|mov|m4v|avi|mkv|webm|3gp|wmv)", name, re.I) and old:
                rm(f)
    if tts_dir and tts_dir.exists():
        for f in tts_dir.glob("*"):
            try:
                if f.is_file() and now - f.stat().st_mtime > 3 * 86400:
                    rm(f)
            except Exception:  # noqa: BLE001
                pass
    if removed:
        log(f"[don-dep] xoá {removed} tệp tạm, giải phóng {freed / 1048576:.0f} MB")
    return {"removed": removed, "freed_mb": round(freed / 1048576, 1)}
