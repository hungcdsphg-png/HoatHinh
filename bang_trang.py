# -*- coding: utf-8 -*-
"""HL Studio — mở VIDEO BẢNG TRẮNG (bản Claude) ngay trong app.

Không chép/sửa gì phần mềm bảng trắng của anh: app chỉ tìm thư mục video-bang-trang-claude,
chạy máy chủ của nó ở chế độ ẩn (không mở trình duyệt, không cửa sổ đen) rồi hiện giao diện
của nó trong một bảng lớn của HL Studio. Đang mở sẵn bằng mo-ung-dung.bat thì dùng luôn cái đó.
"""
from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

NOWIN = 0x08000000 if os.name == "nt" else 0
PORT = 8776
_PROC: dict = {"p": None, "port": 0}


def find(app_dir: Path, cfg: dict) -> Path | None:
    cands = []
    if cfg.get("vbt_claude_dir"):
        cands.append(Path(cfg["vbt_claude_dir"]))
    cands += [app_dir.parent / "video-bang-trang-claude", Path.home() / "video-bang-trang-claude"]
    cands += [Path(f"{d}:/video-bang-trang-claude") for d in "CDEFGH"]
    for c in cands:
        try:
            if (c / "scripts" / "app" / "server.py").exists():
                return c
        except Exception:  # noqa: BLE001
            pass
    return None


def _python(root: Path, vbt: Path | None) -> str:
    for p in [root / ".venv" / "Scripts" / "python.exe", root.parent / "video-bang-trang" / ".venv" / "Scripts" / "python.exe",
              *( [vbt / ".venv" / "Scripts" / "python.exe"] if vbt else [] ), root / ".venv" / "bin" / "python"]:
        if p.exists():
            return str(p)
    return sys.executable


