# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
HOME = Path(os.environ.get('VSP_HOME') or (Path.home() / '.video-san-pham'))
VERSION = '1.0.0'

if hasattr(sys.stdin, 'reconfigure'):
    try:
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def err(msg: str) -> None:
    try:
        sys.stderr.write(str(msg) + '\n')
        sys.stderr.flush()
    except Exception:
        pass


def base() -> str:
    port = os.environ.get('VSP_PORT')
    if port:
        return f"http://127.0.0.1:{port}"
    pf = HOME / 'port.txt'
    if pf.is_file():
        try:
            p = pf.read_text('utf-8').strip()
            if p.isdigit():
                return f"http://127.0.0.1:{p}"
        except Exception:
            pass
    return "http://127.0.0.1:8790"


def http(method: str, path: str, body: dict | None = None, timeout: float = 60.0, raw: bytes | None = None, ctype: str = 'application/json') -> dict:
    if raw is not None:
        data = raw
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    else:
        data = None

    url = base() + path
    headers = {'Content-Type': ctype} if data is not None else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw_res = r.read()
        try:
            return json.loads(raw_res.decode('utf-8'))
        except Exception:
            return {'raw': raw_res.decode('utf-8', 'ignore')}


def alive() -> bool:
    try:
        r = http('GET', '/api/ping', timeout=2)
        return bool(r.get('ok'))
    except Exception:
        return False


def ui_online() -> bool:
    try:
        r = http('GET', '/api/agent/online', timeout=2)
        return bool(r.get('online'))
    except Exception:
        return False


def start_app() -> bool:
    if alive() and ui_online():
        return True
    exe = APP_DIR / 'bin' / 'XuongVideoSanPham.exe'
    if exe.is_file() and os.name == 'nt':
        try:
            subprocess.Popen([str(exe)], cwd=str(APP_DIR))
        except Exception as e:
            err(f"Lỗi mở app exe: {e}")
    else:
        py = sys.executable
        srv = APP_DIR / 'server.py'
        try:
            kwargs = {}
            if os.name == 'nt':
                kwargs['creationflags'] = 0x08000000
            subprocess.Popen([py, str(srv)], cwd=str(APP_DIR), **kwargs)
        except Exception as e:
            err(f"Lỗi mở server.py: {e}")

    for _ in range(30):
        if alive():
            break
        time.sleep(1)
    return alive()


def ui(cmd: str, args: dict | None = None, timeout: float = 120.0) -> dict:
    if not alive() or not ui_online():
        start_app()
    r = http('POST', '/api/agent/cmd', {'cmd': cmd, 'args': args or {}, 'timeout': timeout}, timeout=timeout + 15)
    if not r.get('ok', True):
        raise RuntimeError(r.get('error', 'Lỗi không xác định'))
    return r


def txt(obj) -> list[dict]:
    if isinstance(obj, str):
        return [{'type': 'text', 'text': obj}]
    return [{'type': 'text', 'text': json.dumps(obj, ensure_ascii=False, indent=2)}]


def t_status(a: dict):
    up = alive()
    out = {'server': up, 'app_window': ui_online() if up else False, 'url': base()}
    if up:
        try:
            out['hl'] = http('GET', '/api/hl/info', timeout=5)
            out['hl'].pop('voiceFx', None)
        except Exception:
            pass
    return txt(out)


def t_open(a: dict):
    start_app()
    return txt({'ok': True, 'server': alive(), 'app_window': ui_online()})


def t_get_project(a: dict):
    return txt(ui('get_project', {'include_options': a.get('include_options', False)}))


def t_options(a: dict):
    return txt(ui('options'))


def t_apply(a: dict):
    return txt(ui('apply', {'actions': a.get('actions', [])}))


def t_look(a: dict):
    return txt(ui('set_look', a))


def t_import(a: dict):
    return txt(ui('import_media', {'paths': a.get('paths', [])}))


def t_ai_video(a: dict):
    return txt(ui('ai_make_video', a, timeout=300))


def t_new(a: dict):
    return txt(ui('new_video'))


def t_snapshot(a: dict):
    return txt(ui('snapshot', {'t': a.get('t', 0.0), 'max_width': a.get('max_width')}))


def t_voices(a: dict):
    return txt(ui('generate_voices'))


def t_whisper_captions(a: dict):
    return txt(ui('whisper_captions'))


def t_export(a: dict):
    return txt(ui('export', {'wait_seconds': a.get('wait_seconds', 300)}, timeout=a.get('wait_seconds', 300) + 30))


def t_export_status(a: dict):
    return txt(ui('export_status'))


def t_save(a: dict):
    return txt(ui('save_project', {'name': a.get('name')}))


