from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

NOWIN = 0x08000000 if os.name == 'nt' else 0
CTX: dict = {}

def setup(**kw) -> None:
    CTX.update(kw)

def log(msg: str) -> None:
    try:
        CTX['log'](msg)
    except Exception:
        print(msg)

def _ff() -> str | None:
    try:
        return CTX['ffmpeg']()
    except Exception:
        return shutil.which('ffmpeg')

def _cfg() -> dict:
    try:
        return CTX['load_cfg']()
    except Exception:
        return {}

_CIT = {
    't': 0.0,
    'ok': False,
    'voices': [],
    'tv': 0.0,
    'starting': 0.0,
}

def cit_url() -> str:
    return (_cfg().get('cit_url') or os.environ.get('CIT_VOICE_URL') or 'http://127.0.0.1:8001').rstrip('/')

def _http(method: str, url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 600):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.headers), r.read()

def cit_ok(fresh: bool = False) -> bool:
    now = time.time()
    if not fresh and now - _CIT['t'] < 15:
        return _CIT['ok']
    try:
        st, _, b = _http('GET', cit_url() + '/health', timeout=1.5)
        _CIT['ok'] = (st == 200)
        _CIT['engine'] = json.loads(b or b'{}').get('engine', '')
    except Exception:
        _CIT['ok'] = False
    _CIT['t'] = now
    return _CIT['ok']

def cit_exe() -> Path | None:
    c = _cfg().get('cit_exe')
    cands = [Path(c)] if c else []
    app = Path(CTX.get('APP_DIR') or '.')
    cands.append(app.parent / 'CIT Voice Studio' / 'CIT-Voice-Studio.exe')
    for d in 'CDEFGH':
        cands.append(Path(f'{d}:/CIT Voice Studio/CIT-Voice-Studio.exe'))
    for p in cands:
        try:
            if p.is_file():
                return p
        except Exception:
            pass
    return None

def cit_start(wait: float = 120) -> bool:
    if cit_ok(True):
        return True
    exe = cit_exe()
    if not exe:
        return False
    if time.time() - _CIT['starting'] > 180:
        _CIT['starting'] = time.time()
        log(f'[cit] đang mở {exe}')
        try:
            subprocess.Popen([str(exe)], cwd=str(exe.parent), creationflags=8 if os.name == 'nt' else 0)
        except Exception as e:
            log(f'[cit] không mở được: {e}')
            return False
    t0 = time.time()
    while time.time() - t0 < wait:
        if cit_ok(True):
            return True
        time.sleep(2)
    return False

def cit_voices() -> list[dict]:
    if not cit_ok():
        return []
    if time.time() - _CIT['tv'] < 60 and _CIT['voices']:
        return _CIT['voices']
    try:
        _, _, b = _http('GET', cit_url() + '/voices', timeout=5)
        arr = json.loads(b) or []
        out = []
        for v in arr:
            vid = str(v.get('id') or v.get('name') or '')
            if not vid:
                continue
            desc = v.get('description') or ''
            lab = ('🎙 ' if v.get('isCloned') else '') + 'CIT · ' + vid + (f' — {desc}' if desc else '')
            out.append({'id': 'cit:' + vid, 'label': lab, 'cit': True})
        _CIT['voices'] = out
        _CIT['tv'] = time.time()
        return out
    except Exception as e:
        log(f'[cit] đọc danh sách giọng lỗi: {e}')
        return _CIT['voices']

def _cit_json(path: str, body: dict, out: Path) -> None:
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    st, hd, b = _http('POST', cit_url() + path, data, headers={'Content-Type': 'application/json'}, timeout=900)
    _save_audio(b, hd, out)

def _save_audio(b: bytes, hd: dict, out: Path) -> None:
    ct = (hd.get('Content-Type') or hd.get('content-type') or '').lower()
    if ct.startswith('application/json'):
        import base64
        j = json.loads(b)
        b = base64.b64decode(str(j.get('audio_base64') or j.get('audio') or '').split(',')[-1])
    if len(b) < 200:
        raise RuntimeError('CIT Voice Studio trả về âm thanh rỗng')
    tmp = out.with_suffix('.cit' + ('.mp3' if b[:3] == b'ID3' or b[:2] == b'\xff\xfb' else '.wav'))
    tmp.write_bytes(b)
    ff = _ff()
    if ff:
        subprocess.run([ff, '-y', '-loglevel', 'error', '-i', str(tmp), '-ar', '48000', '-ac', '1', str(out)], check=True, creationflags=NOWIN)
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(out)

