# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

NOWIN = 0x08000000 if os.name == 'nt' else 0

NAMES = {
    'antigravity': 'Antigravity (tài khoản Google)',
    'gemini_cli': 'Gemini CLI (tài khoản Google)',
    'codex': 'Codex (tài khoản ChatGPT)',
    'claude': 'Claude Code (tài khoản Claude)',
    'api': 'Gemini API key',
}

EXE = {
    'antigravity': 'agy',
    'gemini_cli': 'gemini',
    'codex': 'codex',
    'claude': 'claude',
}

INSTALL = {
    'antigravity': 'winget install Google.AntigravityCLI  rồi gõ: agy  (đăng nhập tài khoản Google một lần, xong gõ /quit)',
    'gemini_cli': 'npm i -g @google/gemini-cli  rồi gõ: gemini  (chọn Login with Google)',
    'codex': 'npm i -g @openai/codex  rồi gõ: codex login  (đăng nhập ChatGPT)',
    'claude': 'npm i -g @anthropic-ai/claude-code  rồi gõ: claude  (đăng nhập tài khoản Claude)',
}

ORDER = ('antigravity', 'gemini_cli', 'codex', 'claude')

_home: Path | None = None
_lock = threading.Lock()
_cache: dict = {}

GEMINI_PERSONAL_BLOCKED = (
    "Google đã ngừng cho tài khoản Google cá nhân (kể cả gói Google AI Pro/Ultra) dùng Gemini CLI từ 18/06/2026, "
    "nên đăng nhập bằng Google sẽ báo lỗi IneligibleTierError. "
    "Anh chuyển sang dùng Antigravity (gõ agy) hoặc Codex (ChatGPT) hoặc Claude Code."
)

_BLOCK_RE = re.compile(r'no longer supported|not eligible|ineligible|IneligibleTierError', re.I)
_DENIED_RE = re.compile(r'auto-denied|cannot prompt|permissions\.allow|dangerously-skip-permissions|soft-denied', re.I)
_FALLBACK_ERR = ('hết hạn mức', 'quota', 'quá tải', '429', '503', 'chưa có api key', 'không trả lời được', 'mất kết nối', 'không hợp lệ')


def setup(home: Path) -> None:
    global _home
    _home = Path(home)


def _cfg_file() -> Path:
    h = _home or (Path.home() / '.video-san-pham')
    return h / 'ai_cli.json'


def get_cfg() -> dict:
    f = _cfg_file()
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'provider': 'auto'}


def set_cfg(provider: str) -> dict:
    d = {'provider': provider}
    f = _cfg_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    return d


def find_exe(kind: str) -> str | None:
    name = EXE.get(kind)
    if not name:
        return None
    p = shutil.which(name)
    if p:
        return p
    cands = []
    if os.name == 'nt':
        ad = os.environ.get('APPDATA', '')
        la = os.environ.get('LOCALAPPDATA', '')
        if ad:
            cands.append(Path(ad) / 'npm' / f"{name}.cmd")
        if la:
            cands.append(Path(la) / 'Programs' / name / f"{name}.exe")
            cands.append(Path(la) / 'Microsoft' / 'WinGet' / 'Links' / f"{name}.exe")
    else:
        cands.append(Path('/usr/local/bin') / name)
        cands.append(Path.home() / '.local' / 'bin' / name)

    for c in cands:
        if c.is_file():
            return str(c)
    return None


def _logged_in(kind: str) -> bool | None:
    h = Path.home()
    if kind == 'antigravity':
        return (h / '.gemini' / 'antigravity-cli').exists() or (h / '.gemini' / 'antigravity').exists()
    if kind == 'gemini_cli':
        return (h / '.gemini' / 'oauth_creds.json').exists()
    if kind == 'codex':
        p = Path(os.environ.get('CODEX_CONFIG_DIR') or (h / '.codex'))
        return (p / 'auth.json').exists()
    if kind == 'claude':
        return (h / '.claude' / 'credentials.json').exists()
    return None


def status() -> dict:
    cfg = get_cfg()
    cur = cfg.get('provider', 'auto')
    items = []
    for k in ('antigravity', 'gemini_cli', 'codex', 'claude'):
        exe = find_exe(k)
        in_ = _logged_in(k) if exe else False
        items.append({
            'kind': k,
            'name': NAMES.get(k, k),
            'found': bool(exe),
            'path': exe or '',
            'logged_in': in_,
            'install': INSTALL.get(k, ''),
        })
    return {'provider': cur, 'items': items}


def _real_error(se: str, so: str, rc: int) -> str:
    err = (se or so or f"exit code {rc}").strip()
    if _BLOCK_RE.search(err):
        return GEMINI_PERSONAL_BLOCKED
    return err


def _env(kind: str) -> dict:
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def _save_images(images: list[bytes], d: Path) -> list[Path]:
    out = []
    for i, b in enumerate(images):
        f = d / f"image_{i + 1}.png"
        f.write_bytes(b)
        out.append(f)
    return out


def _run(cmd: list[str], stdin: str | None, cwd: Path, kind: str, timeout: int = 300) -> tuple[int, str, str]:
    kwargs = {
        'cwd': str(cwd),
        'capture_output': True,
        'text': True,
        'encoding': 'utf-8',
        'timeout': timeout,
        'env': _env(kind),
    }
    if os.name == 'nt':
        kwargs['creationflags'] = NOWIN
    r = subprocess.run(cmd, input=stdin, **kwargs)
    return r.returncode, r.stdout, r.stderr


