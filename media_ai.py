# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

NOWIN = 0x08000000 if os.name == 'nt' else 0

MODEL_URLS = {
    'isnet-general-use': 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx',
    'u2netp': 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx',
    'birefnet-lite': 'https://huggingface.co/onnx-community/BiRefNet_lite-ONNX/resolve/main/onnx/model.onnx',
}

STATE = {'msg': '', 'busy': False}
_sess: dict = {}
_lock = threading.Lock()

VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.wmv', '.m4v', '.3gp'}


def _download(url: str, dst: Path, log) -> None:
    tmp = dst.with_suffix('.part')
    log(f"[tach-nen] tải mô hình {dst.name} …")
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as r, open(tmp, 'wb') as f:
            total = int(r.headers.get('Content-Length') or 0)
            got = 0
            while True:
                b = r.read(1024 * 1024)
                if not b:
                    break
                f.write(b)
                got += len(b)
                if total:
                    log(f"[tach-nen] {got * 100 // total}% ({got // (1024 * 1024)}/{total // (1024 * 1024)} MB)")
        tmp.replace(dst)
        log(f"[tach-nen] tải xong {dst.name}")
    except Exception as e:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise e


def _session(models_dir: Path, log, names=('isnet-general-use', 'u2netp')):
    import onnxruntime as ort

    with _lock:
        for name in names:
            if name in _sess:
                return name, _sess[name]
            f = models_dir / f"{name}.onnx"
            if not f.exists():
                url = MODEL_URLS.get(name)
                if url:
                    try:
                        _download(url, f, log)
                    except Exception as e:
                        log(f"[tach-nen] không tải được {name}: {e}")
                        continue
            if f.exists():
                try:
                    so = ort.SessionOptions()
                    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    s = ort.InferenceSession(str(f), sess_options=so, providers=['CPUExecutionProvider'])
                    _sess[name] = s
                    return name, s
                except Exception as e:
                    log(f"[tach-nen] lỗi nạp mô hình {name}: {e}")
        return None, None


def cutout(img_bytes: bytes, models_dir: Path, log, mode: str = 'auto'):
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps

    im = ImageOps.exif_transpose(Image.open(io.BytesIO(img_bytes))).convert('RGB')
    if max(im.size) > 2400:
        im.thumbnail((2400, 2400))

    if mode == 'plain':
        plain = plain_cut(im, force=True)
        if plain is not None:
            log('[tach-nen] nền trơn: tách theo màu nền')
            return plain

    name, sess = None, None
    if mode == 'ky':
        name, sess = _session(models_dir, log, ('birefnet-lite',))
        if sess is None:
            log('[tach-nen] chưa có BiRefNet, dùng ISNet')
    if sess is None:
        name, sess = _session(models_dir, log)

    if sess is None:
        if mode == 'auto':
            plain = plain_cut(im)
        else:
            plain = None
        if plain is not None:
            log('[tach-nen] chưa có mô hình AI, tách theo màu nền')
            return plain
        raise RuntimeError('Chưa có mô hình tách nền ONNX và không phải ảnh nền trơn')

    size = (1024, 1024) if ('isnet' in name or 'birefnet' in name) else (320, 320)
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    x = np.asarray(im.resize(size, Image.BILINEAR), dtype=np.float32) / 255.0
    x = (x - mean) / std
    x = np.transpose(x, (2, 0, 1))[None, ...].astype(np.float32)

    t0 = time.time()
    outs = sess.run(None, {sess.get_inputs()[0].name: x})
    out = outs[0][0]
    if out.ndim == 3 and out.shape[0] == 1:
        out = out[0]
    pred = (out - out.min()) / (out.max() - out.min() + 1e-8)
    mask = Image.fromarray((pred * 255.0).astype(np.uint8), mode='L').resize(im.size, Image.BILINEAR)
    m = np.asarray(mask, dtype=np.float32) / 255.0

    try:
        rgba = _refine(im, m)
    except Exception as e:
        log(f"[tach-nen] lỗi refine mask: {e}")
        rgba = im.convert('RGBA')
        rgba.putalpha(mask)

    bb = rgba.getbbox()
    if bb:
        pad = max(4, int(min(rgba.size) * 0.01))
        x0 = max(0, bb[0] - pad)
        y0 = max(0, bb[1] - pad)
        x1 = min(rgba.width, bb[2] + pad)
        y1 = min(rgba.height, bb[3] + pad)
        rgba = rgba.crop((x0, y0, x1, y1))

    buf = io.BytesIO()
    rgba.save(buf, format='PNG')
    log(f"[tach-nen] tách xong ({round(time.time() - t0, 1)}s, {name})")
    return buf.getvalue()


