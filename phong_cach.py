# -*- coding: utf-8 -*-
from __future__ import annotations

import random
import re

PACKS = [
    {
        'id': 'cam_dem',
        'ten': 'Cam cháy & xanh đêm',
        'bg': ['#0B1E3F', '#FF6B1A'],
        'more': ['#1F4E79', '#FFE8D6'],
        'accent': '#FFD23F',
        'fx': ['sunburst', 'stripes'],
        'music': 'soi_dong',
        'char': {
            'skin': '#F6C9A4',
            'hair': '#1B1B1F',
            'top': '#FF6B1A',
            'bottom': '#0B1E3F',
            'shoe': '#FFFFFF',
            'hairStyle': 'spiky',
            'detail': 'hoodie',
        },
    },
    {
        'id': 'hong_tim',
        'ten': 'Hồng neon & tím than',
        'bg': ['#24124A', '#FF3D8B'],
        'more': ['#5B2A86', '#FFE3EF'],
        'accent': '#3DF5FF',
        'fx': ['glow', 'halftone'],
        'music': 'soi_dong',
        'char': {
            'skin': '#FFD9C2',
            'hair': '#7A2E8E',
            'top': '#3DF5FF',
            'bottom': '#24124A',
            'shoe': '#FF3D8B',
            'hairStyle': 'bun',
            'detail': 'none',
        },
    },
    {
        'id': 'la_vang',
        'ten': 'Xanh lá rừng & vàng chanh',
        'bg': ['#0E3B2E', '#F4F1E6'],
        'more': ['#2E7D5B', '#FFE9A8'],
        'accent': '#C6FF3D',
        'fx': ['paper', 'grid'],
        'music': 'nhe',
        'char': {
            'skin': '#E9B98F',
            'hair': '#4A2B12',
            'top': '#C6FF3D',
            'bottom': '#0E3B2E',
            'shoe': '#2B2B2B',
            'hairStyle': 'cap',
            'detail': 'vest',
        },
    },
    {
        'id': 'do_kem',
        'ten': 'Đỏ cờ & kem sữa (kiểu báo)',
        'bg': ['#C8102E', '#FFF4E0'],
        'more': ['#1D1D1F', '#FFD6A5'],
        'accent': '#111111',
        'fx': ['halftone', 'paper'],
        'music': 'dien_anh',
        'char': {
            'skin': '#F2C4A0',
            'hair': '#2A1A12',
            'top': '#FFF4E0',
            'bottom': '#111111',
            'shoe': '#C8102E',
            'hairStyle': 'bob',
            'detail': 'tie',
        },
    },
    {
        'id': 'bien_cat',
        'ten': 'Xanh biển & cát vàng',
        'bg': ['#003F5C', '#FFB703'],
        'more': ['#0A7EA4', '#FFF3D6'],
        'accent': '#FFFFFF',
        'fx': ['stripes', 'sunburst'],
        'music': 'nhe',
        'char': {
            'skin': '#D9A57A',
            'hair': '#111827',
            'top': '#FFB703',
            'bottom': '#003F5C',
            'shoe': '#FFFFFF',
            'hairStyle': 'puff',
            'detail': 'apron',
        },
    },
    {
        'id': 'den_vang',
        'ten': 'Đen tuyền & vàng cảnh báo',
        'bg': ['#111111', '#FFD600'],
        'more': ['#2B2B2B', '#FFF8D6'],
        'accent': '#FF3B30',
        'fx': ['stripes', 'grid'],
        'music': 'dien_anh',
        'char': {
            'skin': '#F0C7A2',
            'hair': '#3B3B3B',
            'top': '#FFD600',
            'bottom': '#111111',
            'shoe': '#FF3B30',
            'hairStyle': 'cap',
            'detail': 'vest',
        },
    },
    {
        'id': 'tim_mint',
        'ten': 'Tím nho & bạc hà',
        'bg': ['#3A0CA3', '#B8F2E6'],
        'more': ['#6A1FD0', '#FFF0F6'],
        'accent': '#F72585',
        'fx': ['glow', 'halftone'],
        'music': 'soi_dong',
        'char': {
            'skin': '#FFDCC5',
            'hair': '#F72585',
            'top': '#B8F2E6',
            'bottom': '#3A0CA3',
            'shoe': '#FFFFFF',
            'hairStyle': 'bob',
            'detail': 'hoodie',
        },
    },
    {
        'id': 'nau_cafe',
        'ten': 'Nâu cà phê & cam đào (ấm áp)',
        'bg': ['#3E2723', '#FFCCBC'],
        'more': ['#6D4C41', '#FFF3E0'],
        'accent': '#FF7043',
        'fx': ['paper', 'sunburst'],
        'music': 'nhe',
        'char': {
            'skin': '#E8B48C',
            'hair': '#3E2723',
            'top': '#FF7043',
            'bottom': '#5D4037',
            'shoe': '#FFF3E0',
            'hairStyle': 'bun',
            'detail': 'apron',
        },
    },
    {
        'id': 'xanh_dien',
        'ten': 'Xanh điện & trắng (công nghệ)',
        'bg': ['#0033FF', '#F5F7FF'],
        'more': ['#0A1A4F', '#E0F7FF'],
        'accent': '#00E5A0',
        'fx': ['grid', 'glow'],
        'music': 'soi_dong',
        'char': {
            'skin': '#F5CFAF',
            'hair': '#0A0A23',
            'top': '#F5F7FF',
            'bottom': '#0033FF',
            'shoe': '#00E5A0',
            'hairStyle': 'spiky',
            'detail': 'tie',
        },
    },
    {
        'id': 'reu_hong',
        'ten': 'Xanh rêu & hồng phấn đậm',
        'bg': ['#2D3A1F', '#FF8FAB'],
        'more': ['#4F6B3A', '#FFE4EC'],
        'accent': '#FFF275',
        'fx': ['halftone', 'stripes'],
        'music': 'nhe',
        'char': {
            'skin': '#F3C6A5',
            'hair': '#6B3E26',
            'top': '#FF8FAB',
            'bottom': '#2D3A1F',
            'shoe': '#FFF275',
            'hairStyle': 'puff',
            'detail': 'none',
        },
    },
]

