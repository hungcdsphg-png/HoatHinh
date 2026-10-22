from __future__ import annotations
import base64
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXPRS = ['neutral', 'talk', 'laugh', 'smirk', 'angry', 'shock', 'sad', 'happy', 'blink', 'talk2']
LINE_EXPRS = EXPRS[:8]
STICKERS = ['', 'gan', 'mo_hoi', 'tim', 'hoi', 'cham_than', 'lap_lanh', 'may_den', 'nuoc_mat', 'bong_den', 'not_nhac', 'zzz']
SFXS = ['', 'boing', 'pop', 'bop', 'whoosh', 'ding', 'cuoi', 'ba_dum', 'ho_hoi', 'xuoc_dia', 'buon', 'phep']
VFX_CHAR = ['', 'chuot_chip', 'tram', 'robot', 'am_ap', 'dien_thoai', 'thi_tham']

EXPR_EN = {
    'neutral': 'calm neutral face, mouth closed',
    'talk': 'talking normally, mouth open mid-word',
    'laugh': 'laughing hard, eyes squeezed shut into arcs, big open mouth',
    'smirk': 'smug side-eye glance with a sly half smile',
    'angry': 'angry shouting, furrowed brows, wide open mouth, vein mark on forehead',
    'shock': 'shocked, eyes wide and tiny pupils, jaw dropped',
    'sad': 'sad and teary, wobbly frown',
    'happy': 'big happy grin, eyes curved, blushing cheeks',
    'blink': 'calm neutral face with BOTH EYES CLOSED (blinking), mouth closed, otherwise identical to panel 1',
    'talk2': 'talking loudly, mouth opened WIDE in an O shape, otherwise identical to panel 1',
}

STYLE = 'Cute chibi 2D cartoon in the style of popular Vietnamese TikTok comedy animations: thick clean dark-brown outlines, flat bright colors, soft cel shading, oversized heads, big expressive faces, simple shapes, crisp vector-like look.'
NO_TEXT = 'Absolutely no text, letters, numbers, speech bubbles, captions, logos, signatures or watermarks.'

JOBS: dict = {}
_AGY_LOCK = threading.Lock()
_SEEN: set = set()
CUR = threading.local()

SYSTEM = """Bạn là biên kịch tiểu phẩm hoạt hình chibi hài ngắn tiếng Việt cho TikTok/Reels (kiểu các kênh hoạt hình đời thường: 2 nhân vật cà khịa nhau, cắt cảnh qua lại).
Viết theo nhịp có MỞ BÀI – THÂN BÀI – KẾT BÀI rõ ràng: MỞ BÀI (1–2 câu đầu) giới thiệu ai, ở đâu, chuyện gì + móc câu tò mò → THÂN BÀI tình huống/mâu thuẫn leo thang → KẾT BÀI: CÚ CHỐT bất ngờ, hài hoặc ấm lòng rồi 1 câu khép lại trọn vẹn (không bỏ lửng, không cắt ngang).
"title" là tên tập hấp dẫn ≤ 8 chữ (hiện ở thẻ mở đầu), "hook" là câu móc ≤ 10 chữ (hiện dưới tên tập).
Lời thoại NGẮN (mỗi câu 3–16 chữ), đời thường, tự nhiên như người Việt nói chuyện; mỗi câu một người nói.
Nhân vật là nhân vật RIÊNG (không dùng nhân vật phim/truyện có bản quyền, không người nổi tiếng).
Nếu có thông tin sản phẩm/thương hiệu: lồng khéo vào câu chuyện (không quảng cáo lộ liễu), chỉ dùng thông tin được cung cấp, KHÔNG bịa giá.
Trả về DUY NHẤT JSON:
{"title":"tên tập ngắn","hook":"câu móc in trên đầu video (≤ 10 chữ)","seconds":40,
 "places":[{"id":"p1","vi":"bối cảnh tiếng Việt","en":"background description in English, no people"}],
 "characters":[{"id":"a","name":"tên gọi","gender":"male|female","age":"child|teen|adult|elder",
   "look":"English description: hair, face, outfit colors, accessories (distinctive, consistent)","side":"left|right"}],
 "lines":[{"who":"a","text":"lời thoại","expr":"neutral|laugh|smirk|angry|shock|sad|happy","react":"biểu cảm người nghe (cùng danh sách)",
   "shot":"two|close|wide","fx":"none|zoom|shake|speed","bubble":"chữ hiệu ứng ngắn kiểu truyện tranh, ≤ 4 chữ, hoặc rỗng",
   "place":"p1","with":"id nhân vật đang đứng CÙNG khung hình với người nói (người đang nghe); nhiều người cùng có mặt thì ghi danh sách id [\"b\",\"c\"] (tối đa 3); rỗng nếu chỉ một mình",
   "sticker":"hình dán cảm xúc trên đầu người nói: gan|mo_hoi|tim|hoi|cham_than|lap_lanh|may_den|nuoc_mat|bong_den|not_nhac|zzz hoặc rỗng",
   "sfx":"tiếng động hoạt hình: boing|pop|bop|whoosh|ding|cuoi|ba_dum|ho_hoi|xuoc_dia|buon|phep hoặc rỗng"}]}
Mỗi nhân vật thêm "voicefx": hiệu ứng giọng hợp vai (chuot_chip cho trẻ nhỏ/thú cưng/nhân vật lém lỉnh, tram cho ông chủ/kẻ xấu, rỗng = giọng thường).
Mỗi bối cảnh thêm "weather": mua|tuyet|bui_roi|none (ngoài trời mưa/tuyết, căn phòng nắng có bụi sáng) và "mood": vui|buon|cang|dem|binh_thuong.
STICKER/SFX: khoảng 50–60% số câu, đúng cảm xúc (tức → gan, lo/ngượng → mo_hoi, thương → tim, thắc mắc → hoi, bất ngờ → cham_than, có ý hay → bong_den, buồn → may_den).
Câu chốt hài cuối dùng sfx "ba_dum" hoặc "cuoi"; câu thất bại dùng "buon"; câu bất ngờ dùng "xuoc_dia" hoặc "ho_hoi".
CẢNH ĐÔNG NGƯỜI (3+ nhân vật cùng có mặt): dùng shot "wide" và ghi đủ "with".
BỐI CẢNH: LUÔN NHIỀU BỐI CẢNH cho phim đỡ chán, kể cả phim ngắn: ≤ 8 câu thoại → 2–3 bối cảnh; 9–16 câu → 3–4; 17–30 câu → 4–5; dài hơn → 5–6.
Câu chuyện DI CHUYỂN qua các nơi (VD: trên đường đi học → cổng trường → trong lớp → căng tin), hoặc nếu chỉ ở một nơi thì chia thành các GÓC KHÁC NHAU của nơi đó (quầy nước, bàn ăn, góc bếp, ngoài cửa…), mỗi góc là 1 bối cảnh riêng có mô tả "en" khác hẳn nhau.
Đổi bối cảnh sau mỗi 3–5 câu thoại; mỗi câu thoại ghi "place" đúng nơi đang diễn ra; "en" mô tả rõ không gian rộng có tiền cảnh/hậu cảnh, nền đất/sàn ở nửa dưới, KHÔNG có người.
NHÂN VẬT TRONG KHUNG: "with" chỉ là người THẬT SỰ có mặt và đang nói chuyện với người nói ở câu đó. Nhân vật chưa xuất hiện / không có mặt ở nơi đó thì KHÔNG được đưa vào (VD hai anh em trốn học trên đường thì mẹ không có mặt).
Quy tắc góc máy: câu đầu "two" hoặc "close"; câu cảm xúc mạnh (cười to, quát, sốc) dùng "close" + fx "zoom"/"shake"/"speed"; xen kẽ, không quá 2 câu liền cùng góc.
bubble chỉ dùng cho 30–40% số câu, lúc cao trào (VD "CƯỜI NỮA!!", "HẢ???", "Ê!!", "Ủa?").
Số câu thoại ≈ số giây / 2.6."""