def _cut_reflection(a, core, m):
    import numpy as np
    from scipy import ndimage

    if m is None or core.sum() < core.size * 0.02:
        return core

    ys = np.where(core.any(axis=1))[0]
    if len(ys) < 20:
        return core

    y0, y1 = ys[0], ys[-1]
    H = y1 - y0
    if H < 30:
        return core

    # Kiểm tra phản chiếu ở phần dưới
    sat = (a.max(axis=-1) - a.min(axis=-1)) / (a.max(axis=-1) + 1.0)
    cnt = core.sum(axis=1)

    y_cut = y1
    # Tìm vết cắt eo thắt hoặc bóng phản chiếu mờ ở dưới
    bottom_start = int(y0 + H * 0.65)
    for y in range(y1 - 1, bottom_start, -1):
        if cnt[y] < cnt[y - 1] * 0.4 and cnt[y] < cnt[int(y0 + H * 0.5)] * 0.2:
            y_cut = y
            break

    if y_cut < y1:
        newc = core.copy()
        newc[y_cut:, :] = False
        if newc.sum() >= core.sum() * 0.5:
            lab, n = ndimage.label(newc)
            if n > 1:
                sizes = ndimage.sum(newc, lab, range(1, n + 1))
                max_s = max(sizes)
                newc = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= max_s * 0.3])
            return newc

    return core


def _refine(im, m):
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    a = np.asarray(im, dtype=np.float32)
    h, w, _ = a.shape
    bw = max(2, min(h, w) // 100)

    border = np.concatenate([
        a[:bw, :].reshape(-1, 3),
        a[-bw:, :].reshape(-1, 3),
        a[:, :bw].reshape(-1, 3),
        a[:, -bw:].reshape(-1, 3),
    ])
    bgc = np.median(border, axis=0)
    plain = np.percentile(np.sqrt(((border - bgc) ** 2).sum(axis=1)), 90) < 28

    core = m > 0.5
    lab, n = ndimage.label(core)
    if n > 1:
        sizes = ndimage.sum(core, lab, range(1, n + 1))
        max_s = max(sizes)
        core = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= max_s * 0.05])
    core = ndimage.binary_fill_holes(core)

    try:
        core = _cut_reflection(a, core, m)
    except Exception:
        pass

    inner = ndimage.binary_erosion(core, iterations=1)
    alpha = ndimage.gaussian_filter(inner.astype(np.float32), 0.9)

    if plain:
        aa = np.clip(alpha, 0.001, 1.0)[..., None]
        fg = np.clip((a - bgc * (1.0 - aa)) / np.maximum(aa, 0.25), 0, 255)
        a = np.where(alpha[..., None] < 0.98, fg, a)
    else:
        alpha = alpha * ndimage.binary_dilation(core, iterations=2)

    out = np.dstack([a, np.clip(alpha * 255.0, 0, 255)]).astype(np.uint8)
    return Image.fromarray(out, mode='RGBA')


def plain_cut(im, force: bool = False):
    import numpy as np
    from PIL import Image, ImageFilter

    try:
        from scipy import ndimage
    except Exception:
        return None

    a = np.asarray(im, dtype=np.int32)
    h, w, _ = a.shape
    bw = max(2, min(h, w) // 100)

    border = np.concatenate([
        a[:bw, :].reshape(-1, 3),
        a[-bw:, :].reshape(-1, 3),
        a[:, :bw].reshape(-1, 3),
        a[:, -bw:].reshape(-1, 3),
    ])
    med = np.median(border, axis=0)
    dist_b = np.sqrt(((border - med) ** 2).sum(axis=1))

    if not force and np.percentile(dist_b, 90) > 30:
        return None

    dist = np.sqrt(((a - med) ** 2).sum(axis=-1))
    thresh = max(18.0, float(np.percentile(dist_b, 95) * 1.5))
    near = dist > thresh

    lab, n = ndimage.label(near)
    if n == 0:
        return None

    sizes = ndimage.sum(near, lab, range(1, n + 1))
    max_s = max(sizes)
    fg = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= max_s * 0.1])
    fg = ndimage.binary_fill_holes(fg)

    alpha = ndimage.gaussian_filter(fg.astype(np.float32), 0.8)
    rgba = np.dstack([a, np.clip(alpha * 255.0, 0, 255)]).astype(np.uint8)
    res = Image.fromarray(rgba, mode='RGBA')

    bb = res.getbbox()
    if bb:
        pad = max(4, int(min(res.size) * 0.01))
        x0 = max(0, bb[0] - pad)
        y0 = max(0, bb[1] - pad)
        x1 = min(res.width, bb[2] + pad)
        y1 = min(res.height, bb[3] + pad)
        res = res.crop((x0, y0, x1, y1))

    buf = io.BytesIO()
    res.save(buf, format='PNG')
    return buf.getvalue()


