"""HL Studio — giọng tự ghi âm (từng cảnh / một lèo rồi tự cắt) và tự dựng video có tiếng (cắt khoảng lặng, AI phụ đề + chọn đoạn hay)."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import media_ai

NOWIN = 0x08000000 if os.name == "nt" else 0
VOICE_FX = "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-1.5:LRA=9"


def _run(args, **kw):
    return subprocess.run(args, capture_output=True, creationflags=NOWIN, **kw)


def _dur(ff: str, f: Path) -> float:
    r = _run([ff, "-hide_banner", "-i", str(f)])
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr.decode("utf-8", "ignore"))
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _silences(ff: str, f: Path, noise_db: float = -35, min_d: float = 0.35) -> tuple[list[tuple[float, float]], float]:
    r = _run([ff, "-hide_banner", "-i", str(f), "-af", f"silencedetect=noise={noise_db}dB:d={min_d}", "-f", "null", "-"])
    err = r.stderr.decode("utf-8", "ignore")
    total = 0.0
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if m:
        total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    out, st = [], None
    for line in err.splitlines():
        a = re.search(r"silence_start: (-?[\d.]+)", line)
        b = re.search(r"silence_end: ([\d.]+)", line)
        if a:
            st = max(0.0, float(a.group(1)))
        elif b and st is not None:
            out.append((st, float(b.group(1))))
            st = None
    if st is not None:
        out.append((st, total))
    return out, total


def _speech(sil, total, pad=0.08):
    """Từ danh sách khoảng lặng -> danh sách đoạn có tiếng."""
    segs, t = [], 0.0
    for a, b in sil:
        if a - t > 0.05:
            segs.append((max(0.0, t - pad), min(total, a + pad)))
        t = b
    if total - t > 0.05:
        segs.append((max(0.0, t - pad), total))
    return segs


def _clean(ff: str, src: Path, out: Path, a: float | None = None, b: float | None = None):
    args = [ff, "-y", "-loglevel", "error"]
    if a is not None:
        args += ["-ss", f"{a:.3f}"]
    if b is not None:
        args += ["-to", f"{b:.3f}"] if a is None else ["-t", f"{b - a:.3f}"]
    args += ["-i", str(src), "-af", "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05," + "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.12,areverse," + VOICE_FX,
             "-ar", "48000", "-ac", "1", str(out)]
    r = _run(args)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError("Không xử lý được file âm thanh: " + r.stderr.decode("utf-8", "ignore")[-200:])


def _save_raw(data: bytes, name: str, media_dir: Path) -> Path:
    h = hashlib.sha1(data).hexdigest()[:16]
    ext = (Path(name).suffix or ".webm").lower()
    if not re.match(r"^\.[a-z0-9]{2,5}$", ext):
        ext = ".webm"
    p = media_dir / f"rec-{h}{ext}"
    if not p.exists():
        p.write_bytes(data)
    return p


def voice_upload(data: bytes, name: str, media_dir: Path, ff: str | None, log) -> dict:
    if len(data) < 200:
        raise RuntimeError("File ghi âm trống hoặc quá ngắn")
    raw = _save_raw(data, name, media_dir)
    if not ff:
        log(f"[giong-ghi] {raw.name} (chưa có ffmpeg, lưu tệp gốc)")
        return {"url": f"/media/{raw.name}", "dur": 5.0}
    out = raw.with_name(raw.stem + "-voice.wav")
    if not out.exists():
        _clean(ff, raw, out)
    d = _dur(ff, out)
    log(f"[giong-ghi] {out.name} {d:.1f}s")
    return {"url": f"/media/{out.name}", "dur": round(d, 2)}


def voice_split(data: bytes, name: str, n: int, media_dir: Path, ff: str | None, log) -> dict:
    """Một file đọc cả bài -> cắt thành n đoạn tại n-1 khoảng nghỉ dài nhất."""
    n = max(1, int(n))
    raw = _save_raw(data, name, media_dir)
    if not ff:
        return {"parts": [{"url": f"/media/{raw.name}", "dur": 5.0}], "total": 5.0, "warn": ""}
    media_ai.STATE["msg"] = "Đang tìm chỗ nghỉ giữa các câu…"
    sil, total = _silences(ff, raw, -38, 0.3)
    segs = _speech(sil, total)
    if not segs:
        raise RuntimeError("Không nghe thấy tiếng nói trong file")
    gaps = [(segs[i + 1][0] - segs[i][1], i) for i in range(len(segs) - 1)]
    cut_after = sorted(i for _, i in sorted(gaps, reverse=True)[: n - 1])
    parts, start = [], 0
    for i in cut_after:
        parts.append((segs[start][0], segs[i][1]))
        start = i + 1
    parts.append((segs[start][0], segs[-1][1]))
    out = []
    for k, (a, b) in enumerate(parts):
        media_ai.STATE["msg"] = f"Đang cắt đoạn {k + 1}/{len(parts)}…"
        f = raw.with_name(f"{raw.stem}-p{k + 1:02d}-{int(a * 1000)}.wav")
        if not f.exists():
            _clean(ff, raw, f, max(0.0, a - 0.05), b + 0.08)
        out.append({"url": f"/media/{f.name}", "dur": round(_dur(ff, f), 2), "from": round(a, 2), "to": round(b, 2)})
    media_ai.STATE["msg"] = ""
    warn = "" if len(out) == n else f"Chỉ tìm được {len(out)} đoạn cho {n} cảnh: anh đọc chậm lại, nghỉ lâu hơn giữa các cảnh nhé."
    return {"parts": out, "total": round(total, 2), "warn": warn}


# ---------------------------------------------------------------- video có tiếng
def _media_file(media_dir: Path, url_or_id: str) -> Path:
    name = Path(str(url_or_id)).name
    for c in (media_dir / name, media_dir / f"{name}-v.mp4"):
        if c.exists() and c.is_file():
            return c
    raise RuntimeError("Không tìm thấy video trong thư viện")


def video_cuts(d: dict, media_dir: Path, ff: str | None, log) -> dict:
    if not ff:
        raise RuntimeError("Cần ffmpeg")
    f = _media_file(media_dir, d.get("url") or d.get("id"))
    media_ai.STATE["msg"] = "Đang tìm khoảng lặng trong video…"
    sil, total = _silences(ff, f, float(d.get("noise", -33)), float(d.get("minSil", 0.45)))
    segs = _speech(sil, total, pad=0.12)
    merged = []
    for a, b in segs:  # gộp đoạn sát nhau, bỏ đoạn quá ngắn
        if merged and a - merged[-1][1] < 0.15:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    merged = [(round(a, 2), round(b, 2)) for a, b in merged if b - a >= 0.35]
    media_ai.STATE["msg"] = ""
    kept = sum(b - a for a, b in merged)
    return {"segments": [{"from": a, "to": b} for a, b in merged], "total": round(total, 2), "kept": round(kept, 2)}


AV_SYSTEM = "Bạn là biên tập viên video TikTok bán hàng. Nghe kỹ âm thanh tiếng Việt và trả về đúng JSON được yêu cầu, thời gian tính bằng giây (số thập phân) TÍNH TỪ ĐẦU ĐOẠN ÂM THANH ĐƯỢC GỬI."
CHUNK = 480.0  # nghe theo từng khúc 8 phút


def _gemini_audio(prompt: str, audio: bytes, log, llm_mod=None, model: str = "") -> dict:
    import requests  # type: ignore
    key = media_ai._gemini_key()
    if not key:
        raise RuntimeError("Cần API key Gemini để AI nghe tiếng (Video Bảng Trắng > Cài đặt). Vẫn dùng được nút “Cắt khoảng lặng” không cần AI.")
    models = []
    try:
        models = llm_mod.gemini_models(key) if llm_mod else []
    except Exception:  # noqa: BLE001
        pass
    models = models or ["gemini-2.5-flash", "gemini-2.0-flash"]
    if model:
        models = [model] + [m for m in models if m != model]
    parts = [{"text": prompt}, {"inline_data": {"mime_type": "audio/ogg", "data": base64.b64encode(audio).decode()}}]
    last = ""
    for m in models[:3]:
        body = {"systemInstruction": {"parts": [{"text": AV_SYSTEM}]}, "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 24576, "responseMimeType": "application/json"}}
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key}, json=body, timeout=300)
        except Exception as e:  # noqa: BLE001
            last = f"{m}: mất kết nối ({e.__class__.__name__})"
            continue
        if not r.ok:
            last = f"{m}: lỗi {r.status_code} {r.text[:160]}"
            continue
        try:
            txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"] if not p.get("thought"))
            mm = re.search(r"\{.*\}", txt, re.S)
            return json.loads(mm.group(0) if mm else txt)
        except Exception as e:  # noqa: BLE001
            last = f"{m}: trả lời không đọc được ({e})"
    if "429" in last and "quota" in last.lower():
        raise RuntimeError("AI chưa nghe được lời nói: API key Gemini hết lượt miễn phí hôm nay (phần nghe âm thanh chỉ chạy bằng API key).")
    if any(x in last for x in ("429", "503", "500", "502", "504")):
        raise RuntimeError("AI chưa nghe được lời nói: máy chủ Gemini đang quá tải, thử lại sau ít phút.")
    raise RuntimeError("AI không nghe được: " + last)


def _fake_chunk(off: float, dur: float, mode: str) -> dict:
    step = max(2.0, min(6.0, dur / 6))
    tr = [{"start": round(i * step, 2), "end": round(min(dur, i * step + step - .3), 2), "text": f"Câu nói thử {int((off + i * step) // 1)}s"} for i in range(max(1, int(dur // step)))]
    return {"transcript": tr, "keep": [{"start": x["start"], "end": x["end"], "why": "thử", "score": 9 - (i % 5)} for i, x in enumerate(tr[::2])],
            "clips": [{"start": 0.0, "end": min(dur, 30.0), "title": "Clip thử", "hook": "Xem ngay", "score": 8}], "title": "Video thử nghiệm", "hook": "Xem ngay điều bất ngờ", "product": {"name": "", "features": []}}


def _extract_audio(ff: str, f: Path) -> Path:
    aud = f.with_name(f.stem + "-a16.ogg")
    if not aud.exists():
        r = _run([ff, "-y", "-loglevel", "error", "-i", str(f), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "24k", str(aud)])
        if r.returncode != 0 or not aud.exists():
            raise RuntimeError("Video không có tiếng hoặc không đọc được tiếng")
    return aud


def video_ai(d: dict, media_dir: Path, ff: str | None, log, llm_mod=None) -> dict:
    """mode = 'highlight' (chọn đoạn hay cho 1 video) | 'clips' (cắt thành nhiều clip ngắn). Nghe theo khúc 8 phút."""
    if not ff:
        raise RuntimeError("Cần ffmpeg")
    f = _media_file(media_dir, d.get("url") or d.get("id"))
    total = _dur(ff, f)
    if total > 3 * 3600:
        raise RuntimeError("Video dài quá 3 tiếng, anh cắt bớt rồi đưa vào nhé")
    mode = d.get("mode", "highlight")
    media_ai.STATE["msg"] = "Đang tách tiếng từ video…"
    aud = _extract_audio(ff, f)
    n = max(1, int((total + CHUNK - 1) // CHUNK))
    trans, keeps, clips, meta = [], [], [], {}
    for k in range(n):
        off = k * CHUNK
        dur = min(CHUNK, total - off)
        if dur < 1:
            break
        media_ai.STATE["msg"] = f"AI đang nghe khúc {k + 1}/{n} ({int(off // 60)}–{int((off + dur) // 60) + 1} phút)…"
        part = aud.with_name(f"{aud.stem}-c{k:03d}.ogg")
        if not part.exists():
            _run([ff, "-y", "-loglevel", "error", "-ss", f"{off:.2f}", "-t", f"{dur:.2f}", "-i", str(aud), "-c", "copy", str(part)])
        prompt = f"""Đoạn âm thanh này là khúc {k + 1}/{n} của một video quay sản phẩm (dài {dur:.1f} giây). Thông tin thêm: {d.get('info', '')}