def t_tts(a: dict):
    return txt(http('POST', '/api/hl/tts', a, timeout=120))


def t_list_voices(a: dict):
    return txt(http('GET', '/api/hl/voices'))


def t_clone(a: dict):
    return txt(http('POST', '/api/hl/clone', a))


def t_transcribe(a: dict):
    return txt(http('POST', '/api/hl/transcribe', a, timeout=300))


def t_cit_start(a: dict):
    return txt(http('POST', '/api/hl/cit/start', timeout=120))


ACT_HELP = (
    'Danh sách lệnh (scene = số thứ tự cảnh từ 1): {"do":"set","scene":3,"key":"<ô p của cảnh>","value":"..."} · '
    '{"do":"voice","scene":3,"text":"lời đọc"} · {"do":"trans","scene":3,"value":"<mã chuyển cảnh>"} · '
    '{"do":"dur","scene":3,"value":4.5} · {"do":"toggle","scene":3,"on":false} · {"do":"remove","scene":3} · '
    '{"do":"move","scene":3,"to":1} · {"do":"add","type":"<loại cảnh>","after":2,"p":{...},"trans":"chop","voice":"..."} · '
    '{"do":"theme","value":"gold|brand|studio"} · {"do":"color","value":"#RRGGBB"} · '
    '{"do":"music","value":"dien_anh|soi_dong|nhe|khong"} · {"do":"musicVol","value":0.8} · '
    '{"do":"voiceName","value":"<id giọng>"} · {"do":"voiceOn","value":true} · {"do":"subtitles","value":true} · '
    '{"do":"product","name":"...","eyebrow":"...","features":["..."]} · {"do":"brand","name":"...","phone":"...","web":"..."} · '
    '{"do":"remix"} · {"do":"look","filter":"<mã bộ lọc|none>","amount":0.8,"scene":3?} · '
    '{"do":"effect","value":"<mã hiệu ứng|none>","amount":0.7,"scene":3?} · '
    '{"do":"voiceFx","value":"<mã hiệu ứng giọng|none>","scene":3?} · '
    '{"do":"key","scene":3,"on":true,"color":"#00ff00"} (phông xanh cảnh video) · '
    '{"do":"format","value":"portrait|landscape|square"} · '
    '{"do":"layer_text","text":"GIẢM 20%","start":0,"end":3,"x":10,"y":70,"width":80,"size":80,"color":"#ffd400","motion":"<mã chuyển động>"} · '
    '{"do":"layer_media","media":"<id hoặc tên ảnh/video>","start":0,"end":5,"x":5,"y":50,"width":90,"key":true,"motion":"bay_trai"} · '
    '{"do":"layer_motion","layer":1,"value":"<mã chuyển động>"} · {"do":"layer_remove","layer":1} · '
    '{"do":"captions","items":[{"start":0,"end":2.5,"text":"..."}]} · '
    '{"do":"adjust","scene":3?,"exp":0.2,"con":0.1,"sh":0.3,"hi":-0.2,"temp":0.3,"tint":0,"sat":0.1,"vib":0.2,"hue":0,"sharp":0.3,"fade":0,"vig":0.2,"grain":0,"shCol":"#2060ff","hiCol":"#ffa040","split":0.3,"curve":"s|matte|none","auto":true,"reset":true} (chỉnh màu tay) · '
    '{"do":"text_style","layer":1,"preset":"<mã mẫu chữ>","anim":"go|tung_tu|song|nhip|","color":"#fff","style":{"font":"Arial","weight":800,"align":"center","stroke":"#000","strokeW":0.1,"shadow":"#000","shadowB":0.3,"bg":"#e11d2e","bgA":1,"grad":"#ff6a00","upper":true}} · '
    '{"do":"layer_region","start":0,"end":5,"x":30,"y":40,"width":40,"height":10,"shape":"|bo_goc|elip","mode":"mo|pixel|mau|noi","amount":0.7,"feather":0.2,"color":"#000","invert":false} (che/làm mờ/làm nổi vùng; dùng layer_motion hoặc keyframe để bám theo vật) · '
    '{"do":"layer_transform","layer":2,"flipH":true,"crop":{"l":10,"r":10,"t":0,"b":0},"shape":"tron|bo_goc|","feather":0.3,"rot":5} · '
    '{"do":"video_transform","scene":2,"zoom":1.2,"panX":5,"panY":0,"rot90":90,"flipH":true,"cropL":5,"cropR":5,"cropT":0,"cropB":0} · '
    '{"do":"split","t":12.5} (tách cảnh tại giây t) · {"do":"trim","t":3.2,"side":"start|end"} · '
    '{"do":"clip_audio","scene":2,"vol":1.2,"fx":"<mã: can_am, khu_on_manh, lam_sach, …|none>"} · '
    '{"do":"music_fade","in":1.5,"out":2,"points":[{"t":0,"v":0.3},{"t":10,"v":1}]} · '
    '{"do":"export_settings","res":"1080|1440|2160","fps":30,"codec":"h264|hevc","quality":"cao|vua|nhe"}. '
    'Mã cảnh, chuyển cảnh, bộ lọc, hiệu ứng, giọng, chuyển động lớp: gọi hl_get_project với include_options=true.'
)

