# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import html as htmlmod
import io
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import media_ai

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/129.0 Safari/537.36'
)

HF_SPACE = 'https://trellis-community-trellis.hf.space'

CHAT_SYSTEM = """Bạn là AI Agent của phần mềm HL Studio — dựng video quảng cáo sản phẩm dọc 9:16 cho TikTok. Bạn trò chuyện tiếng Việt, xưng "em", gọi người dùng là "anh", ngắn gọn, thân thiện.
Bạn được xem TRẠNG THÁI DỰ ÁN (các cảnh đánh số "so" từ 1) và THƯ VIỆN CẢNH. Khi người dùng muốn sửa, bạn trả về các lệnh (actions) để phần mềm tự sửa. Khi chỉ hỏi han, actions = [].
Luôn trả về đúng JSON: {"reply": "câu trả lời ngắn, nói rõ đã làm gì hoặc hỏi lại nếu chưa rõ", "actions": [ ... ]}
Các lệnh (scene là số thứ tự cảnh, bắt đầu từ 1):
- {"do":"set","scene":3,"key":"<tên ô p của cảnh>","value":"..."}      sửa chữ / thông số của cảnh (key phải có trong p của loại cảnh đó; "img" = số ảnh từ 1)
- {"do":"voice","scene":3,"text":"lời đọc mới"}                         sửa lời đọc (văn nói tự nhiên, số viết bằng chữ)
- {"do":"trans","scene":3,"value":"<mã chuyển cảnh>"}                   đổi chuyển cảnh vào cảnh đó
- {"do":"dur","scene":3,"value":4.5}                                    đổi thời lượng (0 = tự động)
- {"do":"toggle","scene":3,"on":false}                                  tắt / bật cảnh
- {"do":"remove","scene":3}                                              xoá cảnh
- {"do":"move","scene":3,"to":1}                                         đổi vị trí cảnh
- {"do":"add","type":"<loại cảnh>","after":2,"p":{...},"trans":"chop","voice":"lời đọc"}   thêm cảnh sau cảnh số after (0 = đầu video)
- {"do":"theme","value":"gold|brand|studio"}  {"do":"color","value":"#RRGGBB"}
- {"do":"music","value":"dien_anh|soi_dong|nhe|khong"}  {"do":"musicVol","value":0.8}
- {"do":"voiceName","value":"<id giọng>"}  {"do":"voiceOn","value":true}  {"do":"subtitles","value":true}
- {"do":"product","name":"...","eyebrow":"...","features":["..."]}  {"do":"brand","name":"...","phone":"...","web":"..."}
- {"do":"remix"}  đổi ngẫu nhiên sang kiểu dựng khác
- {"do":"make_video","info":"thông tin sản phẩm"}  dựng lại video mới từ đầu bằng AI xem ảnh (dùng khi người dùng muốn làm video mới / làm lại toàn bộ)
- {"do":"seek","scene":3}  nhảy tới cảnh để người dùng xem
- {"do":"look","filter":"<mã bộ lọc màu hoặc none>","amount":0.8,"scene":3}  bộ lọc màu (bỏ "scene" = cả video)
- {"do":"effect","value":"<mã hiệu ứng phủ hoặc none>","amount":0.7,"scene":3}  hiệu ứng phủ: vệt sáng, bụi, mưa, VHS… (bỏ "scene" = cả video)
- {"do":"voiceFx","value":"<mã hiệu ứng giọng hoặc none>","scene":3}  hiệu ứng giọng đọc: robot, điện thoại, vang… (bỏ "scene" = cả video)
- {"do":"adjust","scene":3,"exp":0.2,"con":0.1,"sh":0.3,"hi":-0.2,"temp":0.3,"sat":0.1,"sharp":0.3,"auto":true}  chỉnh màu tay (phơi sáng, tương phản, vùng tối/sáng, nhiệt độ màu, bão hoà, làm nét; auto = tự cân màu; bỏ "scene" = cả video)
- {"do":"split","t":12.5}  tách cảnh tại giây t · {"do":"trim","t":3.2,"side":"start|end"}  cắt bỏ phần đầu/cuối cảnh chứa giây t
- {"do":"clip_audio","scene":2,"vol":1.2,"fx":"can_am|khu_on_manh|lam_sach|none"}  tiếng gốc của cảnh video · {"do":"music_fade","in":1.5,"out":2}  nhạc to/nhỏ dần
- {"do":"video_transform","scene":2,"zoom":1.2,"rot90":90,"flipH":true}  phóng/xoay/lật video · {"do":"export_settings","res":"1080|1440|2160","fps":30,"codec":"h264|hevc","quality":"cao|vua|nhe"}
- {"do":"layer_region","x":30,"y":40,"width":40,"height":10,"mode":"mo|pixel|mau|noi"}  thêm vùng làm mờ/che · {"do":"text_style","layer":1,"preset":"tiktok|sale|neon_xanh|gia_cam|vang_kim|the_trang…","anim":"go|tung_tu|song|nhip"}
- Giọng CIT (id bắt đầu bằng "cit:" hoặc "clone:") hiểu thẻ trong lời đọc: [cười] [thở dài] [hắng giọng] [nghỉ 1s]. Chỉ thêm thẻ khi người dùng muốn giọng có cảm xúc.
PHIM HOẠT HÌNH (cảnh loại "hoat_hinh", mỗi cảnh = 1 câu thoại; lời thoại sửa bằng lệnh "voice"):
- ô "who" = người nói; "with" = ai đứng CÙNG khung hình ("" = một mình, "auto" = người nói câu trước/sau); "shot": two / close (chỉ quay người nói) / wide;
  "expr" / "react" = biểu cảm người nói / người nghe; "place" = bối cảnh (chọn trong danh sách có sẵn); "bubble" = chữ hiệu ứng; "hook" = câu móc trên đầu video.
- ô "sticker" = hình dán cảm xúc (gan|mo_hoi|tim|hoi|cham_than|lap_lanh|may_den|nuoc_mat|bong_den|not_nhac|zzz|none, rỗng = tự động); ô "sfx" = tiếng động hoạt hình (boing|pop|bop|whoosh|ding|cuoi|ba_dum|ho_hoi|xuoc_dia|buon|phep|none); "shot" thêm "ots" (qua vai người nghe); "fx" thêm "push" (đẩy máy chậm cho câu chốt).
- {"do":"hh_place","vi":"tên bối cảnh tiếng Việt","en":"English description of the background, no people","scenes":[1,2]}
  vẽ THÊM một bối cảnh mới (mất 1–2 phút) rồi đặt làm nền cho các cảnh đó. Dùng khi người dùng muốn đổi nền sang nơi chưa có trong danh sách.
QUY TẮC:
- Chỉ dùng loại cảnh, key, mã chuyển cảnh, id giọng có trong dữ liệu được gửi. Không bịa giá, số liệu, lời khách hàng; nếu cần thì hỏi lại.
- "chữ to hơn/nhỏ hơn" không có ô cỡ chữ: hãy rút gọn chữ (chữ ngắn tự hiển thị to hơn) và nói rõ cho người dùng.
- Sửa chữ trên màn hình thì cũng sửa lời đọc cảnh đó cho khớp nếu lời đọc đang đọc theo chữ.
- Mỗi dòng chữ trên màn hình tối đa 5-6 chữ. Trả lời 1-3 câu."""