Trả JSON:
{{"transcript":[{{"start":0.0,"end":2.3,"text":"câu nói nguyên văn, mỗi đoạn 3-10 chữ"}}],
 "keep":[{{"start":0.0,"end":5.0,"why":"lý do ngắn","score":8}}],
 "clips":[{{"start":10.0,"end":45.0,"title":"tiêu đề clip 4-7 chữ","hook":"câu mở đầu gây tò mò 5-8 chữ","score":8}}],
 "title":"tiêu đề chung 4-7 chữ","hook":"câu mở đầu 5-8 chữ","product":{{"name":"tên sản phẩm nghe được","features":["điểm nổi bật nghe được"]}}}}
QUY TẮC: transcript phủ toàn bộ lời nói (câu ngắn để làm phụ đề). keep: các đoạn đáng giữ (trọn câu, bỏ ậm ừ, vấp, lặp, im lặng), score 1-10 theo độ hấp dẫn để bán hàng.
clips: {"2-4 đoạn tự đủ ý, mỗi đoạn 15-60 giây, làm được clip TikTok riêng" if mode == "clips" else "để []"}."""
        res = _fake_chunk(off, dur, mode) if os.environ.get("VSP_FAKE_AI") else _gemini_audio(prompt, part.read_bytes(), log, llm_mod, d.get("model", ""))
        for x in res.get("transcript") or []:
            try:
                trans.append({"t0": round(off + float(x["start"]), 2), "t1": round(off + float(x["end"]), 2), "text": str(x.get("text", "")).strip()})
            except Exception:  # noqa: BLE001
                pass
        for x in res.get("keep") or []:
            try:
                keeps.append({"from": off + float(x["start"]), "to": off + float(x["end"]), "why": str(x.get("why", "")), "score": float(x.get("score", 5))})
            except Exception:  # noqa: BLE001
                pass
        for x in res.get("clips") or []:
            try:
                clips.append({"from": off + float(x["start"]), "to": off + float(x["end"]), "title": str(x.get("title", "")), "hook": str(x.get("hook", "")), "score": float(x.get("score", 5))})
            except Exception:  # noqa: BLE001
                pass
        if not meta.get("title") and res.get("title"):
            meta = {"title": res.get("title", ""), "hook": res.get("hook", ""), "product": res.get("product") or {}}
    # khớp điểm cắt vào khoảng lặng thật cho mượt
    media_ai.STATE["msg"] = "Đang khớp điểm cắt…"
    sil, _ = _silences(ff, aud, -33, 0.2)

    def snap(t, side):
        best, bd = t, 0.6
        for a, b in sil:
            x = b - 0.08 if side == "start" else a + 0.1
            if abs(x - t) < bd:
                best, bd = x, abs(x - t)
        return round(min(total, max(0.0, best)), 2)
    for k in keeps + clips:
        k["from"], k["to"] = snap(k["from"], "start"), snap(k["to"], "end")
    keeps = [k for k in keeps if k["to"] - k["from"] >= 0.5]
    clips = [c for c in clips if c["to"] - c["from"] >= 8]
    # chọn đoạn theo độ dài mong muốn
    target = float(d.get("target") or 0)
    if target and keeps:
        chosen, acc = [], 0.0
        for k in sorted(keeps, key=lambda x: -x["score"]):
            if acc >= target:
                break
            chosen.append(k)
            acc += k["to"] - k["from"]
        keeps = chosen
    keeps.sort(key=lambda x: x["from"])
    # clip: chọn N clip điểm cao, không chồng nhau
    nclip = int(d.get("clips") or 5)
    picked = []
    for c in sorted(clips, key=lambda x: -x["score"]):
        if len(picked) >= nclip:
            break
        if all(c["to"] <= p["from"] or c["from"] >= p["to"] for p in picked):
            picked.append(c)
    picked.sort(key=lambda x: x["from"])
    media_ai.STATE["msg"] = ""
    return {"keep": keeps, "clips": picked, "transcript": trans, "title": meta.get("title", ""), "hook": meta.get("hook", ""), "product": meta.get("product", {}), "total": round(total, 2)}


# ---------------------------------------------------------------- phân tích video vừa đưa vào: nên làm gì?
def video_analyze(d: dict, media_dir: Path, ff: str | None, log, llm_mod=None) -> dict:
    if not ff:
        raise RuntimeError("Cần ffmpeg")
    f = _media_file(media_dir, d.get("url") or d.get("id"))
    total, w, h, has_audio = _dur(ff, f), int(d.get("w") or 0), int(d.get("h") or 0), bool(d.get("audio", True))
    speech = 0.0
    if has_audio:
        media_ai.STATE["msg"] = "Đang nghe thử video…"
        sil, _ = _silences(ff, f, -35, 0.4)
        quiet = sum(b - a for a, b in sil)
        speech = max(0.0, min(1.0, 1 - quiet / max(1.0, total)))
    media_ai.STATE["msg"] = "Đang xem các cảnh trong video…"
    r = _run([ff, "-hide_banner", "-i", str(f), "-vf", "select='gt(scene,0.32)',showinfo", "-an", "-f", "null", "-"])
    cuts = [float(m.group(1)) for m in re.finditer(r"pts_time:([\d.]+)", r.stderr.decode("utf-8", "ignore"))]
    landscape = w > h
    if has_audio and speech > 0.35:
        kind = "noi_dai" if total > 180 else "noi"
    elif total > 180:
        kind = "canh_dai"
    else:
        kind = "canh"
    desc = {"noi": "Video có người nói (giới thiệu / review).", "noi_dai": f"Video nói dài {int(total // 60)} phút — hợp cắt thành nhiều clip ngắn.",
            "canh": "Video quay cảnh / sản phẩm, ít lời nói.", "canh_dai": f"Video cảnh dài {int(total // 60)} phút, ít lời nói."}[kind]
    acts = []
    if kind == "noi":
        acts = [{"id": "highlight", "label": "✦ AI chọn đoạn hay + phụ đề (khoảng 30–45 giây)", "primary": True, "target": 40},
                {"id": "cuts", "label": "✂ Cắt khoảng lặng, giữ hết nội dung"}, {"id": "clips", "label": "🎬 Cắt thành vài clip ngắn", "clips": 3}]
    elif kind == "noi_dai":
        acts = [{"id": "clips", "label": "🎬 AI cắt thành 5 clip ngắn để đăng dần", "primary": True, "clips": 5},
                {"id": "highlight", "label": "✦ AI chọn đoạn hay nhất thành 1 video 60 giây", "target": 60}, {"id": "cuts", "label": "✂ Cắt khoảng lặng, giữ hết (xuất nhanh)"}]
    elif kind == "canh":
        acts = [{"id": "broll", "label": "✦ Làm video quảng cáo: video này làm nền + chữ + lồng tiếng AI", "primary": True},
                {"id": "scenes", "label": f"✂ Tách thành {max(1, len(cuts) + 1)} đoạn theo cảnh quay để dùng xen kẽ"}]
    else:
        acts = [{"id": "scenes", "label": f"✂ Tách {max(1, len(cuts) + 1)} cảnh quay, AI chọn cảnh đẹp làm video 30 giây", "primary": True, "target": 30},
                {"id": "broll", "label": "✦ Làm video quảng cáo có lồng tiếng AI trên nền video này"}]
    if landscape:
        desc += " Video quay ngang: app tự đặt vào khung dọc 9:16 (nền mờ phía sau)."
    media_ai.STATE["msg"] = ""
    return {"kind": kind, "desc": desc, "speech": round(speech, 2), "cuts": [round(c, 2) for c in cuts], "total": round(total, 2), "actions": acts}


# ---------------------------------------------------------------- xuất nhanh (video dài): cắt ghép thẳng bằng ffmpeg + phụ đề
def _ass_time(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _ass_text(s: str) -> str:
    return s.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def fast_export(d: dict, media_dir: Path, out_path: Path, ff: str | None, log) -> dict:
    if not ff:
        raise RuntimeError("Cần ffmpeg")
    items = d.get("items") or []
    if not items:
        raise RuntimeError("Không có đoạn video nào để xuất")
    W_, H_ = 1080, 1920
    acc = (d.get("accent") or "#22C3D6").lstrip("#")
    acc_ass = f"&H00{acc[4:6]}{acc[2:4]}{acc[0:2]}&" if len(acc) == 6 else "&H00D6C322&"
    ass = out_path.with_suffix(".ass")
    ev = []
    sstyle = d.get("subStyle") or "karaoke"
    for sb in d.get("subs") or []:
        t0, t1, txt = float(sb["t0"]), float(sb["t1"]), str(sb["text"])
        words = txt.split()
        if sstyle == "khoi" or not words:
            ev.append(f"Dialogue: 0,{_ass_time(t0)},{_ass_time(t1)},Sub,,0,0,0,,{_ass_text(txt)}")
            continue
        wt = [len(re.sub(r"\W", "", w)) + 2 + (3 if re.search(r"[,;:]$", w) else 5 if re.search(r"[.!?…]$", w) else 0) for w in words]
        tot = sum(wt) or 1
        if sstyle == "mot_chu":  # 1-2 chữ to giữa màn hình, nối tiếp nhau
            acc = 0.0
            for i in range(0, len(words), 2):
                seg = words[i:i + 2]
                a = t0 + acc / tot * (t1 - t0)
                acc += sum(wt[i:i + 2])
                b = t0 + acc / tot * (t1 - t0)
                ev.append(f"Dialogue: 0,{_ass_time(a)},{_ass_time(b)},Big,,0,0,0,,{{\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)}}{_ass_text(' '.join(seg).upper())}")
            continue
        parts = []
        for w, x in zip(words, wt):
            cs = max(1, round(x / tot * (t1 - t0) * 100))
            parts.append(f"{{\\kf{cs}}}{_ass_text(w)} ")
        ev.append(f"Dialogue: 0,{_ass_time(t0)},{_ass_time(t1)},Kara,,0,0,0,,{''.join(parts).strip()}")
    if d.get("hook"):
        ev.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(min(3.5, float(d.get('dur') or 3.5)))},Hook,,0,0,0,,{{\\fad(150,250)}}{_ass_text(str(d['hook']).upper())}")
    if d.get("title"):
        ev.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(99999)},Title,,0,0,0,,{_ass_text(str(d['title']))}")
    ass.write_text("\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W_}", f"PlayResY: {H_}", "WrapStyle: 0", "",
        "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Sub,Arial,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,2,90,170,470,1",
        "Style: Kara,Arial,64,&H003BD4FF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,2,90,170,470,1",
        f"Style: Big,Arial,118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,9,3,5,80,80,0,1",
        f"Style: Hook,Arial,86,&H00FFFFFF,&H00FFFFFF,{acc_ass},&H00000000,-1,0,0,0,100,100,0,0,3,18,0,8,80,160,260,1",
        "Style: Title,Arial,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,8,80,160,150,1", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text", *ev]), encoding="utf-8")
    inputs, fc, n = [], [], 0
    for it in items:
        f = _media_file(media_dir, it["url"])
        a, b = float(it.get("from", 0)), float(it.get("to", 0))
        inputs += ["-ss", f"{a:.3f}", "-t", f"{max(0.2, b - a):.3f}", "-i", str(f)]
        z = 1.08 if it.get("punch") else 1.0
        fc.append(f"[{n}:v]split[b{n}][f{n}];[b{n}]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=8:2,scale={W_}:{H_},eq=brightness=-0.12[bb{n}];"
                  f"[f{n}]scale={int(W_ * z)}:{int(H_ * z)}:force_original_aspect_ratio=decrease[ff{n}];[bb{n}][ff{n}]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,format=yuv420p[v{n}];"
                  f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo[a{n}]")
        n += 1
    cat = "".join(f"[v{i}][a{i}]" for i in range(n))
    assp = str(ass).replace("\\", "/").replace(":", "\\:")
    fc.append(f"{cat}concat=n={n}:v=1:a=1[vc][ac];[vc]subtitles='{assp}'[vo];[ac]loudnorm=I=-14:TP=-1.5:LRA=11[ao]")
    media_ai.STATE["msg"] = "Đang xuất nhanh bằng ffmpeg…"
    args = [ff, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out_path)]
    r = _run(args)
    media_ai.STATE["msg"] = ""
    if r.returncode != 0 or not out_path.exists():
        raise RuntimeError("Xuất nhanh lỗi: " + r.stderr.decode("utf-8", "ignore")[-300:])
    try:
        ass.unlink()
    except Exception:  # noqa: BLE001
        pass
    return {"path": str(out_path), "dur": round(_dur(ff, out_path), 2)}
