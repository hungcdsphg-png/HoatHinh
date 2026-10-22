# -*- coding: utf-8 -*-
"""HL Studio — AI XEM HÌNH các video rồi tự lên kịch bản dựng.

App chụp nhiều khung hình rải đều mỗi video, ghép thành "bảng xem nhanh" có đánh số (V3 · 12.4s),
gửi AI (Gemini API / Antigravity / Codex… theo Nguồn AI đã chọn) để AI XEM nội dung thật:
chọn cảnh đẹp, bỏ cảnh mờ/rung/trùng, sắp thứ tự kể chuyện, đặt chữ trên màn hình, chọn nhạc.
"""
from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import media_ai

NOWIN = media_ai.NOWIN

SYSTEM = """Bạn là ĐẠO DIỄN DỰNG PHIM chuyên nghiệp cho video ngắn (TikTok / Reels / Shorts), người Việt. Bạn TỰ QUYẾT TOÀN BỘ:
độ dài, cấu trúc, thứ tự, cách cắt, chuyển động máy, tốc độ, chữ, màu phim, nhạc — không theo một mẫu cố định nào; mỗi bộ video một cách dựng hợp nội dung.
Bạn được xem các "bảng xem nhanh": mỗi ô là một khung hình có nhãn "V<số video> · <giây>s". Hãy XEM KỸ để hiểu video quay gì.
Nếu có ẢNH CHỤP (ô nhãn "A<số ảnh>"), hãy XEN ảnh vào giữa các clip video như một cú máy: ảnh đẹp/khoảnh khắc đặc biệt, ảnh nhóm, ảnh phong cảnh,
ảnh chi tiết sản phẩm. Ảnh nên đứng 1,5–3s, luôn có "may" (day_vao/keo_ra/lia_ngang/lia_doc) để ảnh không bị chết; có thể ghép 2–4 ảnh liên tiếp
thành chuỗi dồn nhịp 0,6–1s/ảnh. Dùng phần lớn ảnh đẹp, bỏ ảnh mờ/trùng. Ảnh trùng nội dung video thì đặt cạnh clip đó cho liền mạch.

BỘ THỦ PHÁP (chọn cho từng clip, theo ngôn ngữ dựng phim chuyên nghiệp):
- chuyen (cách vào clip): "cat" cắt thẳng trên phách nhạc (MẶC ĐỊNH, chiếm đa số) · "flash" chớp trắng (chỉ cho khoảnh khắc đỉnh) ·
  "den" qua màn đen (đổi thời gian / kết) · "mo" hoà tan (cảm xúc, chậm) · "luot" lia nhòe nhanh (năng động) · "zoom" phóng xuyên ·
  "iris" khép mở tròn · "day_len" đẩy lên (sang chương mới) · "khoi_mau" khối màu quét (sang chương mới) · "lap_phuong" khối 3D (hiếm).
- may (chuyển động máy trên clip): "" đứng yên · "day_vao" đẩy vào chậm · "keo_ra" kéo ra · "lia_ngang" · "lia_doc" ·
  "giat_vao" giật zoom nhấn mạnh · "nhay_cat" nhảy cắt 3 nấc (jump-cut punch-in) · "rung" rung tay máy (sống động).
- toc_do: 1 bình thường · 0.5 quay chậm (khoảnh khắc đẹp: nước bắn, cười, bay) · 1.5–2 tua nhanh (di chuyển, chuẩn bị).
- ramp: true = đổi tốc điện ảnh nhanh→chậm 0,5x→nhanh (cho 1–2 khoảnh khắc đỉnh, chỉ video quay_cham_duoc). dung_hinh: số giây dừng hình cuối clip kèm chớp (chỉ 0–1 lần, thường cảnh kết hoặc đỉnh).
- chu + kieu_chu: "giua" câu móc giữa màn hình (mở đầu) · "chuong" thẻ chương góc dưới (đầu mỗi phần) · "go" gõ từng chữ (lời kể) · "lon" chữ lớn dưới.
- giu_tieng: true khi tiếng gốc có giá trị (người nói vào máy, tiếng nước, tiếng cười); không dùng chung với ramp/toc_do≠1.

LUẬT ĐẠO DIỄN (bắt buộc):
1. Mở đầu = MÓC (trailer bumper): 2–4 clip RẤT ngắn (0,6–1,2s) là những khoảnh khắc ĐỈNH nhất của cả bộ, cắt dồn dập, rồi câu móc chữ "giua".
2. Sau đó kể theo các CHƯƠNG (2–5 chương theo nội dung thật, ví dụ: Lên đường → Đạp xe → Vượt suối → Trekking → Về đích); đầu mỗi chương có chữ "chuong" và chuyển "day_len"/"khoi_mau"/"den".
3. Trong chương: cắt thẳng "cat" theo phách; nhịp thay đổi (2–3,5s cảnh rộng, 1–2s cảnh hành động); xen cảnh rộng – trung – cận.
4. Hiệu ứng toàn khung (flash, giat_vao, ramp, dung_hinh) cộng lại TỐI ĐA 4 lần cả video — dành cho đúng khoảnh khắc mạnh nhất.
5. Thông tin quan trọng (chữ) phải đứng yên ≥1 giây; chữ ngắn ≤7 từ, đúng cái THẤY trong hình, không bịa tên/địa danh không thấy rõ.
6. Kết: cảnh đẹp nhất/cảm xúc nhất, chậm lại (toc_do 0.5 hoặc dung_hinh), câu kết chữ "lon", chuyển "den" hoặc "mo".
7. Bỏ khung mờ, rung lắc hỏng, tối, che ống kính, trùng lặp. Độ dài tổng tự quyết hợp nội dung (thường 30–60s; nhiều tư liệu hay thì tới 90s) — nếu dữ liệu có target>0 thì bám target.
8. Chọn mau (màu phim) hợp không khí: "am" ấm (du lịch, nắng) · "lanh" lạnh (công nghệ, biển) · "dien_anh" điện ảnh (viền đen, trầm) · "tuoi" tươi rực (vui, trẻ) · "tu_nhien" · "den_trang".
9. brandOn=false thì TUYỆT ĐỐI không nhắc thương hiệu, hotline, mua hàng.
10. ĐỘ MƯỢT (quan trọng nhất): mỗi video có "chuyen_dong" = chuỗi số 0–9, mỗi số là mức chuyển động của 0,5 giây (0 đứng yên, 9 rất mạnh).
   Đặt điểm vào/ra clip ở chỗ chuyển động LẮNG (số nhỏ) hoặc ngay khi một động tác VỪA XONG; không cắt giữa cú lia/động tác đang mạnh.
   Hai clip liền nhau nên cùng hướng/nhịp chuyển động. Clip đã có chuyển động mạnh (số ≥6) thì "may" để "" (không chồng thêm chuyển động máy).
11. Quay chậm (toc_do 0.5, ramp) CHỈ dùng khi video có "quay_cham_duoc": true (quay ≥50 hình/giây); video thường thì toc_do 1 hoặc tua nhanh.
12. Chuyển cảnh: cả video chỉ dùng TỐI ĐA 2 kiểu ngoài "cat"/"den" (ví dụ "day_len" cho chương + "mo" cho cảm xúc), lặp lại nhất quán; còn lại cắt thẳng.

Chỉ trả JSON đúng mẫu:
{"tieu_de":"tên video","noi_dung":"1 câu: video quay gì","y_tuong":"1 câu: ý tưởng dựng","cam_xuc":"...","nhac":"soi_dong|nhe|dien_anh","mau":"am|lanh|dien_anh|tuoi|tu_nhien|den_trang",
 "clips":[{"v":1,"t":12.4,"dai":2.5,"chuyen":"cat","may":"day_vao","toc_do":1,"ramp":false,"dung_hinh":0,"chu":"","kieu_chu":"","phu":"","giu_tieng":false,"ly_do":"..."},
          {"anh":2,"dai":2.0,"chuyen":"cat","may":"keo_ra","dung_hinh":0,"chu":"","kieu_chu":"","phu":"","ly_do":"clip ảnh: dùng khóa anh thay cho v và t"}],
 "bo":[{"v":5,"ly_do":"..."}]}"""