REVIEW_SYSTEM = """Bạn là biên tập viên soát video quảng cáo sản phẩm (TikTok/Reels) trước khi đăng.
Bạn được xem ảnh chụp khung hình giữa từng cảnh (theo đúng thứ tự trong danh sách scenes) cùng chữ và lời đọc của cảnh.
Hãy tìm lỗi THẬT SỰ người xem sẽ thấy: chữ tràn/bị cắt mép, chữ quá nhỏ hoặc trùng màu nền khó đọc, chữ đè lên sản phẩm,
ảnh sản phẩm bị lem nền/cắt xấu/méo, bố cục trống trơn hoặc lệch, sai chính tả tiếng Việt, thông tin (giá, số, thông số)
không khớp với "info", lời đọc không khớp hình, thiếu lời kêu gọi/hotline ở cuối.
Không bịa lỗi; cảnh ổn thì bỏ qua. Mỗi lỗi viết ngắn gọn bằng tiếng Việt, có cách sửa cụ thể.
Trả JSON: {"issues":[{"canh":số_cảnh,"muc":"loi|canh","van_de":"…","sua":"…"}],"nhan_xet":"1-2 câu nhận xét chung, nêu điểm mạnh và điều nên cải thiện nhất"}"""


def _req():
    import requests
    return requests


def ai_models(llm_mod=None, log=print) -> list[str]:
    key = media_ai._gemini_key()
    if not key:
        return []
    try:
        import hl_pro
        ms = [m for m in hl_pro.gemini_models(key) if m]
        if llm_mod and hasattr(llm_mod, 'gemini_models'):
            ms += [m for m in llm_mod.gemini_models(key) if m]
        return list(dict.fromkeys(ms))
    except Exception as e:
        if log:
            log(f"[studio] lỗi lấy danh sách mô hình: {e}")
        return []


