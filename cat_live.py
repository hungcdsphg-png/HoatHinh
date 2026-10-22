# -*- coding: utf-8 -*-
"""
Cắt livestream / video dài thành nhiều video ngắn đăng TikTok / Reels / Shorts.
1) Nghe lời nói (Whisper trên máy, hoặc nhờ GPU Colab cho nhanh)
2) AI chọn những đoạn hay nhất (giới thiệu sản phẩm, chốt giá, ưu đãi, phản hồi khách…)
3) ffmpeg cắt từng đoạn, đổi sang khung dọc 9:16, gắn phụ đề to dễ đọc
Kết quả: thư mục <chỗ lưu video>/cat-livestream/<tên video>/clip01…mp4 + noi-dung-dang.txt (tiêu đề, caption, hashtag)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

NOWIN = 0x08000000 if os.name == "nt" else 0
JOBS: dict[str, dict] = {}
LENS = {"ngan": (15, 35), "vua": (30, 60), "dai": (50, 90)}
HOT = ("giá", "giảm", "khuyến mãi", "ưu đãi", "tặng", "freeship", "miễn phí", "chốt", "đặt", "mua", "combo", "sale", "rẻ",
       "chính hãng", "bảo hành", "chất lượng", "đẹp", "thơm", "mềm", "bền", "chỉ còn", "hôm nay", "nhanh tay", "giỏ hàng", "link")

SYSTEM = """Bạn là biên tập viên video ngắn bán hàng (TikTok/Reels) người Việt. Đầu vào là lời thoại có mốc thời gian của một buổi livestream / video dài.
Hãy chọn ra những ĐOẠN HAY NHẤT để cắt thành video ngắn đăng mạng xã hội. Ưu tiên đoạn: giới thiệu công dụng/điểm mạnh sản phẩm rõ ràng, công bố giá & ưu đãi, chốt đơn hấp dẫn, trả lời câu hỏi khách hay, khoảnh khắc vui/cảm xúc, so sánh trước–sau.
Quy tắc:
- Mỗi đoạn phải TRỌN Ý: bắt đầu ở đầu câu, kết thúc ở cuối câu (dùng đúng mốc giây trong dữ liệu).
- Độ dài mỗi đoạn trong khoảng yêu cầu. Các đoạn không chồng lên nhau.
- Bỏ qua đoạn chào hỏi lan man, chờ người xem, đọc tên người xem, im lặng.
- tieu_de: ngắn ≤ 60 ký tự, gây tò mò. caption: 1–2 câu để đăng kèm. hashtag: 3–5 hashtag tiếng Việt không dấu.
Trả về DUY NHẤT JSON: {"clips":[{"start":giây,"end":giây,"tieu_de":"...","caption":"...","hashtag":"#... #...","ly_do":"vì sao hay"}]} sắp theo độ hay giảm dần."""


def _ctx():
    import hl_ext
    return hl_ext.CTX


def _log(m: str) -> None:
    try:
        _ctx()["log"]("[cat-live] " + m)
    except Exception:  # noqa: BLE001
        print(m)


def _ff() -> str:
    import hl_ext
    ff = hl_ext._ff()
    if not ff:
        raise RuntimeError("Cần ffmpeg (chạy CAI-FFMPEG.bat).")
    return ff


def pick_file() -> str:
    if os.name != "nt":
        return ""
    ps = ("Add-Type -AssemblyName System.Windows.Forms;$f=New-Object System.Windows.Forms.OpenFileDialog;"
          "$f.Title='Chọn video livestream / video dài cần cắt';"
          "$f.Filter='Video|*.mp4;*.mov;*.mkv;*.flv;*.webm;*.avi;*.m4v;*.ts|Tất cả|*.*';"
          "$w=New-Object System.Windows.Forms.Form;$w.TopMost=$true;"
          "if($f.ShowDialog($w) -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;Write-Output $f.FileName}")
    r = subprocess.run(["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, timeout=600, creationflags=NOWIN)
    return r.stdout.decode("utf-8", "ignore").strip()


# ---------------------------------------------------------------- nghe
def _listen_local(J, wav: Path, total: float) -> list[dict]:
    import hl_ext
    if not hl_ext.wh_installed():
        raise RuntimeError("Máy chưa có Whisper. Vào mục Caption/Phụ đề bấm cài Whisper, hoặc chọn 'Nhờ GPU Colab nghe'.")
    size = J.get("model") or hl_ext._cfg().get("whisper_model", "small")
    J["msg"] = f"Đang nạp Whisper ({size})…"
    model = hl_ext._wh_model(size)
    segs, _ = model.transcribe(str(wav), language="vi", word_timestamps=True, vad_filter=True, beam_size=1 if size in ("medium", "large-v3") else 5)
    out = []
    t0 = time.time()
    for s in segs:
        if J.get("cancel"):
            raise RuntimeError("Đã huỷ")
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                    "words": [{"s": round(w.start, 2), "e": round(w.end, 2), "w": w.word.strip()} for w in (s.words or [])]})
        if total:
            p = s.end / total
            J["pct"] = 5 + int(p * 55)
            eta = (time.time() - t0) / max(p, 1e-3) * (1 - p)
            J["msg"] = f"Đang nghe trên máy: {s.end / 60:.0f}/{total / 60:.0f} phút (còn ~{eta / 60:.0f} phút)"
    return out


def _listen_colab(J, src: Path) -> list[dict]:
    import colab_gpu
    r = colab_gpu._need_root()
    jid = time.strftime("%m%d-%H%M%S") + "-" + os.urandom(2).hex()
    mp3 = r / "viec" / f"{jid}_audio.mp3"
    J["msg"] = "Đang nén âm thanh để gửi Colab…"
    p = subprocess.run([_ff(), "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(mp3)],
                       capture_output=True, creationflags=NOWIN)
    if p.returncode or not mp3.exists():
        raise RuntimeError("Không tách được âm thanh: " + p.stderr.decode("utf-8", "ignore")[-200:])
    job = {"id": jid, "loai": "nghe", "audio": mp3.name, "ngon_ngu": "vi", "tao_luc": time.strftime("%Y-%m-%d %H:%M:%S"), "nguon": src.name}
    tmp = r / "viec" / (jid + ".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    tmp.replace(r / "viec" / (jid + ".json"))
    x = r / "xong" / jid
    t0 = time.time()
    while time.time() - t0 < 4 * 3600:
        if J.get("cancel"):
            raise RuntimeError("Đã huỷ")
        if (x / "loi.txt").exists():
            raise RuntimeError("Colab báo lỗi: " + (x / "loi.txt").read_text(encoding="utf-8", errors="ignore")[-300:])
        f = x / "loi-thoai.json"
        if (x / "xong.json").exists() and f.exists():
            return json.loads(f.read_text(encoding="utf-8"))["segments"]
        dang = (x / "dang.txt").read_text(encoding="utf-8", errors="ignore") if (x / "dang.txt").exists() else ""
        J["msg"] = ("Colab: " + dang.strip()) if dang else f"Đã gửi âm thanh lên Drive — mở Colab (⚡ GPU miễn phí) và bấm ▶ nếu chưa chạy… ({(time.time() - t0) / 60:.0f} phút)"
        time.sleep(5)
    raise RuntimeError("Chờ Colab quá lâu.")


# ---------------------------------------------------------------- chọn đoạn
def _lines(segs: list[dict], limit: int = 90000) -> str:
    rows = [f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segs if s.get("text")]
    txt = "\n".join(rows)
    if len(txt) <= limit:
        return txt
    # quá dài: gộp các câu thành khối ~20 giây
    out, cur, a = [], [], None
    for s in segs:
        if a is None:
            a = s["start"]
        cur.append(s["text"])
        if s["end"] - a >= 20:
            out.append(f"[{a:.1f}-{s['end']:.1f}] " + " ".join(cur))
            cur, a = [], None
    if cur:
        out.append(f"[{a:.1f}-{segs[-1]['end']:.1f}] " + " ".join(cur))
    return "\n".join(out)[:limit]


def _snap(segs, t: float, start: bool) -> float:
    if start:
        c = [s["start"] for s in segs if s["start"] <= t + 1.5]
        return max(c) if c else segs[0]["start"]
    c = [s["end"] for s in segs if s["end"] >= t - 1.5]
    return min(c) if c else segs[-1]["end"]


def _fix(segs, raw: list[dict], n: int, lo: int, hi: int, total: float, out: list[dict] | None = None) -> list[dict]:
    out = out if out is not None else []
    for c in raw:
        try:
            a, b = float(c["start"]), float(c["end"])
        except Exception:  # noqa: BLE001
            continue
        a, b = _snap(segs, a, True), _snap(segs, b, False)
        if b - a > hi:  # dài quá: cắt ở cuối câu gần mốc hi
            ends = [s["end"] for s in segs if a + lo <= s["end"] <= a + hi]
            b = max(ends) if ends else a + hi
        if b - a < lo:  # ngắn quá: nối thêm câu sau
            ends = [s["end"] for s in segs if s["end"] >= a + lo]
            b = min(ends) if ends and min(ends) - a <= hi + 10 else min(total, a + lo)
        a, b = max(0.0, a - 0.25), min(total or b + 0.4, b + 0.4)
        if any(not (b <= o["start"] or a >= o["end"]) for o in out):
            continue
        out.append({**c, "start": round(a, 2), "end": round(b, 2)})
        if len(out) >= n:
            break
    return out


def _fallback(segs, n: int, lo: int, hi: int) -> list[dict]:
    """Không có AI: chấm điểm theo từ khoá bán hàng, chọn các cửa sổ nhiều từ khoá nhất."""
    cands = []
    for i, s in enumerate(segs):
        a, j, txt = s["start"], i, []
        while j < len(segs) and segs[j]["end"] - a <= (lo + hi) / 2:
            txt.append(segs[j]["text"])
            j += 1
        t = " ".join(txt).lower()
        sc = sum(t.count(k) for k in HOT) + len(t) / 400
        cands.append({"start": a, "end": segs[max(i, j - 1)]["end"], "score": sc, "tieu_de": " ".join(txt)[:55], "caption": "", "hashtag": "#review #sanpham #muasam"})
    cands.sort(key=lambda c: -c["score"])
    return cands


def _choose(J, segs, n, lo, hi, total) -> list[dict]:
    J["msg"] = "AI đang xem lời thoại để chọn đoạn hay…"
    J["pct"] = 62
    user = (f"Video dài {total / 60:.0f} phút. Cần {n} đoạn, mỗi đoạn {lo}–{hi} giây.\n\nLỜI THOẠI:\n" + _lines(segs))
    raw = []
    try:
        import media_ai
        r = media_ai.gemini_vision(SYSTEM, user, [], _log)
        raw = r.get("clips") or []
        _log(f"AI chọn {len(raw)} đoạn")
    except Exception as e:  # noqa: BLE001
        _log(f"AI chưa chọn được ({e}) → chọn theo từ khoá bán hàng")
        J["note"] = "AI chưa trả lời được nên app tự chọn theo từ khoá bán hàng."
    clips = _fix(segs, raw, n, lo, hi, total)
    if len(clips) < n:  # AI chọn thiếu → bù bằng các đoạn nhiều từ khoá bán hàng
        _fix(segs, _fallback(segs, n, lo, hi), n, lo, hi, total, clips)
    return clips


# ---------------------------------------------------------------- phụ đề (ảnh PNG, không phụ thuộc libass/fontconfig)
def _font(size: int):
    from PIL import ImageFont  # type: ignore
    cands = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / n for n in ("arialbd.ttf", "segoeuib.ttf", "tahomabd.ttf", "arial.ttf")]
    cands += [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
    for c in cands:
        if c.exists():
            return ImageFont.truetype(str(c), size)
    return ImageFont.load_default()


def _sub_lines(segs, a: float, b: float) -> list[tuple[float, float, str]]:
    words = []
    for s in segs:
        if s["end"] < a or s["start"] > b:
            continue
        ws = s.get("words") or [{"s": s["start"], "e": s["end"], "w": s["text"]}]
        words += [w for w in ws if w["e"] > a and w["s"] < b and w["w"]]
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 7 or (cur[-1]["e"] - cur[0]["s"]) > 2.6 or re.search(r"[.!?,]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    res = []
    for g in out:
        s0, e0 = max(a, g[0]["s"]) - a, min(b, g[-1]["e"]) - a
        res.append((s0, max(s0 + 0.5, e0), " ".join(w["w"] for w in g).strip()))
    # nối khoảng trống ngắn để chữ không nháy
    for i in range(len(res) - 1):
        if res[i + 1][0] - res[i][1] < 0.6:
            res[i] = (res[i][0], res[i + 1][0], res[i][2])
    return res


def _sub_png(text: str, W: int, f: Path) -> tuple[int, int]:
    from PIL import Image, ImageDraw  # type: ignore
    size = max(30, W // 15)
    font = _font(size)
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d0.textlength(t, font=font) > W * 0.86 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    lines = lines[:2]
    lh = int(size * 1.25)
    im = Image.new("RGBA", (W, lh * len(lines) + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=font)
        d.text(((W - tw) / 2, 10 + i * lh), ln, font=font, fill=(255, 255, 255, 255), stroke_width=max(3, size // 9), stroke_fill=(0, 0, 0, 255))
    im.save(f)
    return im.size


# ---------------------------------------------------------------- cắt
def _cut(J, src: Path, c: dict, i: int, out: Path, segs, vw: int, vh: int, khung: str, sub: bool, tmp: Path) -> None:
    ff = _ff()
    a, b = c["start"], c["end"]
    dur = b - a
    if khung == "doc":
        W, H = 720, 1280
        if vw and vh and vw / vh > 0.62:  # video ngang/vuông → nền mờ + video giữa
            base = (f"[0:v]split[v1][v2];[v1]scale=180:320:force_original_aspect_ratio=increase,crop=180:320,boxblur=8:2,scale={W}:{H},setsar=1[bg];"
                    f"[v2]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[b0]")
        else:
            base = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[b0]"
    else:
        W = vw - vw % 2 if vw else 720
        H = vh - vh % 2 if vh else 1280
        base = f"[0:v]scale={W}:{H},setsar=1[b0]"
    inputs = ["-ss", f"{a:.2f}", "-t", f"{dur:.2f}", "-i", str(src)]
    chain, last = base, "b0"
    if sub:
        for k, (s0, e0, text) in enumerate(_sub_lines(segs, a, b)):
            f = tmp / f"s{i:02d}_{k:03d}.png"
            w_, h_ = _sub_png(text, W, f)
            inputs += ["-i", str(f)]
            y = int(H * (0.70 if khung == "doc" else 0.80))
            chain += f";[{last}][{k + 1}:v]overlay=0:{y}:enable='between(t,{s0:.2f},{e0:.2f})'[o{k}]"
            last = f"o{k}"
    cmd = [ff, "-y", "-loglevel", "error"] + inputs + ["-filter_complex", chain, "-map", f"[{last}]", "-map", "0:a:0?",
                                                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-r", "30",
                                                     "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    p = subprocess.run(cmd, capture_output=True, creationflags=NOWIN)
    if p.returncode or not out.exists():
        raise RuntimeError(f"cắt đoạn {i} lỗi: " + p.stderr.decode("utf-8", "ignore")[-300:])


def start(d: dict) -> dict:
    src = Path(str(d.get("path") or "").strip().strip('"'))
    if not src.is_file():
        raise ValueError("Không thấy file video. Bấm 'Chọn video' để chọn lại.")
    n = max(1, min(15, int(d.get("so") or 6)))
    lo, hi = LENS.get(d.get("do_dai"), LENS["vua"])
    jid = uuid.uuid4().hex[:10]
    J = JOBS[jid] = {"state": "running", "pct": 0, "msg": "Đang chuẩn bị…", "clips": [], "src": str(src), "note": "",
                     "model": d.get("model") or "", "id": jid}

    def run():
        tmp = Path(_ctx()["HOME"]) / "cat-live-tam" / jid
        try:
            import hl_ext
            import hl_pro
            ff = _ff()
            vw, vh, _fps, total, has_a = hl_ext._probe(ff, src)
            if not has_a:
                raise RuntimeError("Video không có tiếng nên không nghe được lời để chọn đoạn.")
            tmp.mkdir(parents=True, exist_ok=True)
            # 1) nghe
            cache = Path(_ctx()["HOME"]) / "cat-live-tam" / f"loi-thoai-{src.stat().st_size}-{int(src.stat().st_mtime)}.json"
            if cache.exists():
                segs = json.loads(cache.read_text(encoding="utf-8"))
                J["msg"] = "Đã có lời thoại từ lần trước"
            elif d.get("nghe") == "colab":
                segs = _listen_colab(J, src)
            else:
                wav = tmp / "am.wav"
                J["msg"] = "Đang tách âm thanh…"
                subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ar", "16000", "-ac", "1", str(wav)], capture_output=True, creationflags=NOWIN)
                segs = _listen_local(J, wav, total)
            segs = [s for s in segs if s.get("text")]
            if not segs:
                raise RuntimeError("Không nghe được lời nói nào trong video.")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
            # 2) chọn
            clips = _choose(J, segs, n, lo, hi, total)
            if not clips:
                raise RuntimeError("Không chọn được đoạn nào phù hợp.")
            clips.sort(key=lambda c: c["start"])
            # 3) cắt
            stem = re.sub(r'[\\/:*?"<>|]+', "", src.stem)[:60] or "video"
            outd = hl_pro.out_dir() / "cat-livestream" / f"{stem}-{time.strftime('%m%d-%H%M')}"
            outd.mkdir(parents=True, exist_ok=True)
            note = [f"Cắt từ: {src.name}\n"]
            for i, c in enumerate(clips, 1):
                if J.get("cancel"):
                    raise RuntimeError("Đã huỷ")
                J["msg"] = f"Đang cắt video {i}/{len(clips)} ({c['end'] - c['start']:.0f} giây)…"
                J["pct"] = 65 + int(34 * (i - 1) / len(clips))
                slug = re.sub(r"[^0-9A-Za-zÀ-ỹ ]+", "", str(c.get("tieu_de", "")))[:40].strip().replace(" ", "-") or "clip"
                out = outd / f"clip{i:02d}-{slug}.mp4"
                _cut(J, src, c, i, out, segs, vw, vh, d.get("khung", "doc"), d.get("phu_de", True) is not False, tmp)
                item = {"file": str(out), "name": out.name, "start": c["start"], "end": c["end"], "tieu_de": c.get("tieu_de", ""),
                        "caption": c.get("caption", ""), "hashtag": c.get("hashtag", "")}
                J["clips"].append(item)
                note.append(f"=== {out.name}  ({_ts(c['start'])} → {_ts(c['end'])})\nTiêu đề: {item['tieu_de']}\nCaption: {item['caption']}\nHashtag: {item['hashtag']}\n")
            (outd / "noi-dung-dang.txt").write_text("\n".join(note), encoding="utf-8")
            J.update(state="done", pct=100, msg=f"Xong {len(clips)} video ngắn", folder=str(outd))
            _log(f"{src.name} → {len(clips)} clip ở {outd}")
        except Exception as e:  # noqa: BLE001
            J.update(state="error", msg=str(e))
            _log("lỗi: " + str(e))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    threading.Thread(target=run, daemon=True).start()
    return {"job": jid}


def _ts(t: float) -> str:
    t = int(t)
    return f"{t // 3600:d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def job(jid: str) -> dict:
    J = JOBS.get(jid)
    return {k: v for k, v in J.items() if k != "model"} if J else {"state": "error", "msg": "Không thấy việc này"}


def cancel(jid: str) -> dict:
    if jid in JOBS:
        JOBS[jid]["cancel"] = True
    return {}