TOOLS = [
    ('hl_status', 'Kiểm tra HL Studio (máy chủ, cửa sổ app, CIT Voice Studio, dự án đang mở). Gọi đầu tiên.', {}, t_status),
    ('hl_open_app', 'Mở cửa sổ HL Studio nếu chưa mở (mất tới 1–2 phút lần đầu).', {}, t_open),
    ('hl_get_project', 'Đọc dự án video đang mở: các cảnh, lời đọc, bộ lọc, lớp chữ/ảnh, thư viện ảnh/video. include_options=true để lấy thêm mã mẫu, hiệu ứng...', {'include_options': {'type': 'boolean'}}, t_get_project),
    ('hl_apply', f"Sửa video bằng danh sách lệnh, chạy đúng thứ tự. {ACT_HELP}", {'actions': {'type': 'array', 'items': {'type': 'object'}, 'description': 'Danh sách lệnh'}}, t_apply),
    ('hl_set_look', 'Đổi nhanh bộ lọc màu / hiệu ứng phủ (cả video hoặc 1 cảnh) và chuyển cảnh vào cảnh đó.', {
        'filter': {'type': 'string', 'description': "mã bộ lọc, VD hoang_hon, hollywood, ngon_mat, noir; 'none' = bỏ"},
        'filter_amount': {'type': 'number'},
        'effect': {'type': 'string', 'description': "mã hiệu ứng phủ, VD ro_sang, bui_roi, mua, vhs, lap_lanh; 'none' = bỏ"},
        'effect_amount': {'type': 'number'},
        'scene': {'type': 'integer', 'description': 'bỏ trống = cả video'},
        'transition': {'type': 'string', 'description': 'mã chuyển cảnh vào cảnh này, VD tim, dong_ho, chay_phim'},
    }, t_look),
    ('hl_import_media', 'Nhập ảnh/video trên máy vào thư viện (đường dẫn file đầy đủ). Đưa đường dẫn thư mục thì app tự xem các video và dựng luôn.', {'paths': {'type': 'array', 'items': {'type': 'string'}}}, t_import),
    ('hl_ai_make_video', 'AI của HL Studio xem ảnh trong thư viện rồi tự dựng cả video (1–3 phút).', {
        'info': {'type': 'string', 'description': 'thông tin sản phẩm/công ty'},
        'length': {'type': 'integer', 'enum': [15, 25, 40, 60]},
        'format': {'type': 'string', 'enum': ['portrait', 'landscape', 'square']},
        'style': {'type': 'string', 'enum': ['tu_chon', 'gold', 'brand', 'studio']},
        'revision': {'type': 'string', 'description': 'dặn thêm'},
    }, t_ai_video),
    ('hl_new_video', 'Xoá dự án đang mở để làm video mới (giữ thương hiệu mặc định).', {}, t_new),
    ('hl_snapshot', 'Chụp 1 khung hình video tại giây t để xem kết quả (trả ảnh).', {'t': {'type': 'number'}, 'max_width': {'type': 'integer'}}, t_snapshot),
    ('hl_generate_voices', 'Đọc giọng (lồng tiếng) cho mọi cảnh có lời đọc.', {}, t_voices),
    ('hl_whisper_captions', 'Whisper nghe âm thanh cả video và điền phụ đề theo mốc thời gian (chạy trên máy).', {}, t_whisper_captions),
    ('hl_export', 'Xuất video MP4. Chờ tối đa wait_seconds rồi trả đường dẫn file (hoặc trạng thái nếu chưa xong).', {'wait_seconds': {'type': 'integer'}}, t_export),
    ('hl_export_status', 'Xem tiến độ xuất video.', {}, t_export_status),
    ('hl_save_project', 'Lưu dự án thành file có tên.', {'name': {'type': 'string'}}, t_save),
    ('hl_tts', 'Đọc một đoạn văn bản ra file WAV (không cần cửa sổ app). voice: id giọng (cit:Tên, clone:id, vieneu:Tên, edge:…); fx: mã hiệu ứng.', {
        'text': {'type': 'string'},
        'voice': {'type': 'string'},
        'fx': {'type': 'string'},
        'pron': {'type': 'string', 'description': 'cách đọc riêng, mỗi dòng: chữ = cách đọc'},
        'save_to': {'type': 'string'},
    }, t_tts),
    ('hl_list_voices', 'Liệt kê giọng đọc (VieNeu, CIT, giọng nhân bản, Edge) và hiệu ứng giọng.', {}, t_list_voices),
    ('hl_clone_voice', 'Lưu giọng mẫu 3–8 giây để nhân bản giọng (cần CIT Voice Studio). Chỉ dùng giọng của người đã đồng ý.', {
        'audio_path': {'type': 'string'},
        'name': {'type': 'string'},
        'ref_text': {'type': 'string', 'description': 'câu nói trong file mẫu (không bắt buộc)'},
    }, t_clone),
    ('hl_transcribe', 'Whisper nghe file âm thanh/video trên máy → phụ đề (SRT). install=true để cài Whisper nếu chưa có.', {
        'path': {'type': 'string'},
        'model': {'type': 'string', 'enum': ['base', 'small', 'medium', 'large-v3-turbo']},
        'language': {'type': 'string'},
        'srt_path': {'type': 'string'},
        'install': {'type': 'boolean'},
        'wait_seconds': {'type': 'integer'},
    }, t_transcribe),
    ('hl_ai_cut_person', 'AI tách người khỏi nền video của 1 cảnh video (không cần phông xanh, chạy CPU 1–3 phút/10 giây video). background = id/màu/ảnh.', {
        'scene': {'type': 'integer'},
        'quality': {'type': 'string', 'enum': ['nhanh', 'vua', 'net']},
        'background': {'type': 'string'},
    }, lambda a: txt(ui('ai_cut_person', a))),
    ('hl_cit_start', 'Mở CIT Voice Studio (giọng VieNeu-TTS v3 48 kHz) và chờ sẵn sàng.', {}, t_cit_start),
]