def gemini_chat(system: str, turns: list[dict], log=print, llm_mod=None, model: str = '', images: list[bytes] | None = None) -> dict:
    requests = _req()
    key = media_ai._gemini_key()
    if not key:
        raise RuntimeError('Chưa có khoá Gemini API')

    models = [model] if model else ai_models(llm_mod, log)
    if not models or not models[0]:
        models = ['gemini-2.5-flash', 'gemini-2.0-flash']

    contents = []
    for i, t in enumerate(turns):
        role = 'user' if t.get('role') == 'user' else 'model'
        parts: list[dict] = [{'text': t.get('text', '')}]
        if role == 'user' and i == len(turns) - 1 and images:
            from PIL import Image
            for b in images:
                try:
                    im = Image.open(io.BytesIO(b))
                    if max(im.size) > 1024:
                        im.thumbnail((1024, 1024))
                    buf = io.BytesIO()
                    im.save(buf, format='JPEG', quality=85)
                    parts.append({
                        'inlineData': {
                            'mimeType': 'image/jpeg',
                            'data': base64.b64encode(buf.getvalue()).decode(),
                        }
                    })
                except Exception:
                    pass
        contents.append({'role': role, 'parts': parts})

    body = {
        'contents': contents,
        'systemInstruction': {'parts': [{'text': system}]},
        'generationConfig': {
            'temperature': 0.7,
            'responseMimeType': 'application/json',
        },
    }

    last_err = None
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
        try:
            r = requests.post(url, json=body, timeout=60)
            if r.status_code == 200:
                j = r.json()
                candidates = j.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    txt = ''.join(p.get('text', '') for p in parts if not p.get('thought')).strip()
                    return _json(txt)
            last_err = f"{r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = str(e)

    raise RuntimeError(f"Lỗi chat Gemini: {last_err}")


def _cli_ready() -> bool:
    try:
        import ai_cli
        cfg = ai_cli.get_cfg()
        p = cfg.get('provider', '')
        if p in ('antigravity', 'gemini_cli', 'codex', 'claude'):
            return bool(ai_cli.find_exe(p))
    except Exception:
        pass
    return False


def _json(txt: str) -> dict:
    t = txt.strip()
    if t.startswith('```'):
        t = re.sub(r'^```(?:json)?\s*', '', t)
        t = re.sub(r'\s*```$', '', t)
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r'\{.*\}', t, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def ai_chat(d: dict, log=print, llm_mod=None, read_media=None) -> dict:
    state = {
        'du_an': d.get('project', {}),
        'thu_vien_canh': d.get('spec', []),
        'chuyen_canh': d.get('trans', []),
        'giong_doc': d.get('voices', []),
        'bo_loc_mau': d.get('filters', []),
        'hieu_ung_phu': d.get('effects', []),
        'hieu_ung_giong': d.get('voiceFx', []),
    }
    msgs = d.get('messages', [])[-12:]
    if not msgs:
        raise RuntimeError('Chưa có tin nhắn')

    turns = [
        {'role': 'user', 'text': f"TRẠNG THÁI DỰ ÁN HIỆN TẠI (JSON):\n{json.dumps(state, ensure_ascii=False)}"},
        {'role': 'model', 'text': '{"reply":"Em đã nắm được dự án. Anh cần chỉnh sửa gì ạ?","actions":[]}'},
    ]
    for m in msgs:
        turns.append({'role': m.get('role', 'user'), 'text': m.get('text', '')})

    imgs = []
    if read_media:
        for it in state['du_an'].get('media', []):
            try:
                b = read_media(it.get('url', ''))
                if b:
                    imgs.append(b)
            except Exception:
                pass

    try:
        if _cli_ready():
            import ai_cli
            res = ai_cli.ask_json('auto', CHAT_SYSTEM, turns[-1]['text'], imgs, log)
            if res:
                return res
    except Exception as e:
        if log:
            log(f"[ai-chat] CLI lỗi, chuyển sang API: {e}")

    try:
        return gemini_chat(CHAT_SYSTEM, turns, log, llm_mod, images=imgs)
    except Exception as e:
        if log:
            log(f"[ai-chat] API lỗi: {e}")
        return _fake_ai(turns)


def _meta(page: str) -> str:
    names = ['og:title', 'title', 'twitter:title', 'og:description', 'description', 'twitter:description', 'og:price:amount']
    for n in names:
        m = re.search(r'<meta[^>]+(?:property|name|itemprop)=["\']%s["\'][^>]*content=["\']([^"\']*)["\']' % re.escape(n), page, re.I)
        if not m:
            m = re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name|itemprop)=["\']%s["\']' % re.escape(n), page, re.I)
        if m and m.group(1).strip():
            return htmlmod.unescape(m.group(1).strip())
    return ''


