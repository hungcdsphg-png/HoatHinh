# -*- coding: utf-8 -*-
"""HL Studio — chuẩn bị video cho dựng MƯỢT.

- Giữ đúng số khung hình/giây của video gốc (tối đa 60), không ép về 30 → quay chậm từ video 60 hình/giây vẫn mượt.
- Chống rung: vidstab 2 lượt (nếu ffmpeg có), không có thì deshake. Lỗi thì chuyển mã thường, không bao giờ làm hỏng việc nhập.
- Khung khoá 1 giây/lần → tua nhanh khi xuất.
- Đo mức chuyển động từng 0,25 giây (để AI cắt đúng lúc động tác vừa xong, và biết clip nào đã rung/lia sẵn).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import media_ai

NOWIN = media_ai.NOWIN
_FILTERS: dict = {}
OPTS = {"stab": False}  # chống rung khi nhập: mặc định TẮT để giữ nguyên độ nét gốc (bật trong Cài đặt)
SCALE = "scale='if(gt(iw,ih),min(1920,iw),-2)':'if(gt(iw,ih),-2,min(1920,ih))'"


def has_filter(ffmpeg: str, name: str) -> bool:
    if ffmpeg not in _FILTERS:
        try:
            r = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, timeout=20, creationflags=NOWIN)
            _FILTERS[ffmpeg] = r.stdout.decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            _FILTERS[ffmpeg] = ""
    return re.search(r"\s" + re.escape(name) + r"\s", _FILTERS[ffmpeg]) is not None


def src_fps(ffmpeg: str, f: Path) -> float:
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(f)], capture_output=True, creationflags=NOWIN)
    s = r.stderr.decode("utf-8", "ignore")
    m = re.search(r"Video:.*?([\d.]+) fps", s) or re.search(r"Video:.*?([\d.]+) tbr", s)
    try:
        return float(m.group(1)) if m else 30.0
    except ValueError:
        return 30.0


def _info(ffmpeg: str, f: Path) -> dict:
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(f)], capture_output=True, creationflags=NOWIN)
    s = r.stderr.decode("utf-8", "ignore")
    v = re.search(r"Video: (\w+).*?, (yuvj?420p)[^,]*,.*?(\d{2,5})x(\d{2,5})", s)
    a = re.search(r"Audio: (\w+)", s)
    return {"vc": v.group(1) if v else "", "pix": v.group(2) if v else "", "w": int(v.group(3)) if v else 0, "h": int(v.group(4)) if v else 0,
            "ac": a.group(1) if a else ""}


def transcode(ffmpeg: str, src: Path, out: Path, log, stab: bool | None = None) -> dict:
    """Chuẩn bị video để dựng mà GIỮ NGUYÊN CHẤT LƯỢNG GỐC:
    - video H.264 thường (điện thoại, tải về): chép nguyên luồng hình, không nén lại → bằng đúng file gốc
    - định dạng khác / 4K / >60 hình/giây: nén lại gần như không mất (crf 14)
    - chống rung chỉ khi anh bật trong Cài đặt (chống rung phải nội suy lại hình nên mềm hơn gốc)"""
    stab = OPTS.get("stab", False) if stab is None else stab
    fps = src_fps(ffmpeg, src)
    rate = "" if fps <= 61 else ",fps=60"
    work = out.parent
    tmp = out.with_suffix(".part.mp4")
    inf = _info(ffmpeg, src)
    aud = ["-c:a", "copy"] if inf["ac"] == "aac" else ["-c:a", "aac", "-b:a", "256k", "-ac", "2", "-ar", "48000"]
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "14", "-g", str(int(round(min(fps, 60)))), "-pix_fmt", "yuv420p",
           *aud, "-movflags", "+faststart"]
    if not stab and inf["vc"] == "h264" and inf["pix"] == "yuv420p" and fps <= 61 and max(inf["w"], inf["h"]) <= 1920:
        try:
            media_ai.STATE["msg"] = f"Đang nhập {src.name} (giữ nguyên chất lượng gốc)…"
            r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "copy", *aud,
                                "-movflags", "+faststart", str(tmp)], capture_output=True, creationflags=NOWIN)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.decode("utf-8", "ignore")[-200:])
            tmp.replace(out)
            log(f"[muot] {src.name}: chép nguyên hình gốc ({inf['w']}x{inf['h']}, {fps:g} hình/giây)")
            return {"fps": round(fps, 2), "stab": "", "goc": 1}
        except Exception as e:  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            log(f"[muot] chép nguyên lỗi, nén lại: {e}")
        finally:
            media_ai.STATE["msg"] = ""
    tries = []
    if stab and has_filter(ffmpeg, "vidstabdetect") and has_filter(ffmpeg, "vidstabtransform"):
        tries.append("vidstab")
    if stab and has_filter(ffmpeg, "deshake"):
        tries.append("deshake")
    tries.append("")
    trf = out.with_suffix(".trf")
    for how in tries:
        try:
            if how == "vidstab":
                media_ai.STATE["msg"] = f"Đang đo độ rung {src.name}…"
                # chạy trong thư mục media, tên tệp tương đối (đường dẫn Windows có "C:" làm hỏng cú pháp bộ lọc)
                r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-vf", f"{SCALE}{rate},vidstabdetect=shakiness=6:accuracy=9:result={trf.name}",
                                    "-f", "null", "-"], capture_output=True, cwd=str(work), creationflags=NOWIN)
                if r.returncode != 0 or not trf.exists():
                    raise RuntimeError(r.stderr.decode("utf-8", "ignore")[-200:])
                vf = f"{SCALE}{rate},vidstabtransform=input={trf.name}:smoothing=10:optzoom=1:maxshift=36:maxangle=0.03:interpol=bicubic"
            elif how == "deshake":
                vf = f"{SCALE}{rate},deshake=rx=32:ry=32:edge=mirror"
            else:
                vf = f"{SCALE}{rate}"
            media_ai.STATE["msg"] = (f"Đang chống rung {src.name}…" if how else f"Đang chuẩn bị video {src.name}…")
            r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf, *enc, str(tmp)], capture_output=True, cwd=str(work), creationflags=NOWIN)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.decode("utf-8", "ignore")[-200:])
            tmp.replace(out)
            log(f"[muot] {src.name}: {fps:g} hình/giây, chống rung: {how or 'không'}")
            return {"fps": round(min(fps, 60), 2), "stab": how}
        except Exception as e:  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            log(f"[muot] {how or 'thường'} lỗi: {e}")
        finally:
            trf.unlink(missing_ok=True)
            media_ai.STATE["msg"] = ""
    raise RuntimeError("Không đọc được video " + src.name)


def prepare(ffmpeg: str, src: Path, media_dir: Path, h: str, log) -> dict:
    """Video đã sẵn sàng để dựng: {h}-v3.mp4 (chất lượng gốc) + bản xem nhẹ + thông tin."""
    out = media_dir / f"{h}-v3.mp4"
    meta = media_dir / f"{h}-v3.json"
    if not out.exists():
        info = transcode(ffmpeg, src, out, log)
        meta.write_text(json.dumps(info), encoding="utf-8")
    try:
        info = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        info = {"fps": src_fps(ffmpeg, out), "stab": ""}
    media_ai.STATE["msg"] = "Đang tạo bản xem trước nhẹ…"
    px = media_ai.make_proxy(ffmpeg, out, log)
    media_ai.STATE["msg"] = ""
    return {"id": h, "kind": "video", "url": f"/media/{out.name}", "v2": 3, **info, **({"proxy": px} if px else {}), **media_ai.probe(ffmpeg, out)}


def upgrade(d: dict, media_dir: Path, ffmpeg: str | None, log) -> dict:
    """Video nhập từ bản cũ (ép 30 hình/giây, chưa chống rung) → làm lại từ file gốc nếu còn."""
    if not ffmpeg:
        raise RuntimeError("Cần ffmpeg")
    name = Path(str(d.get("url", ""))).name
    h = name.split("-")[0]
    cands = []
    if d.get("src"):
        cands.append(Path(str(d["src"])))
    cands += sorted(media_dir.glob(f"{h}.*"))
    cands.append(media_dir / name)
    src = next((c for c in cands if c.is_file() and c.suffix.lower() in media_ai.VIDEO_EXT | {".mp4"} and not c.name.endswith((".json", ".png"))), None)
    if not src:
        raise RuntimeError("Không còn file gốc")
    return prepare(ffmpeg, src, media_dir, h, log)


def motion(ffmpeg: str | None, f: Path, step: float = .25) -> list:
    """Mức chuyển động (0–1) mỗi 0,25 giây, đo trên bản nhẹ; lưu đệm."""
    if not ffmpeg or not f.exists():
        return []
    cache = f.with_name(f.stem + "-mo.json")
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(f), "-an", "-vf",
                        "scale=128:-2,select='gte(scene,0)',metadata=print:key=lavfi.scene_score:file=-", "-f", "null", "-"],
                       capture_output=True, timeout=600, creationflags=NOWIN)
    txt = r.stdout.decode("utf-8", "ignore")
    buckets: dict = {}
    t = None
    for line in txt.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"scene_score=([\d.]+)", line)
        if m and t is not None:
            k = int(t / step)
            buckets.setdefault(k, []).append(float(m.group(1)))
    if not buckets:
        return []
    n = max(buckets) + 1
    out = [round(sum(buckets.get(i, [0])) / max(1, len(buckets.get(i, [0]))), 4) for i in range(n)]
    try:
        cache.write_text(json.dumps(out), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return out