REQUIRED = {
    'hl_ai_cut_person': ['scene'],
    'hl_apply': ['actions'],
    'hl_import_media': ['paths'],
    'hl_tts': ['text'],
    'hl_clone_voice': ['audio_path'],
    'hl_transcribe': ['path'],
}

INSTRUCTIONS = (
    'HL Studio là phần mềm làm video quảng cáo sản phẩm (dọc 9:16 TikTok/Reels, ngang 16:9, vuông). '
    'Quy trình gợi ý: hl_status → hl_import_media (ảnh/video sản phẩm) → hl_ai_make_video → '
    'hl_get_project(include_options=true) → hl_apply / hl_set_look để chỉnh → hl_snapshot để tự xem lại → '
    'hl_generate_voices → hl_export. Không bịa giá, thông số. Giữ chữ trên màn hình ngắn (≤ 6 chữ/dòng).'
)


def handle(msg: dict):
    m = msg.get('method')
    mid = msg.get('id')

    if m == 'initialize':
        pv = msg.get('params', {}).get('protocolVersion') or '2025-06-18'
        return {
            'jsonrpc': '2.0',
            'id': mid,
            'result': {
                'protocolVersion': pv,
                'capabilities': {'tools': {'listChanged': False}},
                'serverInfo': {'name': 'hl-studio', 'version': VERSION},
                'instructions': INSTRUCTIONS,
            },
        }

    if m == 'tools/list':
        out = []
        for name, desc, props, _ in TOOLS:
            out.append({
                'name': name,
                'description': desc,
                'inputSchema': {
                    'type': 'object',
                    'properties': props,
                    'required': REQUIRED.get(name, []),
                },
            })
        return {'jsonrpc': '2.0', 'id': mid, 'result': {'tools': out}}

    if m == 'tools/call':
        params = msg.get('params', {})
        tname = params.get('name')
        args = params.get('arguments', {})
        for name, _, _, fn in TOOLS:
            if name == tname:
                try:
                    res = fn(args)
                    return {'jsonrpc': '2.0', 'id': mid, 'result': {'content': res}}
                except Exception as e:
                    return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32000, 'message': str(e)}}
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f"Tool '{tname}' không tồn tại"}}

    if m == 'notifications/initialized':
        return None

    return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f"Method '{m}' không hỗ trợ"}}


def main():
    err(f"HL Studio MCP {VERSION} · {APP_DIR}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        res = handle(msg)
        if res is not None:
            sys.stdout.write(json.dumps(res, ensure_ascii=False) + '\n')
            sys.stdout.flush()


if __name__ == '__main__':
    main()