ANGLES = [
    ('góc khác', 'another corner of the same place, different camera angle, different furniture and props in view'),
    ('phía ngoài', 'the entrance / just outside of the same place, wide view'),
    ('cận cảnh', 'a closer, cozier part of the same place with detailed props'),
    ('phía đối diện', 'the opposite side of the same place, seen from the other direction'),
    ('toàn cảnh', 'wide establishing view of the whole place from a slightly high angle'),
]

def _more_places(places: list, lines: list) -> None:
    n = len(lines)
    if n < 8:
        need = 2
    elif n < 14:
        need = 3
    elif n < 22:
        need = 4
    else:
        need = 5
    used = {}
    for ln in lines:
        used.setdefault(ln['place'], 0)
        used[ln['place']] += 1
    k = 0
    while len(places) < min(6, need) and used:
        pid = max(used, key=lambda x: used[x])
        if used[pid] < 4:
            return
        base = next(p for p in places if p['id'] == pid)
        base = next((p for p in places if p['id'] == base.get('root')), base)
        vi, en = ANGLES[k % len(ANGLES)]
        k += 1
        nid = f"{base['id']}g{k}"
        places.append({
            'id': nid,
            'vi': f"{base['vi']} ({vi})"[:80],
            'en': f"{base['en']}, {en}"[:400],
            'weather': base.get('weather', ''),
            'mood': base.get('mood', ''),
            'root': base['id'],
        })
        idx = [i for i, ln in enumerate(lines) if ln['place'] == pid]
        half = idx[:len(idx) // 2]
        for i in half:
            lines[i]['place'] = nid
        used[pid] = len(idx) - len(half)
        used[nid] = len(half)

def write_script(d: dict, vision, log, llm_mod=None) -> dict:
    topic = str(d.get('topic', '')).strip()
    if len(topic) < 3:
        raise RuntimeError('Anh gõ ý tưởng / chủ đề tiểu phẩm trước nhé')
    secs = int(d.get('seconds', 0) or 0)
    secs = 0 if secs <= 0 else max(15, min(180, secs))
    n = int(d.get('chars', 0) or 0)
    n = 0 if n <= 0 else min(6, n)
    info = str(d.get('info', '')).strip()[:1200]
    len_txt = f'Độ dài ≈ {secs} giây ({max(4, round(secs / 2.6))} câu thoại).' if secs else 'Độ dài: BẠN TỰ QUYẾT cho vừa câu chuyện (thường 20–90 giây, tối đa 180 giây), số câu thoại ≈ số giây / 2.6; ghi vào "seconds".'
    n_txt = f'Số nhân vật: {n}.' if n else 'Số nhân vật: BẠN TỰ QUYẾT theo câu chuyện (1–6). Chỉ thêm nhân vật khi câu chuyện thật sự cần; ít nhân vật thì dễ theo dõi và vẽ nhanh hơn.'
    user = f'Ý tưởng: {topic}\n{len_txt} {n_txt}\n'
    if info:
        user += f'Thông tin sản phẩm/thương hiệu (chỉ dùng nếu hợp): {info}\n'
    if d.get('notes'):
        user += f"Dặn thêm: {d.get('notes')}\n"
    ser = d.get('series') or {}
    if ser.get('chars'):
        user += '\nPHIM BỘ — đây là TẬP TIẾP THEO. DÙNG LẠI đúng các nhân vật sau (giữ nguyên id, name, gender, age, look, side, voicefx): '
        user += json.dumps(ser['chars'], ensure_ascii=False)
        user += '\nCó thể thêm tối đa 2 nhân vật mới (id mới, khác các id trên) nếu câu chuyện thật sự cần; không bắt buộc dùng hết nhân vật cũ.'
        if ser.get('places'):
            user += '\nBối cảnh đã có (dùng lại thì giữ nguyên id và en): ' + json.dumps(ser.get('places') or [], ensure_ascii=False) + '\nĐược thêm bối cảnh mới (id mới) nếu câu chuyện đi tới nơi khác.'
        user += '\n'
    r = vision(SYSTEM, user, [], log, llm_mod)
    if isinstance(r, str):
        r = json.loads(re.search(r'\{.*\}', r, re.S).group(0))
    out = clean(r)
    if ser.get('chars'):
        old = {c['id']: c for c in ser['chars'] if isinstance(c, dict) and c.get('id')}
        for c in out['characters']:
            if c['id'] in old:
                c.update({k: v for k, v in old[c['id']].items() if k in ('name', 'gender', 'age', 'look', 'side', 'voicefx', 'voice') and v})
        oldp = {p['id']: p for p in (ser.get('places') or []) if isinstance(p, dict) and p.get('id')}
        for p in out['places']:
            if p['id'] in oldp:
                p.update({k: v for k, v in oldp[p['id']].items() if k in ('vi', 'en', 'weather', 'mood') and v})
    return out

def clean(r: dict) -> dict:
    chars = [c for c in (r.get('characters') or []) if isinstance(c, dict)][:6]
    if not chars:
        raise RuntimeError('AI chưa trả nhân vật, anh bấm viết lại')
    ids = []
    for i, c in enumerate(chars):
        cid = re.sub(r'[^a-z0-9]', '', str(c.get('id') or '')).lower() or f'nv{i + 1}'
        c['id'] = cid
        if c['id'] in ids:
            c['id'] = c['id'] + str(i)
        ids.append(c['id'])
        c['gender'] = 'female' if str(c.get('gender', '')).lower().startswith('f') else 'male'
        c['side'] = c.get('side') if c.get('side') in ('left', 'right') else ('left' if i % 2 == 0 else 'right')
        c['name'] = str(c.get('name') or f'Nhân vật {i + 1}')[:24]
        c['look'] = str(c.get('look') or '')[:400]
        c['voicefx'] = c.get('voicefx') if c.get('voicefx') in VFX_CHAR else ''
    lines = []
    for ln in (r.get('lines') or []):
        if not isinstance(ln, dict):
            continue
        if not str(ln.get('text', '')).strip():
            continue
        who = ln.get('who') if ln.get('who') in ids else ids[len(lines) % len(ids)]
        ex = ln.get('expr') if ln.get('expr') in LINE_EXPRS else 'neutral'
        re_ = ln.get('react') if ln.get('react') in LINE_EXPRS else 'neutral'
        w0 = ln.get('with')
        if isinstance(w0, list):
            w0 = w0
        else:
            w0 = [x.strip() for x in str(w0 or '').split(',')]
        wi = ','.join([x for x in dict.fromkeys(w0) if x in ids and x != who][:3])
        lines.append({
            'who': who,
            'with': wi,
            'place': str(ln.get('place') or ''),
            'text': str(ln['text']).strip()[:160],
            'expr': 'neutral' if ex == 'talk' else ex,
            'react': 'neutral' if re_ == 'talk' else re_,
            'shot': ln.get('shot') if ln.get('shot') in ('two', 'close', 'wide') else 'two',
            'fx': ln.get('fx') if ln.get('fx') in ('none', 'zoom', 'shake', 'speed') else 'none',
            'bubble': str(ln.get('bubble') or '')[:24],
            'sticker': ln.get('sticker') if ln.get('sticker') in STICKERS else '',
            'sfx': ln.get('sfx') if ln.get('sfx') in SFXS else '',
        })
    if len(lines) < 2:
        raise RuntimeError('AI viết chưa đủ câu thoại, anh bấm viết lại')
    st = r.get('setting') or {}
    if isinstance(st, str):
        st = {'vi': st, 'en': st}
    places = []
    for i, pl in enumerate((r.get('places') or [])[:6]):
        if isinstance(pl, dict) and (pl.get('en') or pl.get('vi')):
            places.append({
                'id': re.sub(r'[^a-z0-9]', '', str(pl.get('id') or '')).lower() or f'p{i + 1}',
                'vi': str(pl.get('vi') or pl.get('en'))[:80],
                'en': str(pl.get('en') or pl.get('vi'))[:400],
                'weather': pl.get('weather') if pl.get('weather') in ('mua', 'tuyet', 'bui_roi') else '',
                'mood': pl.get('mood') if pl.get('mood') in ('vui', 'buon', 'cang', 'dem') else '',
            })
    if not places:
        places = [{'id': 'p1', 'vi': str(st.get('vi') or 'Bối cảnh'), 'en': str(st.get('en') or st.get('vi') or 'a simple cozy room')}]
    pids = [p['id'] for p in places]
    for ln in lines:
        if ln['place'] not in pids:
            ln['place'] = pids[0]
    _more_places(places, lines)
    try:
        s0 = int(float(r.get('seconds') or 0))
        sec = max(10, min(180, s0)) if s0 else round(len(lines) * 2.6)
    except Exception:
        sec = round(len(lines) * 2.6)
    return {
        'title': str(r.get('title') or 'Tiểu phẩm')[:80],
        'hook': str(r.get('hook') or '')[:60],
        'seconds': sec,
        'setting': {'vi': str(st.get('vi') or ''), 'en': str(st.get('en') or st.get('vi') or 'a simple cozy room')},
        'places': places,
        'characters': chars,
        'lines': lines,
    }

def _gemini_image(prompt: str, refs: list[bytes], aspect: str) -> bytes:
    import requests
    import media_ai
    key = media_ai._gemini_key()
    if not key:
        raise RuntimeError('Chưa có API key Gemini (⚙ Cài đặt › AI & MCP)')
    models = []
    try:
        import hl_pro
        if hl_pro.ai_cfg().get('gemini_image_model'):
            models.append(hl_pro.ai_cfg()['gemini_image_model'])
    except Exception:
        pass
    try:
        import vbt_common
        forced = vbt_common.get_setting('GEMINI_IMAGE_MODEL')
        if forced:
            models.append(forced)
    except Exception:
        pass
    try:
        rr = requests.get('https://generativelanguage.googleapis.com/v1beta/models', params={'pageSize': 200}, headers={'x-goog-api-key': key}, timeout=20)
        if rr.ok:
            found = [m['name'].split('/')[-1] for m in rr.json().get('models', []) if 'image' in m.get('name', '') and m['name'].split('/')[-1].startswith('gemini')]
            found.sort(key=lambda n: ('preview' not in n, 'flash' in n, [int(x) for x in re.findall(r'\d+', n)[:3]]), reverse=True)
            models += [m for m in found if m not in models]
    except Exception:
        pass
    models = models or ['gemini-2.5-flash-image']
    parts = [{'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(b).decode()}} for b in refs]
    parts.append({'text': prompt})
    body = {
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {'responseModalities': ['IMAGE'], 'imageConfig': {'aspectRatio': aspect}},
    }
    last = ''
    for model in models[:3]:
        for attempt in range(3):
            try:
                r = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                    headers={'x-goog-api-key': key, 'Content-Type': 'application/json'},
                    json=body, timeout=(15, 150)
                )
            except requests.RequestException as e:
                last = f'{model}: {e.__class__.__name__}'
                break
            if r.ok:
                b64 = _find_b64(r.json())
                if b64:
                    return base64.b64decode(b64)
                last = f'{model}: không trả ảnh'
                break
            last = f'{model}: {r.status_code} {r.text[:160]}'
            if r.status_code == 429:
                if 'quota' in r.text.lower():
                    raise RuntimeError("Key Gemini đã hết lượt vẽ ảnh (gói miễn phí rất ít hoặc không có lượt vẽ). Anh chọn 'Codex vẽ' hoặc 'Pollinations' rồi thử lại.")
                time.sleep(8 * (attempt + 1))
            elif r.status_code >= 500:
                time.sleep(4 * (attempt + 1))
            else:
                break
    raise RuntimeError(f'Gemini chưa vẽ được ảnh ({last})')

def _find_b64(o):
    if isinstance(o, dict):
        dt = o.get('data')
        if isinstance(dt, str) and len(dt) > 1000:
            return dt
        for v in o.values():
            x = _find_b64(v)
            if x:
                return x
        return None
    if isinstance(o, list):
        for v in o:
            x = _find_b64(v)
            if x:
                return x
        return None
    return None

def _pollinations(prompt: str, aspect: str, seed: int) -> bytes:
    import urllib.parse
    import requests
    w, h = {'9:16': (768, 1344), '16:9': (1344, 768), '1:1': (1024, 1024)}.get(aspect, (1344, 768))
    url = 'https://image.pollinations.ai/prompt/' + urllib.parse.quote(prompt[:1800]) + f'?width={w}&height={h}&seed={seed}&nologo=true&model=flux'
    last = ''
    for _ in range(3):
        try:
            r = requests.get(url, timeout=180)
            if r.ok and len(r.content) > 5000:
                return r.content
            last = f'{r.status_code}'
        except Exception as e:
            last = e.__class__.__name__
        time.sleep(5)
    raise RuntimeError(f'Pollinations chưa vẽ được ảnh ({last})')

def _codex_image(prompt: str, refs: list[bytes], aspect: str, log) -> bytes:
    import os
    import shutil
    import subprocess
    import tempfile
    import ai_cli
    exe = ai_cli.find_exe('codex')
    if not exe:
        raise RuntimeError('Chưa cài Codex (npm i -g @openai/codex, rồi codex login)')
    d = Path(tempfile.mkdtemp(prefix='hh-codex-'))
    try:
        args = []
        for i, b in enumerate(refs):
            p = d / f'mau-{i + 1}.png'
            p.write_bytes(b)
            args += ['-i', str(p)]
        shape = {'9:16': 'dọc 1024x1536', '16:9': 'ngang 1536x1024', '1:1': 'vuông 1024x1024'}.get(aspect, 'ngang 1536x1024')
        msg = f'$imagegen\nDùng công cụ tạo ảnh có sẵn (image_gen), KHÔNG dùng script hay API key. Tạo đúng 1 ảnh khổ {shape}:\n{prompt}\n'
        if refs:
            msg += 'Ảnh đính kèm là ảnh mẫu nhân vật: giữ y hệt khuôn mặt, tóc, quần áo, màu sắc.\n'
        msg += 'Lưu ảnh vào thư mục hiện tại tên ket-qua.png. Không làm gì khác.'
        t0 = time.time()
        cmd = [exe, 'exec', '--skip-git-repo-check', '--ephemeral', '-s', 'workspace-write', '--color', 'never', '--json', '-C', str(d), '-'] + args
        try:
            rc, so, se = ai_cli._run(cmd, msg, d, 'codex', 600)
        except subprocess.TimeoutExpired:
            rc, so, se = -1, '', 'quá thời gian'
        paths = []
        for line in so.splitlines():
            try:
                ai_cli._find_paths(json.loads(line), paths)
            except Exception:
                pass
        files = [Path(p) for p in paths if Path(p).exists()] + sorted(p for p in d.glob('*.png') if not p.name.startswith('mau-'))
        ch = Path(os.environ.get('CODEX_HOME') or (Path.home() / '.codex')) / 'generated_images'
        if ch.exists():
            files += [p for p in ch.rglob('*') if p.suffix.lower() in ('.png', '.jpg', '.webp') and p.stat().st_mtime >= t0 - 2]
        for f in files:
            b = f.read_bytes()
            if len(b) > 5000:
                shutil.rmtree(d, ignore_errors=True)
                return b
        raise RuntimeError(f'Codex chưa tạo được ảnh ({se or so or str(rc)[-200:]})')
    finally:
        shutil.rmtree(d, ignore_errors=True)

def _agy_image(prompt: str, aspect: str, log) -> bytes:
    import shutil
    import subprocess
    import tempfile
    import ai_cli
    exe = ai_cli.find_exe('antigravity')
    if not exe:
        raise RuntimeError('Chưa cài Antigravity (agy)')
    base = ai_cli._home or (Path(tempfile.gettempdir()) / 'ai-tam')
    d = (base / ('ve-' + uuid.uuid4().hex[:8])).resolve()
    d.mkdir(parents=True, exist_ok=True)
    shape = {'9:16': 'tall portrait 9:16', '16:9': 'wide landscape 16:9', '1:1': 'square 1:1'}.get(aspect, 'wide landscape 16:9')
    msg = f'Use your built-in generate_image tool exactly once to create this picture (do NOT draw it with code, SVG or scripts, do NOT run terminal commands, do NOT touch any other file). Aspect ratio: {shape}. Save the image in the current folder as ket-qua.png. Picture: {prompt}'
    _AGY_LOCK.acquire()
    t0 = time.time()
    try:
        cmd = [exe, '--dangerously-skip-permissions', '--disable-slash-commands', '--print-timeout', '280s', '--output-format', 'json', '--print', msg]
        try:
            rc, so, se = ai_cli._run(cmd, None, d, 'antigravity', 300)
            if rc != 0 and re.search(r'unknown (flag|option|argument)|flag provided but not defined', se, re.I):
                rc, so, se = ai_cli._run([exe, '--dangerously-skip-permissions', '--print', msg], None, d, 'antigravity', 300)
        except subprocess.TimeoutExpired:
            rc, so, se = -1, '', 'quá thời gian'
        files = [p for p in d.rglob('*') if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
        gem = Path.home() / '.gemini'
        if not files and gem.exists():
            files = sorted((p for p in gem.rglob('*') if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp') and p.stat().st_mtime >= t0 - 1), key=lambda p: p.stat().st_mtime)
        for f in reversed(files):
            b = f.read_bytes()
            h = hashlib.sha1(b).hexdigest()
            if len(b) > 8000 and h not in _SEEN and str(f) not in _SEEN:
                _SEEN.add(h)
                _SEEN.add(str(f))
                log(f'[hoat-hinh] Antigravity vẽ xong sau {time.time() - t0:.0f}s ({f.name})')
                _AGY_LOCK.release()
                shutil.rmtree(d, ignore_errors=True)
                return b
        raise RuntimeError(f'Antigravity chưa vẽ được ảnh ({ai_cli._real_error(se, so, rc)[-180:]})')
    finally:
        try:
            _AGY_LOCK.release()
        except RuntimeError:
            pass
        shutil.rmtree(d, ignore_errors=True)

def draw(prompt: str, refs: list[bytes], aspect: str, src: str, log, seed: int = 1) -> bytes:
    if src == 'mock':
        return _mock(prompt, aspect)
    if src == 'codex':
        return _codex_image(prompt, refs, aspect, log)
    if src == 'pollinations':
        return _pollinations(prompt, aspect, seed)
    if src == 'antigravity':
        return _agy_image(prompt, aspect, log)
    if src == 'gemini':
        return _gemini_image(prompt, refs, aspect)
    if src == 'openai':
        import hl_pro
        return hl_pro.openai_image(prompt, refs, aspect)
    errs = []
    import hl_pro
    chain = [('Antigravity', lambda: _agy_image(prompt, aspect, log))]
    if hl_pro.gemini_key() or __import__('media_ai')._gemini_key():
        chain.append(('Gemini API', lambda: _gemini_image(prompt, refs, aspect)))
    if hl_pro.ai_cfg().get('openai_key'):
        chain.append(('OpenAI API', lambda: hl_pro.openai_image(prompt, refs, aspect)))
    chain.append(('Pollinations', lambda: _pollinations(prompt, aspect, seed)))
    for name, fn in chain:
        if name == 'Antigravity':
            try:
                import ai_cli
                if not ai_cli.find_exe('antigravity'):
                    errs.append('Antigravity: chưa cài')
                    continue
            except Exception:
                continue
        it = getattr(CUR, 'item', None)
        if it is not None:
            it.update(src=name, t0=time.time())
        try:
            return fn()
        except Exception as e:
            log(f'[hoat-hinh] {name} không vẽ được: {e} → thử cách khác')
            if it is not None:
                it['tried'] = (it.get('tried') or []) + [name]
            errs.append(f'{name}: {str(e)[:120]}')
    raise RuntimeError('Chưa vẽ được bằng cách nào: ' + ' | '.join(errs))

def _mock(prompt: str, aspect: str) -> bytes:
    from PIL import Image, ImageDraw
    w, h = {'9:16': (720, 1280), '16:9': (1600, 900), '1:1': (1000, 1000)}[aspect]
    im = Image.new('RGB', (w, h), 'white')
    g = ImageDraw.Draw(im)
    if 'expression sheet' in prompt:
        col = (200, 120, 60) if 'female' in prompt else (60, 120, 200)
        for i in range(10):
            cx = (i % 5) * w // 5 + w // 10
            cy = (i // 5) * h // 2 + h // 4
            g.ellipse([cx - 75, cy - 150, cx + 75, cy + 10], fill=(250, 214, 180), outline=(60, 40, 30), width=6)
            g.rectangle([cx - 65, cy + 10, cx + 65, cy + 180], fill=col, outline=(60, 40, 30), width=6)
            if i == 8:
                g.line([cx - 45, cy - 85, cx - 15, cy - 85], fill=(60, 40, 30), width=6)
                g.line([cx + 15, cy - 85, cx + 45, cy - 85], fill=(60, 40, 30), width=6)
            else:
                g.ellipse([cx - 40, cy - 95, cx - 20, cy - 75], fill=(60, 40, 30))
                g.ellipse([cx + 20, cy - 95, cx + 40, cy - 75], fill=(60, 40, 30))
            if i == 9:
                g.ellipse([cx - 22, cy - 55, cx + 22, cy - 5], fill=(120, 30, 30), outline=(60, 40, 30), width=4)
            elif i == 1:
                g.ellipse([cx - 18, cy - 45, cx + 18, cy - 25], fill=(120, 30, 30), outline=(60, 40, 30), width=4)
            else:
                g.arc([cx - 35, cy - 60, cx + 35, cy - 20 + i * 3], 0, 180, fill=(60, 40, 30), width=6)
    else:
        for y in range(h):
            g.line([(0, y), (w, y)], fill=(230 - y * 60 // h, 220 - y * 40 // h, 200))
        g.rectangle([0, int(h * 0.72), w, h], fill=(190, 150, 110))
    b = io.BytesIO()
    im.save(b, 'PNG')
    return b.getvalue()

def sheet_prompt(c: dict) -> str:
    top = '; '.join(f"{k + 1}) {EXPR_EN[e]}" for k, e in enumerate(EXPRS[:5]))
    bot = '; '.join(f"{k + 6}) {EXPR_EN[e]}" for k, e in enumerate(EXPRS[5:]))
    return f"{STYLE} Character expression sheet of ONE original character: {c['gender']}, {c.get('age', 'adult')}, {c['look']}. 10 panels in a clean 5 columns x 2 rows grid on a pure white background, generous white space between panels, NO borders or frames, each panel shows the SAME character from the chest up, same outfit, same hairstyle, same colors, same size and same position inside its panel, facing the viewer at a slight 3/4 angle. Panels left-to-right, top row: {top}. Bottom row: {bot}. {NO_TEXT}"

def slice_sheet(png: bytes, n: int = 10, cols: int = 5) -> list:
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    im = Image.open(io.BytesIO(png)).convert('RGB')
    a = np.asarray(im).astype(np.int16)
    ink = (a.min(axis=2) < 225) | ((a.max(axis=2) - a.min(axis=2)) > 28)
    big = ndimage.binary_dilation(ink, iterations=max(4, im.width // 160))
    lab, n_components = ndimage.label(big)
    boxes = []
    if n_components:
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n_components + 1))
        for i in np.argsort(sizes)[::-1][:n]:
            if sizes[i] < big.size * 0.012:
                break
            sl = ndimage.find_objects((lab == (i + 1)).astype(np.int8))[0]
            boxes.append((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop))
    if len(boxes) != n:
        W, H = im.size
        rows_n = (n + cols - 1) // cols
        boxes = [(c * W // cols, r * H // rows_n, (c + 1) * W // cols, (r + 1) * H // rows_n) for r in range(rows_n) for c in range(cols)][:n]
    else:
        rows = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)
        boxes = []
        for r0 in range(0, n, cols):
            boxes += sorted(rows[r0:r0 + cols], key=lambda b: b[0])
    out = []
    for x0, y0, x1, y1 in boxes:
        pad = 6
        rows = np.where(ink[y0:y1, x0:x1].any(axis=1))[0]
        yb = y0 + int(rows[-1]) + 1 if len(rows) else y1
        crop = im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, yb)))
        out.append(cut_white(crop))
    return out

def cut_white(im):
    import numpy as np
    from PIL import Image, ImageFilter
    from scipy import ndimage
    a = np.asarray(im.convert('RGB')).astype(np.int16)
    light = (a.min(axis=2) > 222) & ((a.max(axis=2) - a.min(axis=2)) < 26)
    cut = min(6, max(1, light.shape[0] // 40))
    lab, _ = ndimage.label(light[:-cut])
    edge = set(np.unique(np.concatenate([lab[0], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.zeros(light.shape, bool)
    bg[:-cut] = np.isin(lab, list(edge))
    bg[-cut:] = bg[-cut - 1] & light[-cut:]
    fg = ~bg
    lab2, n2 = ndimage.label(fg)
    if n2 > 1:
        sizes = ndimage.sum(np.ones_like(lab2), lab2, range(1, n2 + 1))
        keep = 1 + int(np.argmax(sizes))
        fg = (lab2 == keep) | ndimage.binary_fill_holes(lab2 == keep)
    alpha = Image.fromarray((fg * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    rgba = im.convert('RGBA')
    rgba.putalpha(alpha)
    bb = alpha.point(lambda v: 255 if v > 10 else 0).getbbox()
    return rgba.crop(bb) if bb else rgba

def start_assets(d: dict, media_dir: Path, log) -> dict:
    jid = uuid.uuid4().hex[:10]
    job = {'id': jid, 'status': 'running', 'percent': 0, 'stage': 'Chuẩn bị', 'started': time.time(), 'items': []}
    JOBS[jid] = job
    threading.Thread(target=_run_assets, args=(job, d, media_dir, log), daemon=True).start()
    return {'jobId': jid}

def _save(media_dir: Path, b: bytes, tag: str) -> str:
    h = hashlib.sha1(b).hexdigest()[:16]
    f = media_dir / f'{h}-hh-{tag}.png'
    if not f.exists():
        f.write_bytes(b)
    return f'/media/{f.name}'

def place_prompt(en: str) -> str:
    return f'{STYLE} Background scene only, NO people, NO characters: {en}. Simple, slightly soft-focus so characters in front stand out, eye-level view, open space in the lower middle. {NO_TEXT}'

def draw_place(d: dict, media_dir: Path, log) -> dict:
    en = str(d.get('en') or d.get('vi') or '').strip()
    if not en:
        raise RuntimeError('Thiếu mô tả bối cảnh')
    aspect = '16:9' if d.get('format') == 'landscape' else ('1:1' if d.get('format') == 'square' else '9:16')
    pid = 'p' + uuid.uuid4().hex[:5]
    url = _save(media_dir, draw(place_prompt(en), [], aspect, d.get('src', 'auto'), log, seed=int(time.time()) % 997), 'bg-' + pid)
    return {'id': pid, 'vi': str(d.get('vi') or en)[:80], 'en': en, 'url': url}

def _run_assets(job: dict, d: dict, media_dir: Path, log) -> None:
    try:
        story = d['story']
        src = d.get('src', 'auto')
        aspect = '16:9' if d.get('format') == 'landscape' else ('1:1' if d.get('format') == 'square' else '9:16')
        chars = story['characters']
        out = {'chars': {}, 'bg': '', 'bgs': {}}
        places = story.get('places') or [{'id': 'p1', 'vi': 'Bối cảnh', 'en': (story.get('setting') or {}).get('en') or 'a simple cozy room'}]
        out['places'] = places
        job['items'] = [{'name': f"Nhân vật {c['name']}", 'state': 'chờ'} for c in chars] + [{'name': f"Bối cảnh: {pl['vi']}", 'state': 'chờ'} for pl in places]
        job['src'] = src

        def begin(k):
            it = job['items'][k]
            it.update(state='đang vẽ', t0=time.time())
            CUR.item = it

        def bump(k, msg):
            it = job['items'][k]
            it.update(state='xong', secs=round(time.time() - it.get('t0', time.time())))
            job['stage'] = msg

        reuse = d.get('reuse') or {}
        rc = reuse.get('chars') or {}
        rb = reuse.get('bgs') or {}

        def one_char(i, c):
            old = rc.get(c['id'])
            if old and (old.get('imgs') or {}).get('neutral'):
                out['chars'][c['id']] = {
                    'name': c['name'],
                    'side': c['side'],
                    'gender': c['gender'],
                    'imgs': old['imgs'],
                    'sheet': old.get('sheet') or old['imgs']['neutral'],
                }
                job['items'][i].update(state='xong', img=out['chars'][c['id']]['sheet'], secs=0, src='phim bộ')
                return
            prompt = sheet_prompt(c)
            begin(i)
            try:
                b = draw(prompt, [], '16:9', src, log, seed=7 + i)
            except Exception:
                job['items'][i]['state'] = 'lỗi'
                raise
            cells = slice_sheet(b)
            imgs = {}
            for e, cim in zip(EXPRS, cells):
                buf = io.BytesIO()
                cim.save(buf, 'PNG')
                imgs[e] = _save(media_dir, buf.getvalue(), f"{c['id']}-{e}")
            out['chars'][c['id']] = {
                'name': c['name'],
                'side': c['side'],
                'gender': c['gender'],
                'imgs': imgs,
                'sheet': _save(media_dir, b, f"{c['id']}-sheet"),
            }
            job['items'][i]['img'] = out['chars'][c['id']]['sheet']
            bump(i, f"Xong nhân vật {c['name']}")

        def one_bg(k, pl):
            if rb.get(pl['id']):
                out['bgs'][pl['id']] = rb[pl['id']]
                out['bg'] = out['bg'] or rb[pl['id']]
                job['items'][k].update(state='xong', img=rb[pl['id']], secs=0, src='phim bộ')
                return
            begin(k)
            try:
                url = _save(media_dir, draw(place_prompt(pl['en']), [], aspect, src, log, seed=3 + k), 'bg-' + pl['id'])
            except Exception:
                job['items'][k]['state'] = 'lỗi'
                raise
            out['bgs'][pl['id']] = url
            out['bg'] = out['bg'] or url
            job['items'][k]['img'] = url
            bump(k, 'Xong bối cảnh ' + pl['vi'])

        max_w = 2 if src in ('gemini', 'openai', 'pollinations', 'mock') else 1
        with ThreadPoolExecutor(max_workers=max_w) as ex:
            futs = [ex.submit(one_char, i, c) for i, c in enumerate(chars)] + [ex.submit(one_bg, len(chars) + j, pl) for j, pl in enumerate(places)]
            errs = []
            for f in futs:
                try:
                    f.result()
                except Exception as e:
                    errs.append(str(e))
        if errs:
            raise RuntimeError(errs[0])
        job['result'] = out
        job['status'] = 'done'
        job['stage'] = 'Xong'
        job['percent'] = 100
        log(f'[hoat-hinh] vẽ xong {len(chars)} nhân vật + phông')
    except Exception as e:
        log(f'[hoat-hinh] lỗi: {e}')
        job.update(status='error', error=str(e), stage='Có lỗi')

TYPICAL = {
    'OpenAI API': 60,
    'openai': 60,
    'Antigravity': 130,
    'antigravity': 130,
    'Codex': 90,
    'codex': 90,
    'Gemini API': 35,
    'gemini': 35,
    'Pollinations': 30,
    'pollinations': 30,
    'mock': 2,
}

def job_status(jid: str) -> dict:
    import math
    j = JOBS.get(jid)
    if not j:
        raise RuntimeError('Không có việc này (app vừa khởi động lại?)')
    items = j.get('items') or []
    now = time.time()
    if items and j.get('status') == 'running':
        acc = 0.0
        run = []
        for it in items:
            if it['state'] == 'xong':
                acc += 1
            elif it['state'] == 'đang vẽ':
                el = now - it.get('t0', now)
                typ = TYPICAL.get(it.get('src') or j.get('src'), 120)
                acc += (1 - math.exp(-el / typ * 1.4)) * 0.95
                run.append(f"{it['name']}{(' bằng ' + it['src']) if it.get('src') else ''} ({int(el)} giây / thường ~{typ} giây)")
        j['percent'] = min(99, int(acc * 100 / len(items)))
        done = sum(1 for it in items if it['state'] == 'xong')
        if run:
            j['stage'] = f"Đang vẽ {', '.join(run)} · xong {done}/{len(items)} hình"
    out = {k: v for k, v in j.items() if not k.startswith('_')}
    out['items'] = [{k: v for k, v in it.items()} for it in items]
    return out

def redraw_char(d: dict, media_dir: Path, log) -> dict:
    c = d['char']
    sub = {'story': {'characters': [c], 'setting': {'en': 'plain'}}, 'src': d.get('src', 'gemini'), 'format': d.get('format')}
    job = {'id': 'x', 'status': 'running', 'items': []}
    _run_assets_chars_only(job, sub, media_dir, log)
    return job['result']

def _run_assets_chars_only(job, d, media_dir, log):
    c = d['story']['characters'][0]
    prompt = sheet_prompt(c)
    b = draw(prompt, [], '16:9', d.get('src', 'gemini'), log, seed=int(time.time()) % 999)
    imgs = {}
    for e, cim in zip(EXPRS, slice_sheet(b)):
        buf = io.BytesIO()
        cim.save(buf, 'PNG')
        imgs[e] = _save(media_dir, buf.getvalue(), f"{c['id']}-{e}")
    job['result'] = {'id': c['id'], 'imgs': imgs, 'sheet': _save(media_dir, b, f"{c['id']}-sheet")}