def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    bd = '----hl' + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode('utf-8'))
    for k, (name, data, ctype) in files.items():
        parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\nContent-Type: {ctype}\r\n\r\n'.encode('utf-8') + data + b'\r\n')
    parts.append(f'--{bd}--\r\n'.encode('utf-8'))
    return b''.join(parts), 'multipart/form-data; boundary=' + bd

def need_cit() -> None:
    if cit_ok(True):
        return
    if cit_start():
        return
    raise RuntimeError("Giọng CIT / giọng nhân bản cần mở phần mềm CIT Voice Studio (thư mục G:\\CIT Voice Studio). Mở CIT-Voice-Studio.exe, chờ chữ 'Sẵn sàng' rồi bấm đọc lại.")

def cit_synth(text: str, voice: str, out: Path, speed: float | None = None, seed: int | None = None) -> None:
    need_cit()
    body = {'text': text, 'voice_id': voice, 'format': 'wav'}
    if speed:
        body['speed'] = float(speed)
    if seed is not None:
        body['seed'] = int(seed)
    log(f"[giong] CIT '{voice}': {text[:60]}…")
    _cit_json('/api/tts/generate', body, out)

def clone_dir() -> Path:
    d = Path(CTX['HOME']) / 'giong-mau'
    d.mkdir(parents=True, exist_ok=True)
    return d

def slug(s: str) -> str:
    s = unicodedata.normalize('NFD', s or 'giong')
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').replace('đ', 'd').replace('Đ', 'D')
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()
    return s[:40] or 'giong'

def clones() -> list[dict]:
    out = []
    for j in sorted(clone_dir().glob('*.json')):
        try:
            m = json.loads(j.read_text(encoding='utf-8'))
            if (clone_dir() / (j.stem + '.wav')).exists():
                out.append({
                    'id': j.stem,
                    'name': m.get('name') or j.stem,
                    'ref_text': m.get('ref_text', ''),
                    'dur': m.get('dur', 0),
                    'url': '/giong-mau/' + j.stem + '.wav',
                })
        except Exception:
            pass
    return out