def recut(mid: str, mode: str, media_dir: Path, models_dir: Path, log) -> dict:
    orig = media_dir / f"{mid}.png"
    if not orig.exists():
        raise RuntimeError('Không thấy ảnh gốc')
    if mode == 'none':
        return {'url': f"/media/{orig.name}", 'cut': False, 'cutMode': 'none'}

    out = media_dir / f"{mid}-cut4-{mode}.png"
    if not out.exists():
        png = cutout(orig.read_bytes(), models_dir, log, mode)
        if not png:
            raise RuntimeError('Cách tách này không hợp với ảnh, thử cách khác')
        out.write_bytes(png)
    return {'url': f"/media/{out.name}", 'cut': True, 'cutMode': mode}


def save_media(
    data: bytes,
    name: str,
    media_dir: Path,
    models_dir: Path,
    ffmpeg: str | None,
    log,
    want_cut: bool = True,
) -> dict:
    media_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(data).hexdigest()[:16]
    ext = Path(name or 'x.jpg').suffix.lower() or '.jpg'

    if ext in VIDEO_EXT:
        src = media_dir / f"{h}{ext}"
        if not src.exists():
            src.write_bytes(data)
        if ffmpeg:
            try:
                import dung_muot
                res = dung_muot.prepare(ffmpeg, src, media_dir, h, log)
                res['name'] = name
                return res
            except Exception as e:
                log(f"[video] dung_muot.prepare lỗi ({e}), dùng video trực tiếp")
        return {
            'id': h,
            'kind': 'video',
            'orig': f"/media/{src.name}",
            'url': f"/media/{src.name}",
            'name': name,
            'fps': 30.0,
            'dur': 10.0,
            'w': 1080,
            'h': 1920,
            'cut': False,
        }

    from PIL import Image, ImageOps

    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    orig = media_dir / f"{h}.png"
    if not orig.exists():
        o = im.convert('RGBA') if im.mode in ('RGBA', 'LA', 'P') else im.convert('RGB')
        if max(o.size) > 2400:
            o.thumbnail((2400, 2400))
        o.save(orig, 'PNG')

    res = {
        'id': h,
        'kind': 'image',
        'orig': f"/media/{orig.name}",
        'name': name,
        'cut': False,
        'url': f"/media/{orig.name}",
    }

    has_alpha = False
    if im.mode in ('RGBA', 'LA'):
        try:
            has_alpha = im.getchannel('A').getextrema()[0] < 200
        except Exception:
            pass

    if want_cut and not has_alpha:
        cut = media_dir / f"{h}-cut4.png"
        if not cut.exists():
            try:
                png = cutout(data, models_dir, log)
                if png:
                    cut.write_bytes(png)
            except Exception as e:
                log(f"[tach-nen] Không tách nền được ({e}), sử dụng ảnh gốc.")
        if cut.exists():
            res.update(url=f"/media/{cut.name}", cut=True)
            return res
    if has_alpha:
        res['cut'] = True
    return res


def make_proxy(ffmpeg: str | None, src: Path, log) -> str | None:
    if not ffmpeg or not src.exists():
        return None
    out = src.with_name(src.stem.replace('-v', '') + '-p.mp4')
    if out.exists():
        return f"/media/{out.name}"
    tmp = out.with_suffix('.part.mp4')
    vf = "scale='if(gt(iw,ih),min(960,iw),-2)':'if(gt(iw,ih),-2,min(960,ih))'"
    cmd = [
        ffmpeg,
        '-y',
        '-loglevel',
        'error',
        '-i',
        str(src),
        '-vf',
        vf,
        '-c:v',
        'libx264',
        '-preset',
        'veryfast',
        '-crf',
        '30',
        '-g',
        '10',
        '-keyint_min',
        '10',
        '-sc_threshold',
        '0',
        '-pix_fmt',
        'yuv420p',
        '-an',
        '-movflags',
        '+faststart',
        str(tmp),
    ]
    kwargs = {'capture_output': True}
    if os.name == 'nt':
        kwargs['creationflags'] = NOWIN
    r = subprocess.run(cmd, **kwargs)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        if log:
            log(f"[proxy] lỗi: {r.stderr.decode('utf-8', 'ignore')[-200:]}")
        return None
    tmp.replace(out)
    return f"/media/{out.name}"


