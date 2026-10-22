# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import csv
import io
import json
import os
import re
import threading
import time
import uuid
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parent

AI_DEF = {
    'gemini_key': '',
    'gemini_model': '',
    'gemini_image_model': '',
    'openai_key': '',
    'openai_base': 'https://api.openai.com/v1',
    'openai_model': 'gpt-5-mini',
    'openai_image_model': 'gpt-image-1',
}

_GM = {'t': 0.0, 'list': []}
_lock = threading.Lock()
UPS_JOBS: dict = {}
_UPS: dict = {'sess': None}

UPS_URL = 'https://huggingface.co/CoderViking/realesr-general-x4v3-onnx/resolve/c6a971706797c7502945a2b4c4274fce4900d4ab/realesr-general-x4v3.onnx'

BRAND_KEYS = ('name', 'phone', 'web', 'color', 'logo', 'voiceName', 'music', 'subStyle', 'slogan', 'theme')

HOOK_SYSTEM = """Bạn là biên tập viên video ngắn (TikTok / Reels / Shorts) tiếng Việt. Từ nội dung video được gửi, viết 3 CÂU MỞ ĐẦU khác hẳn nhau (hook) để giữ chân người xem trong 3 giây đầu:
1. Gây sốc / tò mò (ngược đời, bất ngờ)
2. Nỗi đau / cảnh báo (đánh trúng vấn đề người xem hay gặp)
3. Lợi ích vượt trội / cách làm nhanh
Trả về JSON: {"hooks": ["câu 1", "câu 2", "câu 3"]}"""


def _srv():
    import sys
    return sys.modules.get('__main__') or sys.modules.get('server')


def _ctx():
    return {'HOME': _home()}


def _home() -> Path:
    return Path(os.environ.get('VSP_HOME') or (Path.home() / '.video-san-pham'))


def log(msg: str) -> None:
    try:
        s = _srv()
        if s and hasattr(s, 'log'):
            s.log(msg)
        else:
            print(msg)
    except Exception:
        print(msg)


def _rj(f: Path, default=None):
    if default is None:
        default = {}
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            pass
    return default


def _wj(f: Path, data) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', s)
    s = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', s)
    s = re.sub(r'[ìíịỉĩ]', 'i', s)
    s = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', s)
    s = re.sub(r'[ùúụủũưừứựửữ]', 'u', s)
    s = re.sub(r'[ỳýỵỷỹ]', 'y', s)
    s = re.sub(r'[đ]', 'd', s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-') or 'item'


def ai_file() -> Path:
    return _home() / 'ai.json'


def ai_cfg() -> dict:
    d = dict(AI_DEF)
    d.update({k: v for k, v in _rj(ai_file(), {}).items() if k in AI_DEF})
    for k, env in (('gemini_key', 'GEMINI_API_KEY'), ('openai_key', 'OPENAI_API_KEY')):
        if not d.get(k) and os.environ.get(env):
            d[k] = os.environ[env]
    return d


def _mask(k: str) -> str:
    if not k or len(k) < 8:
        return '***' if k else ''
    return k[:4] + '***' + k[-4:]


def ai_public() -> dict:
    c = ai_cfg()
    return {
        **c,
        'gemini_key_masked': _mask(c.get('gemini_key', '')),
        'openai_key_masked': _mask(c.get('openai_key', '')),
    }


def ai_save(d: dict) -> dict:
    cur = _rj(ai_file(), {})
    for k in AI_DEF:
        if k in d:
            v = d[k]
            if k.endswith('_key'):
                v = str(v or '').strip()
                if '***' in v:
                    continue
            cur[k] = v
    _wj(ai_file(), cur)
    return ai_public()


def gemini_key() -> str | None:
    return ai_cfg().get('gemini_key') or None


def gemini_models(key: str) -> list[str]:
    cfg_mod = ai_cfg().get('gemini_model', '')
    res = [cfg_mod] if cfg_mod else []
    if time.time() - _GM['t'] < 3600 and _GM['list']:
        return list(dict.fromkeys(res + _GM['list']))
    try:
        import requests
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=10)
        if r.status_code == 200:
            names = [m['name'].replace('models/', '') for m in r.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            _GM['t'] = time.time()
            _GM['list'] = names
            return list(dict.fromkeys(res + names))
    except Exception as e:
        log(f"[ai] lỗi lấy danh sách gemini_models: {e}")
    return list(dict.fromkeys(res + ['gemini-2.5-flash', 'gemini-2.0-flash']))


def _openai(path: str, body: dict | None = None, files: dict | None = None, timeout: float = 300.0) -> dict:
    import requests
    c = ai_cfg()
    key = c.get('openai_key')
    if not key:
        raise RuntimeError('Chưa có OpenAI API Key. Cài đặt trong ⚙ Cài đặt › AI & MCP.')
    url = (c.get('openai_base') or 'https://api.openai.com/v1').rstrip('/') + path
    h = {'Authorization': f"Bearer {key}"}
    if files:
        r = requests.post(url, headers=h, data=body, files=files, timeout=timeout)
    else:
        h['Content-Type'] = 'application/json'
        r = requests.post(url, headers=h, json=body, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"OpenAI error {r.status_code}: {r.text[:300]}")
    return r.json()


def openai_json(system: str, user: str, images: list[bytes] | None = None, timeout: float = 300.0) -> dict:
    c = ai_cfg()
    model = c.get('openai_model') or 'gpt-5-mini'
    content = [{'type': 'text', 'text': user}]
    for b in images or []:
        b64 = base64.b64encode(b).decode('utf-8')
        content.append({'type': 'image_url', 'image_url': {'url': f"data:image/png;base64,{b64}"}})
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': content},
        ],
        'response_format': {'type': 'json_object'},
    }
    j = _openai('/chat/completions', body, timeout=timeout)
    txt = j['choices'][0]['message']['content']
    return json.loads(txt)


