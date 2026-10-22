# -*- coding: utf-8 -*-
"""HL Studio — CẢNH XOAY 360° từ ảnh chụp nhiều góc hoặc một đoạn video quay vòng quanh sản phẩm.

- Video: cắt thành N khung hình đều nhau (mặc định 36 = mỗi khung 10°).
- Ảnh / khung hình: tách nền bằng AI, BỎ BÓNG PHẢN CHIẾU trên mặt bàn bóng (tìm đường mặt bàn nơi ảnh gương bắt đầu),
  cắt sát sản phẩm, căn đáy thẳng hàng để khi xoay sản phẩm không nhảy lên xuống.
"""
from __future__ import annotations

import hashlib
import io
import subprocess
from pathlib import Path

import media_ai

NOWIN = media_ai.NOWIN


def drop_reflection(im):
    """Ảnh RGBA đã tách nền: bỏ phần BÓNG PHẢN CHIẾU trên mặt bàn bóng còn dính lại.
    Bóng trên bàn (gỗ, đá màu) là một dải ở ĐÁY ảnh mà gần như mọi điểm đều mang màu mặt bàn; sản phẩm thì không.
    Dò từ dưới lên: các hàng ≥93% điểm cùng tông màu mặt bàn liền nhau → cắt ở mép trên dải đó."""
    import numpy as np  # type: ignore
    a = np.asarray(im).astype(np.float32)
    al = a[..., 3]
    ys, _ = np.where(al > 40)
    if len(ys) < 100:
        return im
    y0, y1 = int(ys.min()), int(ys.max())
    H = y1 - y0
    rgb = a[..., :3]
    mx, mn = rgb.max(2), rgb.min(2)
    sat = (mx - mn) / (mx + 1)
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # màu mặt bàn = màu trung bình 4% hàng dưới cùng (gỗ nâu, đá, kính màu...)
    base = rgb[y1 - max(3, H // 25):y1 + 1][al[y1 - max(3, H // 25):y1 + 1] > 40]
    if len(base) < 30:
        return im
    mu = base.mean(0)
    warm_floor = mu[0] > mu[2] + 15 and (mu.max() - mu.min()) / (mu.max() + 1) > .2
    if warm_floor:
        like = (R > G + 8) & (R > B + 20) & (sat > .18)
    else:  # mặt bàn tối / màu khác: gần màu mặt bàn
        like = np.abs(rgb - mu).sum(2) < 60
    op = al > 40
    frac = (like & op).sum(1) / np.maximum(1, op.sum(1))
    y = y1
    while y > y0 + H * .3 and frac[y] >= .88:
        y -= 1
    if y1 - y < H * .06:  # không có dải bóng rõ → giữ nguyên
        return im
    cut = y + 1
    out = a.copy()
    out[cut:, :, 3] = 0
    fade = max(2, H // 200)
    for k in range(fade):
        out[cut - 1 - k, :, 3] *= (k + 1) / (fade + 1)
    from PIL import Image  # type: ignore
    return Image.fromarray(out.clip(0, 255).astype("uint8"), "RGBA")


def _prep(png: bytes, size: int = 900):
    from PIL import Image  # type: ignore
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    im = drop_reflection(im)
    bb = im.getchannel("A").point(lambda v: 255 if v > 30 else 0).getbbox()
    if bb:
        im = im.crop(bb)
    im.thumbnail((size, size))
    return im


def frames_from_video(ffmpeg: str, src: Path, n: int, out_dir: Path) -> list:
    dur = media_ai.probe(ffmpeg, src).get("dur") or 0
    if not dur:
        raise RuntimeError("Không đọc được độ dài video")
    files = []
    for i in range(n):
        t = dur * (i + .5) / n
        f = out_dir / f"_spin_{i:03d}.jpg"
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", "-q:v", "2", str(f)],
                       capture_output=True, creationflags=NOWIN)
        if f.exists():
            files.append(f)
    return files


def build(d: dict, media_dir: Path, models_dir: Path, ffmpeg: str | None, log) -> dict:
    """d: {video: url} hoặc {images: [url...]} (theo đúng thứ tự góc). Trả {id, frames:[url], w, h}."""
    srcs: list[bytes] = []
    tmp: list[Path] = []
    if d.get("video"):
        if not ffmpeg:
            raise RuntimeError("Cần ffmpeg")
        v = media_dir / Path(str(d["video"])).name
        n = max(8, min(72, int(d.get("n") or 36)))
        media_ai.STATE["msg"] = "Đang cắt khung hình từ video xoay…"
        tmp = frames_from_video(ffmpeg, v, n, media_dir)
        srcs = [f.read_bytes() for f in tmp]
    else:
        for u in d.get("images") or []:
            f = media_dir / Path(str(u)).name
            if f.exists():
                srcs.append(f.read_bytes())
    if len(srcs) < 2:
        raise RuntimeError("Cần ít nhất 2 ảnh / một đoạn video xoay")
    gid = hashlib.sha1(b"".join(hashlib.sha1(s).digest() for s in srcs)).hexdigest()[:12]
    out, W, Hh = [], 0, 0
    try:
        for i, b in enumerate(srcs):
            f = media_dir / f"xoay-{gid}-{i:03d}.png"
            if not f.exists():
                media_ai.STATE["msg"] = f"Đang tách nền khung xoay {i + 1}/{len(srcs)}…"
                png = media_ai.cutout(b, models_dir, log)
                if not png:
                    raise RuntimeError("Tách nền không được")
                im = _prep(png)
                im.save(f, "PNG")
            from PIL import Image  # type: ignore
            with Image.open(f) as im:
                W, Hh = max(W, im.width), max(Hh, im.height)
            out.append(f"/media/{f.name}")
    finally:
        media_ai.STATE["msg"] = ""
        for f in tmp:
            f.unlink(missing_ok=True)
    log(f"[xoay360] {gid}: {len(out)} khung")
    return {"id": gid, "frames": out, "w": W, "h": Hh}


def _dewood(im, strength: float = 1.0):
    """Mặt kim loại/inox bóng hay ám màu mặt bàn gỗ → đưa về xám kim loại (chỉ vùng ngả cam/nâu)."""
    import numpy as np  # type: ignore
    from PIL import Image  # type: ignore
    a = np.asarray(im.convert("RGB")).astype(float) / 255
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    sat = (a.max(2) - a.min(2)) / (a.max(2) + 1e-6)
    k = np.clip((sat - .07) / .33, 0, 1) * ((r > b + .035) & (r >= g)) * strength
    lum = (.3 * r + .59 * g + .11 * b)[..., None]
    steel = np.concatenate([lum * .97, lum, lum * 1.05], 2)
    o = a * (1 - k[..., None]) + steel * k[..., None]
    return Image.fromarray((np.clip(o, 0, 1) * 255).astype("uint8"))


def build_box(d: dict, media_dir: Path, models_dir: Path, log) -> dict:
    """Hộp 3D từ ảnh chụp THẲNG các mặt: {front, back, side, top?: url, metal?: bool}.
    Mỗi ảnh: tách nền → bỏ bóng mặt bàn → cắt sát → làm mặt hộp. Kích thước hộp suy ra từ tỉ lệ ảnh."""
    from PIL import Image  # type: ignore
    faces = {}
    keys = [k for k in ("front", "back", "side", "top") if d.get(k)]
    if not all(k in keys for k in ("front", "back", "side")):
        raise RuntimeError("Cần ít nhất 3 ảnh chụp thẳng: mặt trước, mặt sau, mặt hông")
    srcs = {k: (media_dir / Path(str(d[k])).name).read_bytes() for k in keys}
    gid = hashlib.sha1(b"".join(hashlib.sha1(srcs[k]).digest() for k in keys)).hexdigest()[:12]
    try:
        for i, k in enumerate(keys):
            out = media_dir / f"hop-{gid}-{k}.jpg"
            if not out.exists():
                media_ai.STATE["msg"] = f"Đang tách nền mặt {['trước', 'sau', 'hông', 'trên'][('front', 'back', 'side', 'top').index(k)]} ({i + 1}/{len(keys)})…"
                png = media_ai.cutout(srcs[k], models_dir, log)
                if not png:
                    raise RuntimeError("Tách nền không được")
                im = drop_reflection(Image.open(io.BytesIO(png)).convert("RGBA"))
                bb = im.getchannel("A").point(lambda v: 255 if v > 60 else 0).getbbox()
                im = im.crop(bb) if bb else im
                bg = Image.new("RGB", im.size, (150, 154, 160))
                bg.paste(im, (0, 0), im)
                if d.get("metal", True):
                    bg = _dewood(bg)
                bg.thumbnail((1400, 1400))
                bg.save(out, "JPEG", quality=93)
            with Image.open(out) as im:
                faces[k] = (f"/media/{out.name}", im.width / max(1, im.height))
    finally:
        media_ai.STATE["msg"] = ""
    w = faces["front"][1]
    dpt = faces["side"][1]
    log(f"[hop3d] {gid}: rộng {w:.2f} × cao 1 × sâu {dpt:.2f}")
    return {"id": gid, **{k: v[0] for k, v in faces.items()}, "w": round(w, 3), "h": 1, "d": round(dpt, 3)}