def make_audio(ffmpeg: str | None, src: Path) -> str | None:
    if not ffmpeg or not src.exists():
        return None
    out = src.with_name(src.stem.replace('-v', '') + '-a.m4a')
    if out.exists():
        return f"/media/{out.name}"
    cmd = [
        ffmpeg,
        '-y',
        '-loglevel',
        'error',
        '-i',
        str(src),
        '-vn',
        '-c:a',
        'copy',
        str(out),
    ]
    kwargs = {'capture_output': True}
    if os.name == 'nt':
        kwargs['creationflags'] = NOWIN
    r = subprocess.run(cmd, **kwargs)
    if r.returncode != 0:
        if out.exists():
            out.unlink(missing_ok=True)
        return None
    return f"/media/{out.name}"


def probe(ffmpeg: str, f: Path) -> dict:
    cmd = [ffmpeg, '-i', str(f)]
    kwargs = {'capture_output': True}
    if os.name == 'nt':
        kwargs['creationflags'] = NOWIN
    r = subprocess.run(cmd, **kwargs)
    s = r.stderr.decode('utf-8', 'ignore')
    import re

    dur = 0.0
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', s)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    w, h = 0, 0
    m = re.search(r'Video:.*?(\d{2,5})x(\d{2,5})', s)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
    return {
        'dur': round(dur, 2),
        'w': w,
        'h': h,
        'audio': 'Audio:' in s,
    }


def _gemini_key() -> str:
    try:
        import hl_pro
        k = hl_pro.gemini_key()
        if k:
            return k
    except Exception:
        pass
    try:
        import vbt_common
        k = vbt_common.gemini_key()
        if k:
            return k
    except Exception:
        pass
    return os.environ.get('GEMINI_API_KEY', '')


def gemini_vision(system: str, user: str, images: list[bytes], log, llm_mod=None) -> dict:
    import requests
    from PIL import Image

    key = _gemini_key()
    if not key:
        raise RuntimeError('Chưa có API key Gemini. Mở ⚙ Cài đặt › AI & MCP, dán khoá Gemini (lấy ở aistudio.google.com) rồi thử lại.')

    models = []
    try:
        import hl_pro
        models = [m for m in hl_pro.gemini_models(key) if m]
        if llm_mod and hasattr(llm_mod, 'gemini_models'):
            models += [m for m in llm_mod.gemini_models(key) if m]
    except Exception as e:
        log(f"[ai] lấy danh sách mô hình lỗi: {e}")

    if not models:
        models = ['gemini-2.5-flash', 'gemini-2.0-flash']

    parts: list[dict] = [{'text': user}]
    for b in images or []:
        try:
            im = Image.open(io.BytesIO(b))
            if max(im.size) > 1024:
                im.thumbnail((1024, 1024))
            buf = io.BytesIO()
            im.save(buf, format='JPEG', quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode()
            parts.append({
                'inlineData': {
                    'mimeType': 'image/jpeg',
                    'data': b64,
                }
            })
        except Exception as e:
            log(f"[ai] lỗi chuẩn bị ảnh: {e}")

    body = {
        'contents': [{'role': 'user', 'parts': parts}],
        'systemInstruction': {'parts': [{'text': system}]},
        'generationConfig': {
            'temperature': 0.7,
            'responseMimeType': 'application/json',
        },
    }

    last_err = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        for attempt in range(2):
            try:
                r = requests.post(url, json=body, timeout=60)
                if r.status_code == 200:
                    j = r.json()
                    candidates = j.get('candidates', [])
                    if candidates:
                        content_parts = candidates[0].get('content', {}).get('parts', [])
                        txt = ''.join(p.get('text', '') for p in content_parts if not p.get('thought'))
                        txt = txt.strip()
                        if txt.startswith('```'):
                            txt = re.sub(r'^```(?:json)?\s*', '', txt)
                            txt = re.sub(r'\s*```$', '', txt)
                        return json.loads(txt)
                elif r.status_code == 429:
                    time.sleep(2)
                    continue
                else:
                    last_err = f"{r.status_code}: {r.text[:200]}"
            except Exception as e:
                last_err = str(e)
                time.sleep(1)

    raise RuntimeError(f"Lỗi gọi Gemini Vision: {last_err}")