STORIES = [
    ('dem_nguoc', "TOP đếm ngược: đánh số từ ý ít quan trọng tới ý 'số 1' gây bất ngờ ở cuối"),
    ('tham_tu', "Thám tử điều tra: nhân vật đóng vai thám tử lần ra 'thủ phạm' từng cái một, kết luận vụ án ở cuối"),
    ('truoc_sau', "Trước / Sau: so sánh người làm sai và người làm đúng, hai số phận khác nhau"),
    ('do_vui', "Đố vui: mở bằng câu hỏi trắc nghiệm, khán giả đoán, cảnh sau lật đáp án kèm giải thích"),
    ('nhat_ky', "Nhật ký một ngày: kể theo mốc giờ trong ngày (7h, 10h, 15h...) của một nhân vật gặp chuyện"),
    ('phong_van', "Phỏng vấn đường phố: nhân vật cầm micro hỏi 'mọi người', mỗi cảnh một câu trả lời hài"),
    ('hieu_lam', "Sự thật ngược đời: mỗi cảnh phá một hiểu lầm phổ biến ('Nhiều người nghĩ... nhưng thật ra...')"),
    ('canh_bao', "Bản tin khẩn: giọng phát thanh viên tin nóng, cảnh báo đỏ, kết bằng lời khuyên cứu nguy"),
    ('cong_thuc', "Công thức nấu ăn: trình bày như dạy nấu món, mỗi 'nguyên liệu' là một ý chính"),
    ('hai_ban', "Hai người bạn tranh luận: A nói sai, B sửa lại, cãi qua cãi lại vui vẻ tới kết luận"),
    ('thu_thach', "Thử thách: nhân vật nhận một thử thách, từng cảnh vượt một chướng ngại, cái kết bất ngờ"),
    ('sai_lam', "3 sai lầm chết người: liệt kê các lỗi hay gặp, mỗi cảnh một lỗi + cách tránh"),
    ('bi_mat', "Bí mật ít ai biết: 'Ít ai biết rằng...' mỗi cảnh hé một bí mật thú vị về chủ đề"),
    ('hoi_dap', "Hỏi nhanh đáp gọn: mỗi cảnh một câu hỏi khán giả hay thắc mắc + câu trả lời ngắn gọn"),
    ('so_sanh', "Cái nào hơn: so sánh 2-3 lựa chọn theo từng tiêu chí, chốt cái đáng chọn nhất ở cuối"),
]

EXAMPLE_COLORS = {'#4ade80', '#3a2a52', '#22283a', '#ffd2b0', '#102a43', '#2f6bff'}
FX_ALL = ['sunburst', 'halftone', 'stripes', 'grid', 'glow', 'paper']
VARIETY = {'poster', 'hero', 'cast', 'quote', 'editorial', 'compare', 'steps', 'split', 'cards', 'talk', 'chart'}


def _lum(h: str) -> float:
    v = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    v = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def _fg(bg: str) -> str:
    return '#111111' if _lum(bg) > 0.35 else '#FFFFFF'


def pick(previous: list) -> dict:
    used_p = {x.get('pack', {}).get('id') for x in previous}
    used_s = {x.get('story', [None])[0] for x in previous}
    packs = [p for p in PACKS if p['id'] not in used_p] or PACKS
    stories = [s for s in STORIES if s[0] not in used_s] or STORIES
    p = random.choice(packs)
    s = random.choice(stories)
    return {'pack': p, 'story': s}