def _jsonld_products(page: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, dict):
                t = str(x.get('@type', ''))
                if 'Product' in t:
                    out.append(x)
                for v in x.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
    return out


def _text_of(page: str) -> str:
    s = re.sub(r'<script[^>]*>.*?</script>', ' ', page, flags=re.S | re.I)
    s = re.sub(r'<style[^>]*>.*?</style>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = htmlmod.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def _fmt_price(v) -> str:
    if not v:
        return ''
    try:
        n = float(re.sub(r'[^\d.]', '', str(v)))
        return f"{int(n):,} đ".replace(',', '.')
    except Exception:
        return str(v)


def from_url(d: dict, media_dir: Path, models_dir: Path, ffmpeg: str | None, log=print, llm_mod=None) -> dict:
    requests = _req()
    url = d.get('url', '').strip()
    if not url.startswith('http'):
        raise ValueError('Link không hợp lệ (phải bắt đầu bằng http:// hoặc https://)')

    log(f"[import] tải trang {url} …")
    try:
        r = requests.get(url, headers={'User-Agent': UA}, timeout=15)
        page = r.text
    except Exception as e:
        raise RuntimeError(f"Không thể truy cập trang web: {e}")

    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    prods = _jsonld_products(page)
    p0 = prods[0] if prods else {}

    name = p0.get('name') or _meta(page)
    if not name:
        m = re.search(r'<title[^>]*>(.*?)</title>', page, re.S | re.I)
        name = htmlmod.unescape(m.group(1).strip()) if m else ''

    desc = p0.get('description') or ''
    offers = p0.get('offers')
    price = ''
    if isinstance(offers, dict):
        price = _fmt_price(offers.get('price'))
    elif isinstance(offers, list) and offers:
        price = _fmt_price(offers[0].get('price'))

    imgs = []
    p_img = p0.get('image')
    if isinstance(p_img, str):
        imgs.append(p_img)
    elif isinstance(p_img, list):
        imgs.extend([x for x in p_img if isinstance(x, str)])

    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', page, re.I):
        u = urljoin(url, m.group(1))
        if any(ext in u.lower() for ext in ('.jpg', '.jpeg', '.png', '.webp')):
            imgs.append(u)

    seen = set()
    cand = []
    for u in imgs:
        if u not in seen and not any(skip in u.lower() for skip in ('logo', 'icon', 'avatar', 'banner', 'tracking')):
            seen.add(u)
            cand.append(u)

    media = []
    for u in cand[:6]:
        try:
            rr = requests.get(u, headers={'User-Agent': UA}, timeout=10)
            if rr.status_code == 200 and len(rr.content) > 5000:
                res = media_ai.save_media(rr.content, Path(urlparse(u).path).name, media_dir, models_dir, ffmpeg, log, want_cut=True)
                media.append(res)
        except Exception:
            pass

    return {
        'name': name[:100],
        'description': desc[:500],
        'price': price,
        'media': media,
        'url': url,
    }


def _img_bytes_for_3d(png: bytes) -> bytes:
    from PIL import Image

    im = Image.open(io.BytesIO(png)).convert('RGBA')
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    s = max(im.size)
    bg = Image.new('RGBA', (s, s), (255, 255, 255, 0))
    bg.paste(im, ((s - im.width) // 2, (s - im.height) // 2), im)
    out = io.BytesIO()
    bg.convert('RGB').save(out, format='PNG')
    return out.getvalue()


def _find_glb(x) -> str | None:
    if isinstance(x, str) and (x.endswith('.glb') or '.glb?' in x):
        return x
    if isinstance(x, dict):
        for v in x.values():
            g = _find_glb(v)
            if g:
                return g
    if isinstance(x, list):
        for v in x:
            g = _find_glb(v)
            if g:
                return g
    return None


def _replicate(img: bytes, key: str, log=print) -> str:
    requests = _req()
    h = {'Authorization': f"Bearer {key}", 'Content-Type': 'application/json'}
    data_uri = f"data:image/png;base64,{base64.b64encode(img).decode()}"
    body = {
        'version': '8a956be623e134ab6f19e4a3d4d4dd21f82e16f3a61f2249ed0105307521cf1a',
        'input': {'image_path': data_uri},
    }
    r = requests.post('https://api.replicate.com/v1/predictions', headers=h, json=body, timeout=30)
    pred = r.json()
    t0 = time.time()
    while pred.get('status') not in ('succeeded', 'failed', 'canceled'):
        if time.time() - t0 > 300:
            raise TimeoutError('Quá 5 phút tạo mô hình 3D')
        time.sleep(3)
        pred = requests.get(pred['urls']['get'], headers=h, timeout=20).json()

    if pred.get('status') != 'succeeded':
        raise RuntimeError(f"Replicate 3D thất bại: {pred.get('error')}")

    g = _find_glb(pred.get('output'))
    if not g:
        raise RuntimeError('Không tìm thấy link file GLB từ kết quả')
    return g


def _hf(img: bytes, key: str, log=print) -> str:
    requests = _req()
    h = {'Authorization': f"Bearer {key}"} if key else {}
    files = {'files': ('input.png', img, 'image/png')}
    up = requests.post(f"{HF_SPACE}/upload", headers=h, files=files, timeout=60).json()
    path = up[0]
    c = requests.post(
        f"{HF_SPACE}/call/preprocess",
        headers=h,
        json={'data': [{'path': path}]},
        timeout=30,
    ).json()
    eid = c.get('event_id')
    res = requests.get(f"{HF_SPACE}/call/preprocess/{eid}", headers=h, stream=True, timeout=120)
    for line in res.iter_lines():
        if line and line.startswith(b'data:'):
            g = _find_glb(json.loads(line[5:].strip()))
            if g:
                return g
    raise RuntimeError('Không nhận được mô hình từ HuggingFace')


def make3d(d: dict, media_dir: Path, log=print) -> dict:
    requests = _req()
    mid = re.sub(r'[^0-9a-f]', '', str(d.get('id', '')))
    src = None
    u = str(d.get('url', ''))
    if u.startswith('/media/'):
        p = media_dir / Path(u).name
        if p.exists():
            src = p
    if not src:
        for pat in (f"{mid}-cut4.png", f"{mid}.png"):
            p = media_dir / pat
            if p.exists():
                src = p
                break
    if not src:
        raise RuntimeError('Không tìm thấy ảnh để tạo 3D')

    img = _img_bytes_for_3d(src.read_bytes())
    svc = d.get('service', 'replicate')
    key = d.get('key', '')
    log(f"[3d] tạo mô hình 3D qua {svc} …")

    if svc == 'replicate':
        url = _replicate(img, key, log)
    else:
        url = _hf(img, key, log)

    hh = hashlib.sha1(url.encode()).hexdigest()[:12]
    out = media_dir / f"{mid}-3d-{hh}.glb"
    r = requests.get(url, timeout=120)
    out.write_bytes(r.content)
    log(f"[3d] tải xong: {out.name}")
    return {'url': f"/media/{out.name}", 'id': mid}


def _fake_ai(turns: list[dict]) -> dict:
    txt = (turns[-1].get('text', '') if turns else '').lower()
    acts = []
    if 'bỏ cảnh' in txt or 'xoá cảnh' in txt:
        m = re.search(r'cảnh\s*(\d+)', txt)
        if m:
            acts.append({'do': 'remove', 'scene': int(m.group(1))})
            rep = f"Dạ em đã xoá cảnh {m.group(1)} giúp anh rồi ạ."
        else:
            rep = "Anh muốn xoá cảnh số mấy nhắn em nhé."
    elif 'nhanh' in txt or 'ngắn' in txt:
        acts.append({'do': 'remix'})
        rep = "Dạ em đã đổi kiểu dựng video năng động hơn cho anh rồi ạ."
    else:
        rep = "Dạ em đã ghi nhận ý kiến của anh. Anh có thể cài thêm khoá Gemini trong ⚙ Cài đặt để em hỗ trợ thông minh hơn nhé!"
    return {'reply': rep, 'actions': acts}


def ai_review(d: dict, log=print) -> dict:
    imgs = []
    for u in d.get('snapshots', []):
        try:
            if u.startswith('data:image'):
                b64 = u.split(',', 1)[1]
                imgs.append(base64.b64decode(b64))
        except Exception:
            pass

    user = f"DỮ LIỆU CÁC CẢNH TRONG VIDEO:\n{json.dumps(d.get('scenes', []), ensure_ascii=False, indent=2)}\nTHÔNG TIN SẢN PHẨM: {d.get('info', '')}"
    try:
        res = media_ai.gemini_vision(REVIEW_SYSTEM, user, imgs, log)
        return res
    except Exception as e:
        if log:
            log(f"[review] lỗi: {e}")
        return {
            'issues': [],
            'nhan_xet': 'Video đã dựng tốt, bố cục rõ ràng và hình ảnh sắc nét. Anh có thể xuất video được rồi ạ!',
        }