def openai_image(prompt: str, refs: list[bytes] | None = None, aspect: str = '1:1') -> bytes:
    import requests
    c = ai_cfg()
    model = c.get('openai_image_model') or 'gpt-image-1'
    size = '1024x1792' if aspect == '9:16' else ('1792x1024' if aspect == '16:9' else '1024x1024')
    body = {
        'model': model,
        'prompt': prompt,
        'n': 1,
        'size': size,
        'response_format': 'b64_json',
    }
    j = _openai('/images/generations', body, timeout=120)
    b64 = j['data'][0]['b64_json']
    return base64.b64decode(b64)


def mcp_info() -> dict:
    py = sys.executable
    mcp_script = APP / 'hl_mcp.py'
    return {
        'server': 'hl-studio',
        'command': py,
        'args': [str(mcp_script)],
        'env': {'PYTHONIOENCODING': 'utf-8'},
    }


def mcp_install() -> dict:
    info = mcp_info()
    return {'ok': True, 'config': info}


def brand_dir() -> Path:
    p = _home() / 'thuong-hieu'
    p.mkdir(parents=True, exist_ok=True)
    return p


def brands() -> list[dict]:
    res = []
    for f in sorted(brand_dir().glob('*.json')):
        d = _rj(f)
        if d:
            res.append(d)
    return res


def brand_save(b: dict) -> dict:
    bid = b.get('id') or _slug(b.get('name') or 'brand')
    b['id'] = bid
    _wj(brand_dir() / f"{bid}.json", b)
    return b


def brand_delete(bid: str) -> dict:
    f = brand_dir() / f"{bid}.json"
    if f.is_file():
        f.unlink()
    return {'ok': True}


def series_dir() -> Path:
    p = _home() / 'chuoi-video'
    p.mkdir(parents=True, exist_ok=True)
    return p


def series_list() -> list[dict]:
    res = []
    for f in sorted(series_dir().glob('*.json')):
        d = _rj(f)
        if d:
            res.append(d)
    return res


def series_get(sid: str) -> dict:
    return _rj(series_dir() / f"{sid}.json", {})


def series_save(d: dict) -> dict:
    sid = d.get('id') or f"series_{uuid.uuid4().hex[:8]}"
    d['id'] = sid
    _wj(series_dir() / f"{sid}.json", d)
    return d


def series_delete(sid: str) -> dict:
    f = series_dir() / f"{sid}.json"
    if f.is_file():
        f.unlink()
    return {'ok': True}


COLS = (
    ('tên', 'ten', 'name', 'sản phẩm', 'san pham', 'product'),
    ('thông tin', 'thong tin', 'mô tả', 'mo ta', 'ý chính', 'y chinh', 'info', 'description', 'nội dung'),
    ('giá', 'gia', 'price'),
    ('ảnh', 'anh', 'hình', 'hinh', 'image', 'images', 'thư mục', 'thu muc', 'folder', 'video'),
    ('ghi chú', 'ghi chu', 'note', 'notes', 'yêu cầu', 'yeu cau'),
    ('kiểu', 'kieu', 'loại', 'loai', 'mode', 'type'),
)