def prompt(pc: dict, avoid_colors=None) -> str:
    p = pc['pack']
    s = pc['story']
    c = p['char']
    av = ', '.join(sorted({x.lower() for x in (avoid_colors or []) if x})) if avoid_colors else ''
    res = (
        f"\nĐẠO DIỄN LẦN NÀY (để video KHÁC HẲN các video trước):\n"
        f"- Cách kể (BẮT BUỘC theo): {s[1]}. Concept và câu mở đầu bám cách kể này, sáng tạo, bất ngờ.\n"
        f"- MÀU: BẠN TỰ CHỌN bảng màu hợp chủ đề và cách kể (2 màu nền luân phiên + 1 màu nhấn tương phản mạnh, màu tươi đậm). Gợi ý nếu bí: '{p['ten']}' ({p['bg'][0]}/{p['bg'][1]}, nhấn {p['accent']}). "
    )
    if av:
        res += f"TRÁNH trùng các màu đã dùng gần đây: {av}.\n"
    else:
        res += "\n"
    res += (
        f"- NHÂN VẬT: BẠN TỰ CHỌN ngoại hình + đặt tên hợp chủ đề (tóc, áo, chi tiết nghề). Gợi ý: tóc {c['hairStyle']}, {c['detail']}.\n"
        f"- fx: chọn 2-3 kiểu hợp màu (gợi ý {', '.join(p['fx'])}); cảnh liền nhau nên khác fx. Nhạc: {p['music']}.\n"
    )
    return res


def _contrast(a: str, b: str) -> float:
    la = _lum(a)
    lb = _lum(b)
    hi = max(la, lb)
    lo = min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def apply(plan: dict, pc: dict) -> dict:
    p = pc['pack']
    pal = list(p['bg']) + list(p.get('more', []))
    acc = p['accent']
    order = [0, 1, 2, 3, 1, 0, 3, 2] if len(pal) >= 4 else [0, 1]
    fxs = list(p['fx']) + [x for x in FX_ALL if x not in p['fx']][:1]
    k = 0
    for sc in plan.get('scenes', []):
        if not isinstance(sc, dict):
            continue
        bg = pal[order[k % len(order)] % len(pal)]
        sc['bg'] = bg
        sc['fg'] = _fg(bg)
        chroma = lambda c: max(int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)) - min(int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        cands = [acc] + sorted([c for c in pal if c != bg], key=chroma, reverse=True)
        sc['accent'] = next((c for c in cands if _contrast(bg, c) >= 3.5), max(cands, key=lambda c: _contrast(bg, c)))
        others = [pal[order[(k + j) % len(order)] % len(pal)] for j in range(1, len(order) + 1)]
        sc['bg2'] = next((c for c in others if c != bg), others[0])
        prev_fx = plan['scenes'][k - 1].get('fx') if k else None
        sc['fx'] = next((f for f in fxs[k % len(fxs):] + fxs if f != prev_fx), fxs[0])
        k += 1

    vary(plan)

    ch = plan.get('character')
    if isinstance(ch, dict) and ch.get('on'):
        name = ch.get('name') or ''
        ch.update(p['char'])
        ch['name'] = name

    if plan.get('music') in (None, '', 'nhe', 'dien_anh', 'soi_dong'):
        plan['music'] = p['music']

    bgs = p['bg']
    plan['primary'] = acc if _lum(acc) < 0.6 else bgs[0]
    plan['dark'] = bgs[0] if _lum(bgs[0]) < 0.1 else '#111111'
    plan['style'] = p['id']
    plan['story'] = pc['story'][0]
    plan['styleName'] = f"{p['ten']} · {pc['story'][1].split(':')[0]}"
    return plan


def vary(plan: dict) -> dict:
    sc = [x for x in plan.get('scenes', []) if isinstance(x, dict)]
    if len(sc) < 3:
        return plan
    cap = max(2, int(len(sc) * 0.4 + 0.5))
    alt_lines = ['cards', 'steps']
    alt_one = ['poster', 'quote', 'talk']
    for i, x in enumerate(sc):
        prev = sc[i - 1].get('layout') if i else None
        lay = x.get('layout')
        used = sum(1 for y in sc[:i] if y.get('layout') == lay)
        if prev != lay and used < cap:
            continue
        lines = [t for t in str(x.get('body') or '').split('\n') if t.strip()]
        opts = (alt_lines + alt_one) if len(lines) >= 2 else alt_one
        nxt = sc[i + 1].get('layout') if i + 1 < len(sc) else None
        for o in opts:
            if o in (prev, nxt, lay):
                continue
            if o == 'talk' and not (plan.get('character') or {}).get('on'):
                continue
            if sum(1 for y in sc if y.get('layout') == o) >= cap:
                continue
            x['layout'] = o
            break
    return plan