def _alive(port: int) -> bool:
    """Cổng này có đúng là máy chủ Video Bảng Trắng không (không nhầm app khác)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1.5) as r:
            d = json.loads(r.read().decode("utf-8", "ignore") or "{}")
            return isinstance(d, dict) and d.get("edition") == "Claude"
    except Exception:  # noqa: BLE001
        return False


def start(app_dir: Path, cfg: dict, vbt: Path | None, log) -> dict:
    root = find(app_dir, cfg)
    if not root:
        raise RuntimeError("Không thấy thư mục video-bang-trang-claude (VD G:\\video-bang-trang-claude).")
    for port in range(PORT, PORT + 4):           # anh đã mở sẵn bằng mo-ung-dung.bat → dùng luôn
        if _alive(port):
            return {"url": f"http://127.0.0.1:{port}", "dir": str(root)}
    p = _PROC.get("p")
    if p is None or p.poll() is not None:
        py = _python(root, vbt)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        logf = open(root / "_hl-studio.log", "ab")  # noqa: SIM115
        _PROC["p"] = subprocess.Popen([py, str(root / "scripts" / "app" / "server.py"), "--no-browser", "--port", str(PORT)],
                                      cwd=str(root), env=env, stdout=logf, stderr=subprocess.STDOUT, creationflags=NOWIN)
        log(f"[bang-trang] mở Video Bảng Trắng: {root} ({py})")
    for _ in range(60):                           # chờ tối đa ~30 giây (lần đầu nạp thư viện hơi lâu)
        for port in range(PORT, PORT + 4):
            if _alive(port):
                return {"url": f"http://127.0.0.1:{port}", "dir": str(root)}
        if _PROC["p"].poll() is not None:
            raise RuntimeError("Video Bảng Trắng không chạy được — xem file _hl-studio.log trong " + str(root))
        time.sleep(.5)
    raise RuntimeError("Video Bảng Trắng mở quá lâu, anh bấm lại thử.")


@atexit.register
def stop() -> None:
    p = _PROC.get("p")
    if p is not None and p.poll() is None:
        try:
            p.terminate()
        except Exception:  # noqa: BLE001
            pass


# ---------- GỘP VÀO HL STUDIO: gọi máy chủ bảng trắng qua HL (cùng địa chỉ → không vướng chặn trình duyệt) ----------
def proxy(app_dir: Path, cfg: dict, vbt: Path | None, log, method: str, rest: str, query: str, body: bytes | None) -> tuple[int, str, bytes]:
    base = start(app_dir, cfg, vbt, log)["url"]
    rest = rest.lstrip("/")
    if not rest.startswith(("file", "static/")):
        rest = "api/" + rest                      # /api/vbt/plan → /api/plan của máy chủ bảng trắng
    url = f"{base}/{rest}" + (f"?{query}" if query else "")
    req = urllib.request.Request(url, data=body if method == "POST" else None, method=method,
                                 headers={"Content-Type": "application/json"} if method == "POST" else {})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, r.headers.get("Content-Type", "application/json"), r.read()
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        return e.code, e.headers.get("Content-Type", "application/json"), e.read()


def import_project(proj: Path, media_dir: Path, ffmpeg: str | None, log, only: str | None = None) -> dict:
    """Video bảng trắng đã vẽ xong → từng cảnh thành 1 đoạn video (hình vẽ tay + giọng đọc) để đưa lên dòng thời gian HL."""
    import hashlib

    import dung_muot
    import media_ai

    if not ffmpeg:
        raise RuntimeError("Cần ffmpeg")
    plan = json.loads((proj / "plan.json").read_text(encoding="utf-8"))
    out = []
    for sc in plan.get("scenes", []):
        if only and sc["id"] != only:
            continue
        sd = proj / "work" / sc["id"]
        mp4, wav, tj = sd / "scene.mp4", sd / "audio.wav", sd / "timing.json"
        if not mp4.exists():
            continue
        st = mp4.stat()
        h = hashlib.sha1(f"vbt|{mp4}|{st.st_mtime}|{st.st_size}".encode()).hexdigest()[:16]
        src = media_dir / f"{h}.mp4"
        if not (media_dir / f"{h}-v3.mp4").exists():
            media_ai.STATE["msg"] = f"Đang đưa cảnh {sc['id']} vào HL Studio…"
            cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(mp4)]
            if wav.exists():
                cmd += ["-i", str(wav), "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
            # giữ nét vẽ sắc: nén gần như không mất, khung khoá 1 giây/lần để tua nhanh
            cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-g", "30", "-movflags", "+faststart", str(src)]
            r = subprocess.run(cmd, capture_output=True, creationflags=NOWIN)
            if r.returncode != 0:
                raise RuntimeError("Không ghép được cảnh " + sc["id"] + ": " + r.stderr.decode("utf-8", "ignore")[-200:])
        m = dung_muot.prepare(ffmpeg, src, media_dir, h, log)
        m.update(name=f"Bảng trắng · {sc.get('title') or sc['id']}", vbt=1)
        try:
            src.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        cues = []
        try:
            cues = json.loads(tj.read_text(encoding="utf-8")).get("cues", [])
        except Exception:  # noqa: BLE001
            pass
        out.append({"media": m, "title": sc.get("title", ""), "cues": cues, "sid": sc["id"],
                    "elements": [{"label": e.get("label") or e.get("id", ""), "narration": e.get("narration", "")} for e in sc.get("elements", [])],
                    "narration": " ".join(e.get("narration", "") for e in sc.get("elements", [])).strip()})
    media_ai.STATE["msg"] = ""
    if not out:
        raise RuntimeError("Chưa có cảnh nào vẽ xong")
    return {"title": plan.get("title", ""), "scenes": out}


def redo_scene(app_dir: Path, cfg: dict, vbt: Path | None, proj: Path, sid: str, narr: list, title: str,
               media_dir: Path, ffmpeg: str | None, log, mock: bool = False) -> dict:
    """Anh sửa lời đọc 1 cảnh trong HL → đọc lại + chia vùng + vẽ lại đúng cảnh đó (giữ nguyên tranh), rồi thay vào dòng thời gian."""
    import media_ai

    root = find(app_dir, cfg)
    if not root:
        raise RuntimeError("Không thấy thư mục video-bang-trang-claude")
    pf = proj / "plan.json"
    plan = json.loads(pf.read_text(encoding="utf-8"))
    sc = next((x for x in plan.get("scenes", []) if x["id"] == sid), None)
    if not sc:
        raise RuntimeError("Không thấy cảnh " + sid)
    for el, t in zip(sc.get("elements", []), narr):
        if isinstance(t, str) and t.strip():
            el["narration"] = t.strip()
    if title:
        sc["title"] = title
    pf.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    media_ai.STATE["msg"] = "Đang đọc lại và vẽ lại cảnh…"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([_python(root, vbt), "-u", str(root / "scripts" / "pipeline.py"), str(pf), "--redo", "tts,annotate,render",
                        "--scene", sid, "--stop-after", "render", "--res", "1920"] + (["--mock"] if mock else []),
                       cwd=str(root), env=env, capture_output=True, creationflags=NOWIN)
    media_ai.STATE["msg"] = ""
    if r.returncode != 0:
        raise RuntimeError("Vẽ lại lỗi: " + r.stdout.decode("utf-8", "ignore")[-300:])
    return import_project(proj, media_dir, ffmpeg, log, only=sid)