def _xlsx_rows(b: bytes) -> list[list[str]]:
    rows = []
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            xml = z.read('xl/sharedStrings.xml').decode('utf-8', 'ignore')
            for m in re.finditer(r'<t[^>]*>(.*?)</t>', xml, re.S):
                shared.append(m.group(1))

        if 'xl/worksheets/sheet1.xml' in z.namelist():
            sheet_xml = z.read('xl/worksheets/sheet1.xml').decode('utf-8', 'ignore')
            for r in re.finditer(r'<row[^>]*>(.*?)</row>', sheet_xml, re.S):
                row_vals = []
                for c in re.finditer(r'<c[^>]*t=["\']([^"\']*)["\'][^>]*><v>([^<]*)</v></c>', r.group(1)):
                    t, v = c.group(1), c.group(2)
                    if t == 's' and v.isdigit() and int(v) < len(shared):
                        row_vals.append(shared[int(v)])
                    else:
                        row_vals.append(v)
                if row_vals:
                    rows.append(row_vals)
    return rows


def parse_list(b: bytes, name: str) -> dict:
    nl = name.lower()
    rows = []
    if nl.endswith(('.csv', '.txt')):
        text = b.decode('utf-8-sig', 'ignore')
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    elif nl.endswith('.xlsx'):
        try:
            rows = _xlsx_rows(b)
        except Exception as e:
            raise RuntimeError(f"Lỗi đọc file Excel: {e}")

    if not rows:
        return {'items': []}

    header = [h.strip().lower() for h in rows[0]]
    mapping = {}
    for idx, col in enumerate(header):
        for key_idx, aliases in enumerate(COLS):
            target_key = ('ten', 'info', 'gia', 'anh', 'ghichu', 'kieu')[key_idx]
            if any(a in col for a in aliases):
                mapping[target_key] = idx
                break

    items = []
    for r in rows[1:]:
        if not any(r):
            continue
        item = {}
        for k, idx in mapping.items():
            if idx < len(r):
                item[k] = r[idx].strip()
        items.append(item)
    return {'items': items}


def _ups_model() -> Path:
    f = APP / 'models' / 'realesr-general-x4v3.onnx'
    if not f.is_file():
        try:
            import urllib.request
            f.parent.mkdir(parents=True, exist_ok=True)
            log("[upscale] đang tải mô hình RealESRGAN …")
            urllib.request.urlretrieve(UPS_URL, str(f))
        except Exception as e:
            log(f"[upscale] lỗi tải mô hình: {e}")
    return f


def _ups_session():
    if _UPS['sess'] is not None:
        return _UPS['sess']
    f = _ups_model()
    if not f.is_file():
        return None
    try:
        import onnxruntime as ort
        _UPS['sess'] = ort.InferenceSession(str(f), providers=['CPUExecutionProvider'])
        return _UPS['sess']
    except Exception as e:
        log(f"[upscale] lỗi khởi tạo ONNX session: {e}")
        return None


def upscale_image(src: Path, out: Path, want: int = 2, tile: int = 192, pad: int = 12, prog=None) -> Path:
    import numpy as np
    from PIL import Image

    sess = _ups_session()
    if not sess:
        raise RuntimeError('Chưa có mô hình RealESRGAN')

    im = Image.open(src)
    alpha = im.getchannel('A') if im.mode in ('RGBA', 'LA') else None
    rgb = np.asarray(im.convert('RGB'), dtype=np.float32) / 255.0

    h, w, _ = rgb.shape
    out_h, out_w = h * 4, w * 4
    out_arr = np.zeros((out_h, out_w, 3), dtype=np.float32)

    ys = list(range(0, h, tile))
    xs = list(range(0, w, tile))
    total = len(ys) * len(xs)
    done = 0

    inp_name = sess.get_inputs()[0].name

    for y in ys:
        for x in xs:
            y0, x0 = max(0, y - pad), max(0, x - pad)
            y1, x1 = min(h, y + tile + pad), min(w, x + tile + pad)

            patch = rgb[y0:y1, x0:x1]
            t = np.transpose(patch, (2, 0, 1))[None, ...].astype(np.float32)
            res = sess.run(None, {inp_name: t})[0][0]
            res = np.transpose(res, (1, 2, 0))

            oy0, ox0 = (y - y0) * 4, (x - x0) * 4
            oy1, ox1 = oy0 + min(tile, h - y) * 4, ox0 + min(tile, w - x) * 4

            out_arr[y * 4:y * 4 + (oy1 - oy0), x * 4:x * 4 + (ox1 - ox0)] = res[oy0:oy1, ox0:ox1]
            done += 1
            if prog:
                prog(done / total)

    out_arr = np.clip(out_arr * 255.0, 0, 255).astype(np.uint8)
    up_im = Image.fromarray(out_arr)

    target_w, target_h = w * want, h * want
    if want != 4:
        up_im = up_im.resize((target_w, target_h), Image.LANCZOS)

    if alpha:
        alpha_up = alpha.resize((target_w, target_h), Image.BILINEAR)
        up_im.putalpha(alpha_up)

    out.parent.mkdir(parents=True, exist_ok=True)
    up_im.save(out)
    return out