def _agy_transcript(cwd: Path, since: float) -> str:
    t_file = cwd / '.gemini' / 'antigravity' / 'transcript.jsonl'
    if not t_file.is_file():
        return ''
    lines = []
    try:
        for line in t_file.read_text(encoding='utf-8').splitlines():
            j = json.loads(line)
            if j.get('created_at', 0) >= since:
                lines.append(j.get('content', ''))
    except Exception:
        pass
    return '\n'.join(lines)


def _cmdlen(cmd: list[str]) -> int:
    return sum(len(x) for x in cmd)


def _agy_allow_read(d: Path) -> None:
    agy_dir = d / '.gemini' / 'antigravity'
    agy_dir.mkdir(parents=True, exist_ok=True)


def _agy_ask(exe: str, rule: str, system: str, user: str, names: list[str], d: Path, timeout: int = 300, log=print) -> str:
    full = f"{rule}\n\n### HƯỚNG DẪN\n{system}\n\n### YÊU CẦU\n{user}"
    cmd = [exe, '--mode', 'plan', '--disable-slash-commands', '--print-timeout', str(max(60, timeout - 20))]
    rc, so, se = _run(cmd, stdin=full, cwd=d, kind='antigravity', timeout=timeout)
    if rc != 0:
        raise RuntimeError(_real_error(se, so, rc))
    return so.strip()


def ask(kind: str, system: str, user: str, images: list[bytes] | None = None, log=print, timeout: int = 300) -> str:
    if kind == 'auto':
        cfg = get_cfg()
        p = cfg.get('provider', 'auto')
        kind = p if p != 'auto' else 'antigravity'

    exe = find_exe(kind)
    if not exe:
        raise RuntimeError(f"Chưa cài {NAMES.get(kind, kind)}. Hướng dẫn: {INSTALL.get(kind, '')}")

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        saved = _save_images(images or [], d)
        names = [f.name for f in saved]
        rule = "Chỉ trả về JSON thuần tuý, không giải thích gì thêm."
        if kind == 'antigravity':
            return _agy_ask(exe, rule, system, user, names, d, timeout, log)

        full = f"{system}\n\n{user}"
        cmd = [exe]
        rc, so, se = _run(cmd, stdin=full, cwd=d, kind=kind, timeout=timeout)
        if rc != 0:
            raise RuntimeError(_real_error(se, so, rc))
        return so.strip()


def to_json(txt: str) -> dict:
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


def ask_json(kind: str, system: str, user: str, images: list[bytes] | None = None, log=print, timeout: int = 300) -> dict:
    try:
        txt = ask(kind, system, user, images, log, timeout)
        return to_json(txt)
    except Exception:
        txt = ask(kind, system, user + "\n\nLƯU Ý: lần trước trả lời sai định dạng. CHỈ trả về MỘT khối JSON hợp lệ, không chữ nào khác.", images, log, timeout)
        return to_json(txt)


def test(kind: str, log=print) -> bool:
    try:
        res = ask(kind, "Trả về 'OK'.", "Kiểm tra kết nối.", log=log, timeout=30)
        return 'ok' in res.lower()
    except Exception as e:
        if log:
            log(f"Test {kind} thất bại: {e}")
        return False


def _order(prov: str) -> list[str]:
    if prov in ORDER:
        return [prov] + [x for x in ORDER if x != prov]
    return list(ORDER)


def _via(fn_api, fn_cli, log=print, fn_oa=None):
    prov = get_cfg().get('provider', 'auto')
    if prov == 'openai' and fn_oa:
        return fn_oa()

    if os.environ.get('VSP_FAKE_AI') and not os.environ.get('VSP_TEST_CLI'):
        return fn_api()

    if prov == 'gemini_cli':
        prov = 'antigravity'

    if prov in ORDER and find_exe(prov):
        try:
            return fn_cli()
        except Exception as e:
            if log:
                log(f"[cli] {prov} lỗi: {e}, thử API...")

    return fn_api()


def install(media_ai_mod, studio_ext_mod, log_default=print) -> None:
    pass


def _find_paths(obj, out: list) -> None:
    if isinstance(obj, str) and (obj.endswith('.png') or obj.endswith('.jpg')):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _find_paths(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _find_paths(v, out)


def gen_images(src: bytes, brief: str, n: int = 1, size: str = '1024x1024', log=print, state=None, timeout: int = 900) -> list[bytes]:
    exe = find_exe('codex')
    if not exe:
        raise RuntimeError('Chưa cài Codex. Mở cmd gõ: npm i -g @openai/codex  rồi: codex login')

    base = (_home / 'ai-tam') if _home else (Path(tempfile.gettempdir()) / 'ai-tam')
    d = base / f"anh-{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True, exist_ok=True)

    sp = d / 'input.png'
    sp.write_bytes(src)

    prompt = f"Tạo {n} ảnh mới từ ảnh sản phẩm {sp.name} theo yêu cầu: {brief}. Lưu các ảnh ra thư mục hiện tại dạng anh_1.png, anh_2.png... Kích thước: {size}."
    cmd = [exe, 'exec', prompt]
    rc, so, se = _run(cmd, stdin=None, cwd=d, kind='codex', timeout=timeout)
    if rc != 0:
        raise RuntimeError(_real_error(se, so, rc))

    out = []
    for f in sorted(d.glob('*.png')):
        if f.name != 'input.png':
            out.append(f.read_bytes())
    return out