def _frame(ffmpeg: str, f: Path, t: float, w: int) -> bytes:
    r = subprocess.run([ffmpeg, "-v", "error", "-ss", f"{max(0, t):.2f}", "-i", str(f), "-frames:v", "1", "-vf", f"scale={w}:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
                       capture_output=True, timeout=30, creationflags=NOWIN)
    return r.stdout


def contact_sheets(vids: list[dict], media_dir: Path, ffmpeg: str, per: int, max_sheets: int = 8, imgs: list | None = None):
    """Trả về (danh sách ảnh JPEG, bảng tra nhãn). Mỗi hàng = 1 video, mỗi ô = 1 khung hình có nhãn."""
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    try:
        font = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:  # noqa: BLE001
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
        except Exception:  # noqa: BLE001
            font = ImageFont.load_default()
    rows, labels = [], {}
    for i, v in enumerate(vids, 1):
        f = media_dir / Path(str(v.get("url", ""))).name
        if not f.exists():
            continue
        dur = float(v.get("dur") or 0) or 5.0
        n = max(3, min(per, int(dur // 1.2) or 3))
        cells = []
        for k in range(n):
            t = round(dur * (k + .5) / n, 1)
            b = _frame(ffmpeg, f, t, 220)
            if not b:
                continue
            im = Image.open(io.BytesIO(b)).convert("RGB")
            im.thumbnail((220, 300))
            d = ImageDraw.Draw(im)
            tag = f"V{i} · {t}s"
            d.rectangle((0, 0, 10 + 13 * len(tag), 30), fill=(0, 0, 0))
            d.text((5, 3), tag, fill=(255, 230, 0), font=font)
            cells.append(im)
            labels.setdefault(i, []).append(t)
        if cells:
            rows.append(cells)
    # ảnh chụp: mỗi hàng 6 ảnh, nhãn A1, A2…
    icells = []
    for j, a in enumerate(imgs or [], 1):
        f = media_dir / Path(str(a.get("url", ""))).name
        try:
            im = Image.open(f).convert("RGB")
        except Exception:  # noqa: BLE001
            continue
        im.thumbnail((220, 300))
        d = ImageDraw.Draw(im)
        tag = f"A{j}"
        d.rectangle((0, 0, 14 + 15 * len(tag), 30), fill=(160, 0, 90))
        d.text((5, 3), tag, fill=(255, 255, 255), font=font)
        icells.append(im)
        labels.setdefault("anh", []).append(j)
    for k in range(0, len(icells), 6):
        rows.append(icells[k:k + 6])
    if not rows:
        raise RuntimeError("Không chụp được khung hình nào từ video")
    # xếp hàng vào các bảng, mỗi bảng tối đa ~1100px cao
    sheets, cur, h = [], [], 0
    for r in rows:
        rh = max(c.height for c in r) + 6
        if cur and h + rh > 1150:
            sheets.append(cur)
            cur, h = [], 0
        cur.append(r)
        h += rh
    if cur:
        sheets.append(cur)
    if len(sheets) > max_sheets:  # quá nhiều video: gộp bớt (mỗi video ít khung hơn)
        return contact_sheets(vids, media_dir, ffmpeg, max(3, per - 2), max_sheets, imgs) if per > 3 else (_render(sheets[:max_sheets]), labels)
    return _render(sheets), labels


def _render(sheets):
    from PIL import Image  # type: ignore
    out = []
    for rows in sheets:
        W = max(sum(c.width + 6 for c in r) for r in rows)
        H = sum(max(c.height for c in r) + 6 for r in rows)
        sh = Image.new("RGB", (W, H), (24, 24, 28))
        y = 0
        for r in rows:
            x = 0
            for c in r:
                sh.paste(c, (x, y))
                x += c.width + 6
            y += max(c.height for c in r) + 6
        buf = io.BytesIO()
        sh.save(buf, "JPEG", quality=85)
        out.append(buf.getvalue())
    return out


def _lv(x: float) -> int:
    import math
    return max(0, min(9, int(round((math.log10(max(x, 1e-4)) + 3.3) * 3))))


def _digits(mo: list) -> str:
    """mức chuyển động mỗi 0,5 giây → chuỗi số 0–9 cho AI đọc"""
    return "".join(str(_lv(max(mo[i:i + 2]))) for i in range(0, len(mo), 2))[:240]


def _level(mo: list, a: float, b: float) -> float:
    seg = mo[int(a / .25):max(int(a / .25) + 1, int(b / .25))]
    return sum(_lv(x) for x in seg) / len(seg) if seg else 0


def _snap(mo: list, a: float, b: float, dur: float):
    """dời điểm vào ±0,3s và điểm ra ±0,4s về chỗ chuyển động nhỏ nhất (cắt lúc động tác vừa dứt), giữ độ dài gần như cũ"""
    if not mo:
        return a, b
    def best(t, r):
        lo, hi = max(0, int((t - r) / .25)), min(len(mo) - 1, int((t + r) / .25))
        if hi < lo:
            return t
        k = min(range(lo, hi + 1), key=lambda i: (mo[i], abs(i * .25 + .125 - t)))
        return k * .25 + .125 if mo[k] < mo[min(len(mo) - 1, max(0, int(t / .25)))] * .7 else t
    na, nb = best(a, .3), best(b, .4)
    if dur:
        na, nb = max(0.0, na), min(dur, nb)
    return (na, nb) if nb - na >= max(.5, (b - a) * .7) else (a, b)


def _limit_trans(clips: list) -> None:
    """chuyển cảnh nhất quán: ngoài cắt thẳng / màn đen / chớp chỉ giữ 2 kiểu dùng nhiều nhất"""
    soft = [c["chuyen"] for c in clips if c.get("chuyen") not in ("cat", "den", "flash")]
    keep = [k for k, _ in sorted(((k, soft.count(k)) for k in set(soft) if k != "lap_phuong"), key=lambda x: -x[1])[:2]] or ["day_len"]
    for c in clips:
        if c.get("chuyen") not in ("cat", "den", "flash") and c["chuyen"] not in keep:
            c["chuyen"] = keep[0]


def plan(d: dict, media_dir: Path, ffmpeg: str | None, log) -> dict:
    if not ffmpeg:
        raise RuntimeError("Cần ffmpeg để AI xem video")
    vids = [v for v in (d.get("videos") or []) if isinstance(v, dict)][:30]
    imgs = [a for a in (d.get("images") or []) if isinstance(a, dict)][:24]
    if not vids:
        raise RuntimeError("Chưa có video nào")
    media_ai.STATE["msg"] = f"AI đang xem {len(vids)} video" + (f" + {len(imgs)} ảnh…" if imgs else "…")
    per = 8 if len(vids) <= 4 else 6 if len(vids) <= 10 else 4
    sheets, labels = contact_sheets(vids, media_dir, ffmpeg, per, imgs=imgs)
    nimg = len(labels.pop("anh", []))
    import dung_muot
    motions, fpss = [], []
    for v in vids:
        f = media_dir / Path(str(v.get("proxy") or v.get("url", ""))).name
        try:
            mo = dung_muot.motion(ffmpeg, f) if f.exists() else []
        except Exception:  # noqa: BLE001
            mo = []
        motions.append(mo)
        fpss.append(float(v.get("fps") or 30))
    info = {"target": int(d.get("target") or 0), "brandOn": bool(d.get("brandOn")), "brand": d.get("brand") if d.get("brandOn") else None,
            "san_pham": d.get("product") or None, "ghi_chu": str(d.get("note") or "")[:500],
            "videos": [{"v": i, "ten": str(v.get("label") or "")[:60], "dai_giay": round(float(v.get("dur") or 0), 1), "loi_noi": v.get("speech"),
                        "khung_da_xem": labels.get(i, []), "chuyen_dong": _digits(motions[i - 1]), "quay_cham_duoc": fpss[i - 1] >= 48}
                       for i, v in enumerate(vids, 1)],
            "anh": [{"anh": j, "ten": str(a.get("label") or "")[:60]} for j, a in enumerate(imgs[:nimg], 1)]}
    log(f"[xem-video] AI xem {len(vids)} video + {nimg} ảnh qua {len(sheets)} bảng hình")
    try:
        if __import__("os").environ.get("VSP_FAKE_AI") and not __import__("os").environ.get("VSP_TEST_CLI"):
            res = {"tieu_de": "Chuyến đi", "noi_dung": "Video thử", "nhac": "soi_dong", "nhan_xet": "Dựng thử",
                   "mau": "am", "y_tuong": "móc dồn dập rồi kể theo chương",
                   "clips": [{"v": i, "t": ts[len(ts) // 2], "dai": 1.0 if i == 1 else 2.5, "chu": "Bắt đầu thôi" if i == 1 else ("Chặng 2" if i == 2 else ""), "kieu_chu": "giua" if i == 1 else "chuong",
                              "chuyen": "cat" if i == 1 else "day_len", "may": "giat_vao" if i == 1 else "day_vao", "toc_do": 1, "ramp": i == 2, "dung_hinh": 0.8 if i == len(labels) else 0} for i, ts in labels.items()]}
            for j in range(1, nimg + 1):
                res["clips"].insert(min(len(res["clips"]), j * 2 - 1), {"anh": j, "dai": 2.0, "chuyen": "cat", "may": ["day_vao", "keo_ra", "lia_ngang"][j % 3], "chu": "Ảnh " + str(j) if j == 1 else "", "kieu_chu": "go"})
        else:
            res = media_ai.gemini_vision(SYSTEM, "DỮ LIỆU:\n" + json.dumps(info, ensure_ascii=False), sheets, log)
    finally:
        media_ai.STATE["msg"] = ""
    if not isinstance(res, dict) or not isinstance(res.get("clips"), list):
        raise RuntimeError("AI chưa trả về kịch bản dựng hợp lệ")
    clips = []
    for c in res["clips"][:80]:
        try:
            if c.get("anh") not in (None, "", 0) and c.get("v") in (None, "", 0):
                j = int(str(c.get("anh")).lstrip("Aa"))
                if not 1 <= j <= nimg:
                    continue
                clips.append({"img": j - 1, "dai": round(max(0.5, min(5.0, float(c.get("dai") or 2))), 2), "chu": str(c.get("chu") or "")[:60], "phu": str(c.get("phu") or "")[:40],
                              "kieu_chu": c.get("kieu_chu") if c.get("kieu_chu") in ("giua", "chuong", "go", "lon") else ("lon" if c.get("chu") else ""),
                              "chuyen": c.get("chuyen") if c.get("chuyen") in ("cat", "flash", "den", "mo", "luot", "zoom", "iris", "day_len", "khoi_mau", "lap_phuong") else "cat",
                              "may": c.get("may") if c.get("may") in ("day_vao", "keo_ra", "lia_ngang", "lia_doc", "giat_vao", "rung") else "day_vao",
                              "dung_hinh": max(0.0, min(1.5, float(c.get("dung_hinh") or 0))), "ly_do": str(c.get("ly_do") or "")[:120]})
                continue
            v = int(str(c.get("v")).lstrip("Vv"))
            if not 1 <= v <= len(vids):
                continue
            dur = float(vids[v - 1].get("dur") or 0)
            t = max(0.0, min(float(c.get("t") or 0), max(0.0, dur - .3)))
            dai = max(0.6, min(8.0, float(c.get("dai") or 2.5)))
            sp = float(c.get("toc_do") or 1)
            sp = min([0.5, 1.0, 1.5, 2.0], key=lambda x: abs(x - sp))
            slow_ok = fpss[v - 1] >= 48
            ramp = bool(c.get("ramp")) and slow_ok
            if sp < 1 and not slow_ok:
                sp = 1.0  # video 30 hình/giây: quay chậm sẽ lặp hình, giật → giữ tốc độ thường
            src = dai if ramp else dai * sp  # đoạn gốc cần lấy để ra đúng "dai" giây sau đổi tốc
            a = max(0.0, t - src * .4)
            b = min(dur, a + src) if dur else a + src
            mo = motions[v - 1]
            a, b = _snap(mo, a, b, dur)  # cắt ở chỗ chuyển động lắng / động tác vừa xong
            if b - a < .4:
                continue
            may = c.get("may") if c.get("may") in ("", "day_vao", "keo_ra", "lia_ngang", "lia_doc", "giat_vao", "nhay_cat", "rung") else ""
            if may in ("day_vao", "keo_ra", "lia_ngang", "lia_doc", "rung") and _level(mo, a, b) >= 6:
                may = ""  # clip đã lia/chạy mạnh: không chồng thêm chuyển động máy
            clips.append({"v": v - 1, "from": round(a, 2), "to": round(b, 2), "chu": str(c.get("chu") or "")[:60], "phu": str(c.get("phu") or "")[:40],
                          "kieu_chu": c.get("kieu_chu") if c.get("kieu_chu") in ("giua", "chuong", "go", "lon") else ("lon" if c.get("chu") else ""),
                          "chuyen": c.get("chuyen") if c.get("chuyen") in ("cat", "flash", "den", "mo", "luot", "zoom", "iris", "day_len", "khoi_mau", "lap_phuong") else "cat",
                          "may": may, "toc_do": sp, "ramp": ramp, "dung_hinh": max(0.0, min(1.5, float(c.get("dung_hinh") or 0))),
                          "giu_tieng": bool(c.get("giu_tieng")), "ly_do": str(c.get("ly_do") or "")[:120]})
        except Exception:  # noqa: BLE001
            continue
    if not any("v" in c for c in clips):
        raise RuntimeError("AI chưa chọn được cảnh nào")
    _limit_trans(clips)
    return {"title": str(res.get("tieu_de") or "")[:80], "summary": str(res.get("noi_dung") or "")[:200], "mood": res.get("cam_xuc"),
            "music": res.get("nhac") if res.get("nhac") in ("soi_dong", "nhe", "dien_anh") else "soi_dong",
            "grade": res.get("mau") if res.get("mau") in ("am", "lanh", "dien_anh", "tuoi", "tu_nhien", "den_trang") else "tu_nhien",
            "clips": clips, "drop": [x for x in (res.get("bo") or []) if isinstance(x, dict)][:30], "note": str(res.get("y_tuong") or res.get("nhan_xet") or "")[:300]}