def upscale_start(url: str, want: int = 2, mid: str = '', cut: bool = False) -> dict:
    jid = f"ups_{uuid.uuid4().hex[:8]}"
    UPS_JOBS[jid] = {'status': 'pending', 'progress': 0.0}

    def run():
        try:
            p = APP / url.lstrip('/')
            out_p = APP / 'media' / f"{p.stem}-up4{p.suffix}"
            upscale_image(p, out_p, want=want, prog=lambda pr: UPS_JOBS[jid].update(progress=pr))
            UPS_JOBS[jid] = {'status': 'done', 'progress': 1.0, 'url': f"/media/{out_p.name}"}
        except Exception as e:
            UPS_JOBS[jid] = {'status': 'error', 'error': str(e)}

    threading.Thread(target=run, daemon=True).start()
    return {'jid': jid}


def out_dir() -> Path:
    p = Path(os.environ.get('VSP_OUT') or (_home() / 'xuat'))
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_side(name: str, body: bytes) -> dict:
    f = out_dir() / name
    f.write_bytes(body)
    return {'ok': True, 'path': str(f)}


def read_doc(b: bytes, name: str) -> dict:
    nl = name.lower()
    if nl.endswith('.txt'):
        return {'text': b.decode('utf-8-sig', 'ignore').strip()}
    if nl.endswith('.csv'):
        return {'text': b.decode('utf-8-sig', 'ignore').strip()}
    if nl.endswith('.docx'):
        try:
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                if 'word/document.xml' in z.namelist():
                    xml = z.read('word/document.xml').decode('utf-8', 'ignore')
                    txt = re.sub(r'<[^>]+>', ' ', xml)
                    txt = re.sub(r'\s+', ' ', txt).strip()
                    return {'text': txt}
        except Exception as e:
            raise RuntimeError(f"Lỗi đọc file Word: {e}")
    return {'text': ''}


def write_hooks(d: dict) -> dict:
    import media_ai
    M = _srv()
    llm = getattr(M, 'llm_mod', None)
    prompt = f"{HOOK_SYSTEM}\n\nNỘI DUNG VIDEO (JSON):\n{json.dumps(d, ensure_ascii=False)[:15000]}"
    r = media_ai.gemini_vision(HOOK_SYSTEM, prompt, [], log, llm)
    hooks = [str(x).strip() for x in r.get('hooks', []) if x]
    return {'hooks': hooks}


def handle_get(path: str, q: dict):
    if path.startswith('/api/license'):
        import ban_quyen
        return ban_quyen.handle_get(path, q)
    if path == '/api/ai/config':
        return ('json', ai_public())
    if path == '/api/brands':
        return ('json', {'brands': brands()})
    if path == '/api/series':
        return ('json', {'series': series_list()})
    if path == '/api/mcp/info':
        return ('json', mcp_info())
    if path == '/api/upscale/status':
        jid = q.get('jid', '')
        return ('json', UPS_JOBS.get(jid, {'status': 'not_found'}))
    return None


def handle_post_raw(path: str, q: dict, body: bytes):
    if path == '/api/parse_list':
        name = q.get('name', 'list.xlsx')
        return ('json', parse_list(body, name))
    if path == '/api/read_doc':
        name = q.get('name', 'doc.docx')
        return ('json', read_doc(body, name))
    return None


def handle_post(path: str, d: dict):
    if path.startswith('/api/license'):
        import ban_quyen
        return ban_quyen.handle_post(path, d)
    if path == '/api/ai/config':
        return ai_save(d)
    if path == '/api/brands/save':
        return brand_save(d)
    if path == '/api/brands/delete':
        return brand_delete(d.get('id', ''))
    if path == '/api/series/save':
        return series_save(d)
    if path == '/api/series/delete':
        return series_delete(d.get('id', ''))
    if path == '/api/upscale/start':
        return upscale_start(d.get('url', ''), d.get('want', 2), d.get('id', ''), d.get('cut', False))
    if path == '/api/write_hooks':
        return write_hooks(d)
    return None