def clone_save(raw: bytes, fname: str, name: str, ref_text: str = '') -> dict:
    ff = _ff()
    if not ff:
        raise RuntimeError('Cần ffmpeg để đọc file giọng mẫu')
    if len(raw) < 2000:
        raise RuntimeError('File giọng mẫu quá ngắn')
    sid = slug(name)
    base = sid
    i = 2
    while (clone_dir() / (sid + '.wav')).exists():
        sid = f'{base}-{i}'
        i += 1
    src = clone_dir() / ('_tam' + Path(fname or 'a.webm').suffix.lower())
    src.write_bytes(raw)
    out = clone_dir() / (sid + '.wav')
    af = 'silenceremove=start_periods=1:start_threshold=-45dB,highpass=f=70,afftdn=nf=-25,loudnorm=I=-18:TP=-2'
    r = subprocess.run([
        ff, '-y', '-loglevel', 'error',
        '-i', str(src),
        '-af', af,
        '-t', '12',
        '-ar', '24000',
        '-ac', '1',
        str(out),
    ], capture_output=True, creationflags=NOWIN)
    src.unlink(missing_ok=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError('Không đọc được file giọng mẫu (hãy dùng MP3/WAV/M4A hoặc ghi âm lại)')
    dur = _dur(ff, out)
    if dur < 2.5:
        out.unlink(missing_ok=True)
        raise RuntimeError(f'Giọng mẫu chỉ {dur:.1f} giây, cần 3–8 giây nói rõ ràng')
    (clone_dir() / (sid + '.json')).write_text(
        json.dumps({'name': name or sid, 'ref_text': ref_text or '', 'dur': round(dur, 1)}, ensure_ascii=False),
        encoding='utf-8'
    )
    log(f"[nhan-ban] đã lưu giọng mẫu '{name}' ({dur:.1f}s)")
    return {'id': sid, 'name': name or sid, 'dur': round(dur, 1), 'voice': 'clone:' + sid}

def clone_delete(sid: str) -> None:
    for ext in ('.wav', '.json'):
        (clone_dir() / (slug(sid) + ext)).unlink(missing_ok=True)

def _dur(ff: str, f: Path) -> float:
    r = subprocess.run(
        [ff, '-i', str(f)],
        capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=NOWIN
    )
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', r.stderr or '')
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 0.0

def clone_synth(text: str, sid: str, out: Path) -> None:
    need_cit()
    f = clone_dir() / (slug(sid) + '.wav')
    if not f.exists():
        raise RuntimeError(f"Không thấy giọng mẫu '{sid}' (có thể đã xoá)")
    meta = {}
    try:
        meta = json.loads((clone_dir() / (slug(sid) + '.json')).read_text(encoding='utf-8'))
    except Exception:
        pass
    fields = {'text': text, 'denoise': 'true', 'format': 'wav', 'seed': '7'}
    if meta.get('ref_text'):
        fields['ref_text'] = meta['ref_text']
    body, ctype = _multipart(fields, {'ref_audio': (f.name, f.read_bytes(), 'audio/wav')})
    log(f"[giong] nhân bản '{meta.get('name', sid)}': {text[:60]}…")
    st, hd, b = _http('POST', cit_url() + '/api/tts/clone', body, headers={'Content-Type': ctype}, timeout=900)
    _save_audio(b, hd, out)

def voices_extra() -> list[dict]:
    out = list(cit_voices())
    for c in clones():
        out.append({'id': 'clone:' + c['id'], 'label': '🎙 Giọng nhân bản · ' + c['name'], 'clone': True})
    return out

TAG_RE = re.compile(r'\[\s*(cười|hắng giọng|thở dài|nghỉ[^\]]{0,16}|nghi[^\]]{0,16}|pause[^\]]{0,16})\s*\]', re.IGNORECASE)

def split_tags(text: str) -> list[tuple[str, str]]:
    out = []
    pos = 0
    for m in TAG_RE.finditer(text or ''):
        if m.start() > pos:
            out.append(('txt', text[pos:m.start()]))
        out.append(('tag', '[' + m.group(1).strip() + ']'))
        pos = m.end()
    if pos < len(text or ''):
        out.append(('txt', text[pos:]))
    return out

def strip_tags(text: str) -> str:
    return ' '.join(TAG_RE.sub(' ', text or '').split())

def prep_text(text: str, pron: str, keep_tags: bool, norm) -> str:
    parts = split_tags(text)
    res = []
    for kind, s in parts:
        if kind == 'tag':
            if keep_tags:
                res.append(' ' + s + ' ')
            elif s.lower().startswith(('[nghỉ', '[nghi', '[pause')):
                res.append(', ')
        else:
            try:
                res.append(norm(s, pron) if s.strip() else s)
            except Exception:
                res.append(s)
    return ' '.join(''.join(res).split())

VOICE_FX: dict[str, tuple[str, str]] = {
    'lam_sach': ('Làm sạch giọng (khử ồn, cân âm lượng)', 'highpass=f=80,afftdn=nf=-25,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-1.5'),
    'am_ap': ('Ấm, dày tiếng (radio FM)', 'bass=g=5:f=140,treble=g=2,acompressor=threshold=-18dB:ratio=3,loudnorm=I=-16:TP=-1.5'),
    'robot': ('Robot', "afftfilt=real='hypot(re,im)*sin(0)':imag='hypot(re,im)*cos(0)':win_size=512:overlap=0.75,aecho=0.8:0.88:8:0.5,volume=1.6"),
    'chuot_chip': ('Chuột chíp (giọng cao)', 'asetrate=48000*1.45,aresample=48000,atempo=0.69'),
    'tram': ('Giọng trầm (quái vật)', 'asetrate=48000*0.72,aresample=48000,atempo=1.39,bass=g=4'),
    'dien_thoai': ('Qua điện thoại', 'highpass=f=320,lowpass=f=3300,acompressor=threshold=-25dB:ratio=6,volume=1.8'),
    'loa_phong': ('Loa phóng thanh', 'highpass=f=600,lowpass=f=4200,acrusher=bits=8:mix=0.35,acompressor=threshold=-22dB:ratio=8,volume=2'),
    'radio': ('Radio cũ', 'highpass=f=450,lowpass=f=4800,acrusher=bits=10:mix=0.2,aecho=0.6:0.5:25:0.2,volume=1.6'),
    'vang_phong': ('Vang trong phòng', 'aecho=0.8:0.85:40|70:0.3|0.2'),
    'hoi_truong': ('Vang hội trường', 'aecho=0.8:0.9:90|160|260:0.35|0.25|0.15'),
    'nha_tho': ('Vang nhà thờ lớn', 'aecho=0.8:0.9:300|520|800:0.35|0.28|0.2,lowpass=f=9000'),
    'san_van_dong': ('Sân vận động', 'aecho=0.8:0.92:600|1100|1700:0.3|0.22|0.15,highpass=f=150'),
    'tieng_vong': ('Tiếng vọng (echo)', 'aecho=0.8:0.7:280|560:0.45|0.25'),
    'duoi_nuoc': ('Dưới nước', 'lowpass=f=550,vibrato=f=4:d=0.25,aecho=0.6:0.6:60:0.3,volume=1.6'),
    'dia_than': ('Đĩa than cổ', 'highpass=f=180,lowpass=f=6000,acrusher=bits=12:mix=0.15,vibrato=f=0.6:d=0.03'),
    'lofi': ('Lo-fi', 'lowpass=f=3600,acrusher=bits=9:samples=2:mix=0.4,vibrato=f=0.5:d=0.02'),
    'meo_tieng': ('Méo tiếng (distortion)', 'acrusher=bits=5:mix=0.55,volume=0.8'),
    'thi_tham': ('Thì thầm', 'highpass=f=900,afftdn=nf=-20,volume=1.7'),
    'tang_bass': ('Tăng bass', 'bass=g=9:f=110'),
    'tang_treble': ('Trong, sáng (tăng treble)', 'treble=g=7:f=4000'),
    'nhanh': ('Đọc nhanh hơn 15%', 'atempo=1.15'),
    'cham': ('Đọc chậm hơn 12%', 'atempo=0.88'),
}

def fx_list() -> list[dict]:
    return [{'id': k, 'label': v[0]} for k, v in VOICE_FX.items()]

def apply_fx(src: Path, fx: str, out: Path) -> None:
    ff = _ff()
    if not ff or fx not in VOICE_FX:
        shutil.copyfile(src, out)
        return
    chain = 'aresample=48000,' + VOICE_FX[fx][1]
    r = subprocess.run([
        ff, '-y', '-loglevel', 'error',
        '-i', str(src),
        '-af', chain,
        '-ar', '48000',
        '-ac', '1',
        str(out),
    ], capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=NOWIN)
    if r.returncode != 0 or not out.exists():
        log(f"[giong] hiệu ứng '{fx}' lỗi ({r.stderr or ''[-200:]}), dùng giọng gốc")
        shutil.copyfile(src, out)

WH = {
    'jobs': {},
    'model': None,
    'size': '',
    'install': {'state': '', 'log': ''},
}

WH_MODELS = [
    ('base', 'Nhanh (base, ~150 MB)'),
    ('small', 'Cân bằng (small, ~480 MB)'),
    ('medium', 'Chính xác (medium, ~1,5 GB)'),
    ('large-v3-turbo', 'Chính xác nhất (large-v3-turbo, ~1,6 GB, chậm)'),
]

def wh_installed() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec('faster_whisper') is not None
    except Exception:
        return False

def wh_status() -> dict:
    return {
        'installed': wh_installed(),
        'install': WH['install'],
        'models': [{'id': a, 'label': b} for a, b in WH_MODELS],
        'model': _cfg().get('whisper_model', 'small'),
    }

def _py() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == 'pythonw.exe' and (exe.parent / 'python.exe').exists():
        return str(exe.parent / 'python.exe')
    return str(exe)

def wh_install() -> dict:
    if WH['install'].get('state') == 'running':
        return wh_status()
    WH['install'] = {'state': 'running', 'log': 'Đang cài faster-whisper (5–10 phút, cần mạng)…'}
    def run():
        try:
            p = subprocess.Popen(
                [_py(), '-m', 'pip', 'install', '--upgrade', 'faster-whisper'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='ignore', creationflags=NOWIN
            )
            tail = []
            for line in p.stdout:
                tail = (tail + [line.strip()])[-6:]
                WH['install']['log'] = ' · '.join(x for x in tail if x)[-300:]
            p.wait()
            import importlib
            importlib.invalidate_caches()
            if p.returncode == 0 and wh_installed():
                WH['install'] = {'state': 'ok', 'log': 'Đã cài xong Whisper.'}
            else:
                WH['install'] = {'state': 'error', 'log': 'Cài lỗi: ' + WH['install']['log']}
        except Exception as e:
            WH['install'] = {'state': 'error', 'log': f'Cài lỗi: {e}'}
        log('[whisper] ' + WH['install']['log'])
    threading.Thread(target=run, daemon=True).start()
    return wh_status()

def _wh_model(size: str):
    if WH['model'] is not None and WH['size'] == size:
        return WH['model']
    from faster_whisper import WhisperModel
    root = Path(CTX['HOME']) / 'whisper'
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    log(f'[whisper] nạp mô hình {size} (lần đầu sẽ tải về)…')
    WH['model'] = WhisperModel(
        size,
        device='cpu',
        compute_type='int8',
        download_root=str(root),
        cpu_threads=max(2, (os.cpu_count() or 4) - 1),
    )
    WH['size'] = size
    return WH['model']

def wh_start(src: Path, size: str = '', lang: str = 'vi', prompt: str = '') -> dict:
    if not wh_installed():
        return {'need_install': True}
    size = size or _cfg().get('whisper_model', 'small')
    jid = uuid.uuid4().hex[:10]
    J = {'state': 'running', 'pct': 0, 'msg': 'Đang nạp Whisper…', 'segments': [], 'src': str(src)}
    WH['jobs'][jid] = J

    def run():
        try:
            ff = _ff()
            wav = src
            if ff:
                wav = Path(CTX['HOME']) / 'whisper' / (jid + '.wav')
                wav.parent.mkdir(parents=True, exist_ok=True)
                r = subprocess.run([
                    ff, '-y', '-loglevel', 'error',
                    '-i', str(src),
                    '-vn', '-ar', '16000', '-ac', '1',
                    str(wav),
                ], capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=NOWIN)
                if r.returncode != 0 or not wav.exists():
                    if 'does not contain any stream' in (r.stderr or '') or 'Output file' in (r.stderr or ''):
                        raise RuntimeError('file này không có tiếng để nghe')
                    raise RuntimeError('không đọc được âm thanh: ' + (r.stderr or '')[-160:])
            total = _dur(ff, wav) if ff else 0
            model = _wh_model(size)
            J['msg'] = 'Đang nghe…'
            segs, info = model.transcribe(
                str(wav),
                language=lang or None,
                word_timestamps=True,
                vad_filter=True,
                beam_size=5,
                initial_prompt=prompt or None,
            )
            for s in segs:
                words = [{'s': round(w.start, 2), 'e': round(w.end, 2), 'w': w.word.strip()} for w in (s.words or [])]
                J['segments'].append({
                    'start': round(s.start, 2),
                    'end': round(s.end, 2),
                    'text': s.text.strip(),
                    'words': words,
                })
                if total:
                    J['pct'] = min(99, round(round(s.end / total * 100)))
                    J['msg'] = f'Đã nghe {s.end:.0f}/{total:.0f} giây'
            J['state'] = 'done'
            J['pct'] = 100
            J['msg'] = f'Xong: {len(J["segments"])} câu'
            if wav != src:
                wav.unlink(missing_ok=True)
        except Exception as e:
            J['state'] = 'error'
            J['msg'] = f'Whisper lỗi: {e}'
            log('[whisper] ' + J['msg'])

    threading.Thread(target=run, daemon=True).start()
    return {'job': jid}

def wh_job(jid: str) -> dict:
    J = WH['jobs'].get(jid)
    if not J:
        return {'state': 'error', 'msg': 'Không thấy việc nghe này'}
    return {k: J[k] for k in ('state', 'pct', 'msg', 'segments')}

AG = {
    'cv': threading.Condition(),
    'q': [],
    'res': {},
    'last': 0.0,
}

def agent_ui_online() -> bool:
    return (time.time() - AG['last']) < 30

def agent_cmd(cmd: str, args: dict, timeout: float = 120) -> dict:
    cid = uuid.uuid4().hex[:12]
    with AG['cv']:
        AG['q'].append({'id': cid, 'cmd': cmd, 'args': args or {}})
        AG['cv'].notify_all()
        end = time.time() + timeout
        while cid not in AG['res']:
            left = end - time.time()
            if left <= 0:
                AG['q'] = [x for x in AG['q'] if x['id'] != cid]
                return {'ok': False, 'error': 'App chưa trả lời (cửa sổ HL Studio có đang mở không?)' if not agent_ui_online() else 'Hết thời gian chờ app làm xong'}
            AG['cv'].wait(min(left, 5))
            if cid in AG['res']:
                return AG['res'].pop(cid)

def agent_poll(wait: float = 20) -> list:
    with AG['cv']:
        AG['last'] = time.time()
        end = time.time() + wait
        while not AG['q']:
            left = end - time.time()
            if left <= 0:
                break
            AG['cv'].wait(min(left, 5))
            AG['last'] = time.time()
            if AG['q']:
                break
        q = AG['q']
        AG['q'] = []
        return q

def agent_result(cid: str, data: dict) -> None:
    with AG['cv']:
        AG['res'][cid] = data
        AG['cv'].notify_all()

def handle_get(path: str, q: dict):
    import hl_pro
    r = hl_pro.handle_get(path, q)
    if r is not None:
        return r
    if path == '/api/hl/info':
        return 'json', {
            'ok': True,
            'cit': cit_ok(),
            'citEngine': _CIT.get('engine', ''),
            'citExe': bool(cit_exe()),
            'clones': clones(),
            'voiceFx': fx_list(),
            'clipFx': clip_fx_list(),
            'whisper': wh_status(),
            'ui': agent_ui_online(),
        }
    if path.startswith('/giong-mau/'):
        return 'file', clone_dir() / Path(path).name
    if path == '/api/whisper/status':
        return 'json', {'ok': True, **wh_status()}
    if path.startswith('/api/whisper/job/'):
        return 'json', {'ok': True, **wh_job(path.rsplit('/', 1)[-1])}
    if path == '/api/agent/poll':
        return 'json', {'ok': True, 'cmds': agent_poll(float(q.get('wait', '20')))}
    if path.startswith('/api/aicut/job/'):
        return 'json', {'ok': True, **aicut_job(path.rsplit('/', 1)[-1])}
    if path == '/api/agent/status':
        return 'json', {'ok': True, 'ui': agent_ui_online()}
    return None

def _media_file(url: str) -> Path | None:
    if not url:
        return None
    u = urllib.parse.urlparse(url).path
    if u.startswith('/media/'):
        return Path(CTX['MEDIA_DIR']) / Path(u).name
    if u.startswith('/tts/'):
        return Path(CTX['TTS_DIR']) / Path(u).name
    p = Path(url)
    if p.is_file():
        return p
    return None

def handle_post_raw(path: str, q: dict, body: bytes):
    import hl_pro
    r = hl_pro.handle_post_raw(path, q, body)
    if r is not None:
        return r
    if path == '/api/clone/save':
        return {'ok': True, **clone_save(body, q.get('file', 'giong.webm'), q.get('name', 'Giọng của tôi'), q.get('ref', ''))}
    if path == '/api/whisper/upload':
        f = Path(CTX['HOME']) / 'whisper' / ('mix-' + uuid.uuid4().hex[:8] + '.wav')
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(body)
        return {'ok': True, **wh_start(f, q.get('model', ''), q.get('lang', 'vi'), q.get('prompt', ''))}
    return None

def handle_post(path: str, d: dict):
    import hl_pro
    r = hl_pro.handle_post(path, d)
    if r is not None:
        return r
    if path == '/api/clone/delete':
        clone_delete(d.get('id', ''))
        return {'ok': True, 'clones': clones()}
    if path == '/api/cit/start':
        return {'ok': True, 'cit': cit_start(float(d.get('wait', 60))) and cit_ok(True)}
    if path == '/api/whisper/install':
        return {'ok': True, **wh_install()}
    if path == '/api/whisper/model':
        c = _cfg()
        c['whisper_model'] = d.get('model', 'small')
        CTX['save_cfg'](c)
        return {'ok': True, **wh_status()}
    if path == '/api/whisper/start':
        f = _media_file(d.get('url') or d.get('path') or '')
        if not f or not f.exists():
            raise RuntimeError('Không thấy file âm thanh/video để nghe')
        return {'ok': True, **wh_start(f, d.get('model', ''), d.get('lang', 'vi'), d.get('prompt', ''))}
    if path == '/api/audio-fx':
        return {'ok': True, **audio_fx(d.get('url', ''), d.get('fx', ''))}
    if path == '/api/aicut/start':
        return {'ok': True, **aicut_start(d.get('url', ''), d.get('quality', 'vua'))}
    if path == '/api/agent/result':
        agent_result(d.get('id', ''), d.get('data') or {})
        return {'ok': True}
    if path == '/api/agent/cmd':
        return agent_cmd(d.get('cmd', ''), d.get('args') or {}, float(d.get('timeout', 120)))
    if path == '/api/voice-fx/preview':
        src = _media_file(d.get('url', ''))
        if not src or not src.exists():
            raise RuntimeError('Chưa có giọng để thử')
        out = Path(CTX['TTS_DIR']) / (src.stem + '-' + slug(d.get('fx', '')) + '.wav')
        if not out.exists():
            apply_fx(src, d.get('fx', ''), out)
        return {'ok': True, 'url': '/tts/' + out.name}
    return None

CLIP_FX = {
    'can_am': ('Cân âm lượng (to đều)', 'loudnorm=I=-16:TP=-1.5:LRA=11'),
    'khu_on_manh': ('Khử ồn mạnh (gió, quạt, xe)', 'highpass=f=100,afftdn=nf=-30:nr=18,anlmdn=s=7,loudnorm=I=-16:TP=-1.5'),
}

def audio_fx(url: str, fx: str) -> dict:
    src = _media_file(url)
    if not src or not src.exists():
        raise RuntimeError('Không thấy tiếng của video')
    chain = (CLIP_FX.get(fx) or VOICE_FX.get(fx) or (None, None))[1]
    if not chain:
        return {'url': url}
    base = Path(CTX['MEDIA_DIR']) / f'{src.stem}-afx-{slug(fx)}'
    for ext, codec in (('.ogg', ['-c:a', 'libopus', '-b:a', '160k']), ('.wav', ['-c:a', 'pcm_s16le'])):
        out = Path(str(base) + ext)
        if out.exists():
            return {'url': '/media/' + out.name}
        ff = _ff()
        if not ff:
            raise RuntimeError('Cần ffmpeg')
        r = subprocess.run([
            ff, '-y', '-loglevel', 'error',
            '-i', str(src),
            '-vn',
            '-af', 'aresample=48000,' + chain,
            '-ar', '48000',
            *codec,
            str(out)
        ], capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=NOWIN)
        if r.returncode == 0 and out.exists():
            log(f'[tieng-goc] {fx} → {out.name}')
            return {'url': '/media/' + out.name}
        out.unlink(missing_ok=True)
        log(f"[tieng-goc] hiệu ứng '{fx}' ({ext}) lỗi: {(r.stderr or '')[-200:]}")
    return {'url': url}

def clip_fx_list() -> list[dict]:
    return [{'id': k, 'label': v[0]} for k, v in CLIP_FX.items()] + fx_list()

SEG = {'jobs': {}, 'sess': None}
SEG_URL = 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx'

def _seg_model(J: dict) -> Path:
    d = Path(CTX['APP_DIR']) / 'models'
    d.mkdir(parents=True, exist_ok=True)
    f = d / 'u2net_human_seg.onnx'
    if f.exists() and f.stat().st_size > 100_000_000:
        return f
    J['msg'] = 'Đang tải mô hình tách người (~170 MB, chỉ lần đầu)…'
    tmp = f.with_suffix('.tai')
    with urllib.request.urlopen(SEG_URL, timeout=60) as r:
        with tmp.open('wb') as fh:
            tot = int(r.headers.get('Content-Length') or 0)
            got = 0
            while True:
                b = r.read(1048576)
                if not b:
                    break
                fh.write(b)
                got += len(b)
                if tot:
                    J['msg'] = f'Đang tải mô hình tách người: {got * 100 // tot}% (chỉ lần đầu)'
    tmp.replace(f)
    return f

def _probe(ff: str, src: Path) -> tuple[int, int, float, float, bool]:
    r = subprocess.run([ff, '-i', str(src)], capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=NOWIN)
    e = r.stderr or ''
    m = re.search(r'Video:.*?(\d{2,5})x(\d{2,5})', e)
    w, h = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    rot = re.search(r'rotation of (-?\d+)|rotate\s*:\s*(-?\d+)', e)
    if rot and abs(int(rot.group(1) or rot.group(2))) in (90, 270):
        w, h = h, w
    fm = re.search(r'(\d+(?:\.\d+)?) fps', e)
    fps = float(fm.group(1)) if fm else 30.0
    return w, h, fps, _dur(ff, src), ('Audio:' in e)

def aicut_start(url: str, quality: str = 'vua') -> dict:
    src = _media_file(url)
    if not src or not src.exists():
        raise RuntimeError('Không thấy file video')
    jid = uuid.uuid4().hex[:10]
    J = {'state': 'running', 'pct': 0, 'msg': 'Đang chuẩn bị…'}
    SEG['jobs'][jid] = J

    def run():
        try:
            import numpy as np
            import onnxruntime as ort
            import cv2
            ff = _ff()
            if not ff:
                raise RuntimeError('cần ffmpeg')
            model = _seg_model(J)
            if SEG['sess'] is None:
                so = ort.SessionOptions()
                so.intra_op_num_threads = max(2, (os.cpu_count() or 4) - 1)
                SEG['sess'] = ort.InferenceSession(str(model), so, providers=['CPUExecutionProvider'])
            sess = SEG['sess']
            iname = sess.get_inputs()[0].name
            w0, h0, fps, dur, has_a = _probe(ff, src)
            if not w0:
                raise RuntimeError('không đọc được video')
            mx = {'nhanh': 540, 'vua': 720, 'net': 1080}.get(quality, 720)
            k = min(1.0, mx / max(w0, h0))
            W_ = int(w0 * k) // 2 * 2
            H_ = int(h0 * k) // 2 * 2
            out = Path(CTX['MEDIA_DIR']) / f'{src.stem}-tachnguoi-{quality}.webm'
            tmp = out.with_suffix('.tam.webm')
            rd = subprocess.Popen([
                ff, '-loglevel', 'error',
                '-i', str(src),
                '-vf', f'scale={W_}:{H_}',
                '-f', 'rawvideo',
                '-pix_fmt', 'rgb24',
                '-',
            ], stdout=subprocess.PIPE, creationflags=NOWIN)
            enc = [
                ff, '-y', '-loglevel', 'error',
                '-f', 'rawvideo',
                '-pix_fmt', 'rgba',
                '-s', f'{W_}x{H_}',
                '-r', f'{fps:.3f}',
                '-i', '-',
            ]
            if has_a:
                enc += ['-i', str(src), '-map', '0:v', '-map', '1:a:0', '-c:a', 'libopus', '-b:a', '128k']
            enc += [
                '-c:v', 'libvpx-vp9',
                '-pix_fmt', 'yuva420p',
                '-b:v', '0',
                '-crf', '30',
                '-deadline', 'realtime',
                '-cpu-used', '8',
                '-row-mt', '1',
                '-auto-alt-ref', '0',
                '-shortest',
                str(tmp),
            ]
            wr = subprocess.Popen(enc, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NOWIN)
            mean = np.array([0.485, 0.456, 0.406], np.float32)
            std = np.array([0.229, 0.224, 0.225], np.float32)
            n_tot = max(1, int(dur * fps))
            step = 2 if fps > 40 else 1
            prev = None
            n = 0
            fsz = W_ * H_ * 3
            while True:
                buf = rd.stdout.read(fsz)
                if len(buf) < fsz:
                    break
                img = np.frombuffer(buf, np.uint8).reshape(H_, W_, 3)
                if n % step == 0 or prev is None:
                    x = cv2.resize(img, (320, 320), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
                    x = ((x - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)
                    m = sess.run(None, {iname: x})[0][0, 0]
                    m = (m - m.min()) / max(1e-6, float(m.max() - m.min()))
                    m = cv2.resize(m, (W_, H_), interpolation=cv2.INTER_LINEAR)
                    m = np.clip((m - 0.12) / 0.76, 0, 1)
                    if prev is not None:
                        m = m * 0.7 + prev * 0.3
                    prev = m
                a = (prev * 255).astype(np.uint8)
                a = cv2.GaussianBlur(a, (3, 3), 0)
                rgba = np.dstack([img, a])
                wr.stdin.write(rgba.tobytes())
                n += 1
                J['pct'] = min(99, n * 100 // n_tot)
                J['msg'] = f'AI đang tách người: {n}/{n_tot} hình'
            rd.wait()
            wr.stdin.close()
            err = wr.stderr.read().decode('utf-8', 'ignore') if wr.stderr else ''
            wr.wait()
            if wr.returncode != 0 or not tmp.exists():
                raise RuntimeError('ghi video lỗi: ' + err[-200:])
            tmp.replace(out)
            J.update(
                state='done',
                pct=100,
                msg=f'Xong: đã tách người ({n} hình)',
                url='/media/' + out.name,
                w=W_, h=H_, dur=dur, fps=fps, audio=has_a,
            )
            log(f'[tach-nguoi] {src.name} → {out.name}')
        except Exception as e:
            J.update(state='error', msg=f'Tách người lỗi: {e}')
            log('[tach-nguoi] ' + J['msg'])

    threading.Thread(target=run, daemon=True).start()
    return {'job': jid}

def aicut_job(jid: str) -> dict:
    J = SEG['jobs'].get(jid)
    if not J:
        return {'state': 'error', 'msg': 'Không thấy việc này'}
    return dict(J)
