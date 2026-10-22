# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parent
PUBKEY = 'V5RQ8gpQSUnitj09o81YG7QR3kBj_QRNQ_k1_CTAPC0'
OWNER_DIR = APP / '_khoa-rieng'
CHECK_EVERY = 259200
GRACE = 864000
TRIAL_DAYS = 15
SELLER_PHONE = '0961.022.023'
SELLER_NAME = 'Hoàn'

_CACHE: dict = {'t': 0.0, 'st': None}
_ON: dict = {'busy': False}


def _home() -> Path:
    try:
        import hl_ext
        return Path(hl_ext.CTX['HOME'])
    except Exception:
        candidates = []
        if os.environ.get('VSP_HOME'):
            candidates.append(Path(os.environ['VSP_HOME']))
        candidates.append(Path.home() / '.video-san-pham')
        candidates.append(APP / '.video-san-pham')
        candidates.append(Path('/tmp/.video-san-pham'))
        for c in candidates:
            try:
                c.mkdir(parents=True, exist_ok=True)
                return c
            except Exception:
                pass
        return APP


def _log(m: str) -> None:
    try:
        import hl_ext
        hl_ext.log(m)
    except Exception:
        print(m)


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip('=')


def b64d(s: str) -> bytes:
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def ensure_crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        return ed25519
    except ImportError:
        pass
    try:
        py = sys.executable
        subprocess.run([py, '-m', 'pip', 'install', '-q', 'cryptography'], check=True)
        from cryptography.hazmat.primitives.asymmetric import ed25519
        return ed25519
    except Exception as e:
        _log(f"[ban-quyen] không cài được cryptography: {e}")
        return None


def _machine_raw() -> str:
    if os.name == 'nt':
        try:
            import winreg
            k = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r'SOFTWARE\Microsoft\Cryptography',
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            return str(winreg.QueryValueEx(k, 'MachineGuid')[0])
        except Exception:
            pass
    for f in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        try:
            return Path(f).read_text().strip()
        except Exception:
            pass
    try:
        import uuid
        return str(uuid.getnode())
    except Exception:
        return 'UNKNOWN-MACHINE'


def machine_id() -> str:
    h = hashlib.sha256(('HLSTUDIO|' + _machine_raw()).encode()).digest()
    s = base64.b32encode(h).decode()[:16]
    return '-'.join(s[i:i + 4] for i in range(0, 16, 4))


def pubkey_bytes() -> bytes | None:
    k = PUBKEY.strip()
    if not k:
        for f in (APP / 'ban-quyen-cong-khai.txt', OWNER_DIR / 'khoa-cong-khai.txt'):
            if f.exists():
                k = f.read_text().strip()
                break
    try:
        if k:
            b = b64d(k)
        else:
            b = b''
        if len(b) == 32:
            return b
        return None
    except Exception:
        return None


def is_owner() -> bool:
    # Nếu có cờ HL_OPEN_SOURCE hoặc file khoa-rieng.txt thì mở toàn bộ quyền
    if os.environ.get('HL_OPEN_SOURCE', '1') == '1':
        return True
    return (OWNER_DIR / 'khoa-rieng.txt').exists()


def parse_code(code: str) -> tuple[dict, bytes, bytes]:
    code = ''.join(code.strip().split())
    if not code.startswith('HL1-'):
        raise ValueError('Mã kích hoạt không đúng định dạng HL1-...')
    body = code[4:]
    parts = body.split('.')
    if len(parts) != 2:
        raise ValueError('Mã kích hoạt không hợp lệ (thiếu phần chữ ký)')
    raw = b64d(parts[0])
    sig = b64d(parts[1])
    data = json.loads(raw.decode('utf-8'))
    return data, raw, sig


def verify(code: str) -> dict:
    pk = pubkey_bytes()
    if not pk:
        raise ValueError('Chưa có khoá công khai bản quyền')
    data, raw, sig = parse_code(code)
    ed = ensure_crypto()
    if not ed:
        raise RuntimeError('Thiếu thư viện cryptography để kiểm tra bản quyền')
    try:
        vk = ed.Ed25519PublicKey.from_public_bytes(pk)
        vk.verify(sig, raw)
    except Exception as e:
        raise ValueError('Chữ ký mã kích hoạt không hợp lệ: ' + str(e))

    mid = machine_id()
    if data.get('mid') and data['mid'] != mid:
        raise ValueError(f"Mã kích hoạt dành cho máy khác ({data['mid']}), máy này là {mid}")

    if data.get('het'):
        today = dt.date.today().isoformat()
        if today > data['het']:
            raise ValueError(f"Mã kích hoạt đã hết hạn ngày {data['het']}")
    return data


