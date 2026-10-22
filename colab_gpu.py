# -*- coding: utf-8 -*-
"""
GPU miễn phí qua Google Colab — cho máy không có card đồ hoạ.
HL Studio ghi "phiếu việc" (JSON) vào thư mục Google Drive (đồng bộ bằng Google Drive cho máy tính);
notebook HL_Studio_GPU.ipynb chạy trên Colab đọc phiếu, vẽ ảnh (Z-Image-Turbo, Apache-2.0) /
sáng tác nhạc (ACE-Step 1.5) rồi ghi kết quả về Drive; HL Studio thấy file về thì đưa vào video.

Cấu trúc thư mục:  <Drive>/HL-Studio-Colab/
    HL_Studio_GPU.ipynb      notebook (mở bằng Google Colab)
    viec/<id>.json           phiếu việc HL Studio gửi
    xong/<id>/...            kết quả + dang.txt (đang làm) / xong.json (xong) / loi.txt (lỗi)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import string
import time
from pathlib import Path

ROOT_NAME = "HL-Studio-Colab"
NB_NAME = "HL_Studio_GPU.ipynb"
APP_DIR = Path(__file__).resolve().parent
RATIOS = ("9:16", "1:1", "16:9", "4:5")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
AUD_EXT = (".mp3", ".wav", ".flac", ".m4a", ".ogg")


def _ctx():
    import hl_ext
    return hl_ext.CTX


def _cfg() -> dict:
    try:
        return _ctx()["load_cfg"]() or {}
    except Exception:  # noqa: BLE001
        return {}


def _detect() -> Path | None:
    """Tìm thư mục 'My Drive' của Google Drive cho máy tính (ổ ảo G:, H:… hoặc thư mục trong máy)."""
    cands = []
    if os.name == "nt":
        for L in string.ascii_uppercase[2:]:
            for sub in ("My Drive", "Drive của tôi"):
                cands.append(Path(f"{L}:/") / sub)
    home = Path.home()
    cands += [home / "Google Drive" / "My Drive", home / "Google Drive", home / "My Drive", home / "GoogleDrive"]
    for c in cands:
        try:
            if c.is_dir():
                return c
        except OSError:
            continue
    return None


def root() -> tuple[Path | None, bool]:
    """(thư mục HL-Studio-Colab, có phải tự dò không)."""
    p = (_cfg().get("colab_dir") or "").strip()
    if p:
        return Path(p), False
    d = _detect()
    return (d / ROOT_NAME if d else None), True


def set_dir(path: str) -> dict:
    path = (path or "").strip().strip('"')
    cfg = _cfg()
    if path:
        p = Path(path)
        if not p.exists():
            raise ValueError("Không thấy thư mục này trên máy.")
        if p.name != ROOT_NAME:
            p = p / ROOT_NAME
        cfg["colab_dir"] = str(p)
    else:
        cfg.pop("colab_dir", None)
    _ctx()["save_cfg"](cfg)
    return info()


def _prepare(r: Path) -> None:
    (r / "viec").mkdir(parents=True, exist_ok=True)
    (r / "xong").mkdir(parents=True, exist_ok=True)
    src = APP_DIR / "colab" / NB_NAME
    dst = r / NB_NAME
    if src.exists() and (not dst.exists() or dst.read_bytes() != src.read_bytes()):
        shutil.copyfile(src, dst)
    guide = r / "DOC-TRUOC.txt"
    if not guide.exists():
        guide.write_text(
            "HL Studio — Vẽ ảnh & sáng tác nhạc bằng GPU miễn phí (Google Colab)\n\n"
            "1. Mở drive.google.com → thư mục HL-Studio-Colab.\n"
            "2. Chuột phải HL_Studio_GPU.ipynb → Mở bằng → Google Colaboratory.\n"
            "3. Menu Thời gian chạy (Runtime) → Thay đổi loại thời gian chạy → chọn GPU T4 → Lưu.\n"
            "4. Bấm nút ▶ ở ô đầu tiên, cho phép truy cập Google Drive.\n"
            "5. Để tab Colab mở. Ảnh/nhạc làm xong tự về máy, HL Studio tự nhận.\n",
            encoding="utf-8")


def info() -> dict:
    r, auto = root()
    ok = bool(r and r.parent.is_dir())
    if ok:
        try:
            _prepare(r)
        except OSError as e:
            return {"dir": str(r), "auto": auto, "ok": False, "error": str(e), "jobs": []}
    return {"dir": str(r) if r else "", "auto": auto, "ok": ok, "notebook": str(r / NB_NAME) if ok else "",
            "jobs": jobs() if ok else []}


def _need_root() -> Path:
    r, _ = root()
    if not r or not r.parent.is_dir():
        raise ValueError("Chưa thấy thư mục Google Drive trên máy. Cài 'Google Drive cho máy tính' hoặc chọn thư mục Drive trong bảng Colab.")
    _prepare(r)
    return r


def submit(d: dict) -> dict:
    r = _need_root()
    kind = d.get("loai")
    jid = time.strftime("%m%d-%H%M%S") + "-" + os.urandom(2).hex()
    if kind == "anh":
        ds = []
        for it in d.get("ds") or []:
            p = str(it.get("prompt") if isinstance(it, dict) else it).strip()
            if p:
                ds.append({"prompt": p[:1500], "so": max(1, min(4, int((it.get("so") if isinstance(it, dict) else 1) or 1)))})
        if not ds:
            raise ValueError("Nhập ít nhất 1 mô tả ảnh.")
        if len(ds) > 30:
            raise ValueError("Tối đa 30 mô tả mỗi lần.")
        job = {"id": jid, "loai": "anh", "ds": ds, "tile": d.get("tile") if d.get("tile") in RATIOS else "9:16"}
    elif kind == "nhac":
        style = str(d.get("phong_cach") or "").strip()
        if not style:
            raise ValueError("Nhập phong cách nhạc (VD: nhạc nền vui tươi, guitar, pop).")
        job = {"id": jid, "loai": "nhac", "phong_cach": style[:800], "loi": str(d.get("loi") or "").strip()[:3000],
               "giay": max(10, min(240, int(d.get("giay") or 60))), "bpm": max(60, min(180, int(d.get("bpm") or 100))),
               "ngon_ngu": d.get("ngon_ngu") or "vi", "so": max(1, min(4, int(d.get("so") or 2)))}
    elif kind == "studio":
        import hl_ext
        urls = [u for u in (d.get("anh") or []) if u][:6]
        if not urls:
            raise ValueError("Chọn ít nhất 1 ảnh sản phẩm (đã tách nền).")
        scene = str(d.get("boi_canh") or "").strip()
        if not scene:
            raise ValueError("Chọn hoặc gõ bối cảnh muốn đặt sản phẩm vào.")
        files = []
        for k, u in enumerate(urls, 1):
            f = hl_ext._media_file(u)
            if not f or not f.exists():
                raise ValueError("Không thấy ảnh sản phẩm trong thư viện.")
            dst = r / "viec" / f"{jid}_sp{k}.png"
            from PIL import Image  # type: ignore
            im = Image.open(f)
            if im.mode != "RGBA":
                im = im.convert("RGBA")
            im.thumbnail((1600, 1600))
            im.save(dst)
            files.append(dst.name)
        job = {"id": jid, "loai": "studio", "sp": files, "boi_canh": scene[:800], "them": str(d.get("them") or "")[:300],
               "so": max(1, min(4, int(d.get("so") or 2))), "tile": d.get("tile") if d.get("tile") in RATIOS else "9:16"}
    else:
        raise ValueError("Loại việc không đúng.")
    job["tao_luc"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = r / "viec" / (jid + ".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(r / "viec" / (jid + ".json"))
    return {"id": jid, "job": job}


def jobs() -> list[dict]:
    r, _ = root()
    if not r or not (r / "viec").is_dir():
        return []
    out = []
    for f in sorted((r / "viec").glob("*.json"), reverse=True)[:40]:
        try:
            job = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        x = r / "xong" / f.stem
        files = []
        if x.is_dir():
            files = sorted(p.name for p in x.iterdir() if p.suffix.lower() in IMG_EXT + AUD_EXT)
        st = "cho"
        if (x / "loi.txt").exists():
            st = "loi"
        elif (x / "xong.json").exists():
            st = "xong"
        elif (x / "dang.txt").exists() or files:
            st = "dang"
        out.append({"id": f.stem, "loai": job.get("loai"), "tom_tat": _summary(job), "tao_luc": job.get("tao_luc", ""),
                    "status": st, "files": files, "nhan": (x / "da-nhan.txt").exists(),
                    "loi": (x / "loi.txt").read_text(encoding="utf-8", errors="ignore")[-400:] if st == "loi" else "",
                    "tien_do": (x / "dang.txt").read_text(encoding="utf-8", errors="ignore")[-200:] if st == "dang" and (x / "dang.txt").exists() else ""})
    return out


def _summary(job: dict) -> str:
    if job.get("loai") == "studio":
        return f"{len(job.get('sp', [])) * job.get('so', 1)} ảnh studio {job.get('tile', '')} · " + job.get("boi_canh", "")[:60]
    if job.get("loai") == "nghe":
        return "Nghe lời thoại: " + job.get("nguon", "")[:60]
    if job.get("loai") == "anh":
        n = sum(i.get("so", 1) for i in job.get("ds", []))
        return f"{n} ảnh {job.get('tile', '')} · " + (job.get("ds") or [{}])[0].get("prompt", "")[:60]
    return f"{job.get('so', 1)} bản nhạc {job.get('giay', 60)}s · " + job.get("phong_cach", "")[:60]


def _safe(jid: str) -> str:
    if not re.fullmatch(r"[0-9A-Za-z._-]{4,40}", jid or ""):
        raise ValueError("Mã việc không đúng")
    return jid


def file_path(jid: str, name: str) -> Path:
    r = _need_root()
    f = (r / "xong" / _safe(jid) / Path(name).name)
    if not f.is_file():
        raise FileNotFoundError(name)
    return f


def mark(jid: str) -> dict:
    r = _need_root()
    x = r / "xong" / _safe(jid)
    if x.is_dir():
        (x / "da-nhan.txt").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return {"id": jid}


def cancel(jid: str) -> dict:
    """Huỷ phiếu chưa làm (đổi đuôi để notebook bỏ qua)."""
    r = _need_root()
    f = r / "viec" / (_safe(jid) + ".json")
    if f.exists():
        f.replace(f.with_suffix(".huy"))
    return {"id": jid}


def open_drive() -> dict:
    import webbrowser
    webbrowser.open("https://drive.google.com/drive/my-drive")
    return {}