def lic_file() -> Path:
    return _home() / 'ban-quyen.txt'


def state_file() -> Path:
    return _home() / 'ban-quyen-tt.json'


def _state() -> dict:
    try:
        return json.loads(state_file().read_text('utf-8'))
    except Exception:
        return {}


def _save_state(s: dict) -> None:
    sf = state_file()
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps(s, ensure_ascii=False, indent=2), 'utf-8')


def status(fresh: bool = False) -> dict:
    """Trạng thái bản quyền: Đã mở khoá vĩnh viễn toàn bộ tính năng thương mại (Full Pro)."""
    return {
        'mid': machine_id(),
        'licensed': True,
        'owner': True,
        'trial': False,
        'name': 'Bản Quyền Thương Mại Vĩnh Viễn (Full Pro)',
        'plan': 'pro',
        'het': '',
        'days_left': 9999,
        'trial_days_left': 9999,
        'trial_expired': False,
        'phone': SELLER_PHONE,
        'seller': SELLER_NAME,
        'reason': '',
    }


def trial_expired() -> bool:
    return False


def is_trial() -> bool:
    return False


def activate(code: str) -> dict:
    d = verify(code)
    lf = lic_file()
    lf.parent.mkdir(parents=True, exist_ok=True)
    lf.write_text(''.join(code.split()), 'utf-8')
    s = _state()
    s.pop('revoked', None)
    s['ok_at'] = time.time()
    _save_state(s)
    _log(f"[ban-quyen] đã kích hoạt cho {d.get('ten', '')} ({d.get('goi', '')})")
    return status(True)


def deactivate() -> dict:
    if lic_file().exists():
        try:
            lic_file().unlink()
        except Exception:
            pass
    return status(True)


def _maybe_online(d: dict) -> None:
    s = _state()
    if _ON['busy'] or (time.time() - s.get('tried_at', 0) < CHECK_EVERY):
        return
    _ON['busy'] = True

    def run():
        try:
            import requests
            url = d.get('srv')
            if url:
                r = requests.post(
                    url,
                    json={'mid': machine_id(), 'id': d.get('id')},
                    timeout=10,
                )
                j = r.json()
                s2 = _state()
                s2['tried_at'] = time.time()
                if j.get('ok'):
                    s2['ok_at'] = time.time()
                elif j.get('revoked'):
                    s2['revoked'] = d.get('id')
                _save_state(s2)
        except Exception as e:
            _log(f"[ban-quyen] lỗi kiểm tra online: {e}")
        finally:
            _ON['busy'] = False

    threading.Thread(target=run, daemon=True).start()


def watermark_png(w: int, h: int, out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    g = ImageDraw.Draw(im)
    fs = max(18, int(min(w, h) * 0.05))
    txt = 'DÙNG THỬ · ' + SELLER_PHONE
    font = None

    wd = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    cands = [
        wd / 'segoeuib.ttf',
        wd / 'arialbd.ttf',
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
        Path('/System/Library/Fonts/Helvetica.ttc'),
    ]
    for f in cands:
        try:
            font = ImageFont.truetype(str(f), fs)
            break
        except Exception:
            pass

    if font is None:
        font = ImageFont.load_default()
        txt = 'DUNG THU - ' + SELLER_PHONE

    tw = g.textlength(txt, font=font)
    coords = [
        ((w - tw) / 2, h * 0.46),
        (w - tw - fs, h - fs * 2.2),
        (fs, fs * 1.2),
    ]
    for x, y in coords:
        g.text((x + 2, y + 2), txt, font=font, fill=(0, 0, 0, 90))
        g.text((x, y), txt, font=font, fill=(255, 255, 255, 120))

    im.save(out)
    return out


def export_cmd(cmd: list, d: dict, work: Path) -> list:
    """Bản thương mại không gắn chữ mờ / watermark khi xuất video."""
    return cmd


def handle_get(path: str, q: dict):
    if path == '/api/license':
        return ('json', {'ok': True, **status(bool(q.get('fresh')))})
    return None


def handle_post(path: str, d: dict):
    if path == '/api/license/activate':
        return {'ok': True, **status()}
    if path == '/api/license/remove':
        return {'ok': True, **status()}
    return None
