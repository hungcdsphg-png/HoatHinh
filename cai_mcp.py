# -*- coding: utf-8 -*-
"""
Cài máy chủ MCP "hl-studio" vào các phần mềm AI trên máy (chạy 1 lần):
  Claude Desktop · Claude Code · Gemini CLI / Antigravity · Codex · Cursor
Mỗi file cấu hình được sao lưu (.bak-hl) trước khi sửa. Chạy lại nhiều lần không sao.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
PY = Path(sys.executable)
if PY.name.lower() == "pythonw.exe" and PY.with_name("python.exe").exists():
    PY = PY.with_name("python.exe")
SERVER = {"command": str(PY), "args": [str(APP / "hl_mcp.py")]}
HOME = Path.home()
APPDATA = Path(os.environ.get("APPDATA") or (HOME / "AppData" / "Roaming"))


def merge_json(f: Path, key: str = "mcpServers", create: bool = False) -> str:
    if not f.exists() and not create:
        return ""
    f.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8") or "{}")
        except Exception:  # noqa: BLE001
            return f"  ! {f} không đọc được (JSON lỗi), bỏ qua"
        shutil.copyfile(f, f.with_name(f.name + ".bak-hl"))
    data.setdefault(key, {})["hl-studio"] = dict(SERVER)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"  ✓ {f}"


def codex(f: Path) -> str:
    if not f.parent.exists():
        return ""
    txt = f.read_text(encoding="utf-8") if f.exists() else ""
    if "[mcp_servers.hl-studio]" in txt:
        return f"  ✓ {f} (đã có)"
    if f.exists():
        shutil.copyfile(f, f.with_name(f.name + ".bak-hl"))
    esc = lambda s: s.replace("\\", "\\\\")  # noqa: E731
    txt += f'\n[mcp_servers.hl-studio]\ncommand = "{esc(SERVER["command"])}"\nargs = ["{esc(SERVER["args"][0])}"]\nstartup_timeout_sec = 30\ntool_timeout_sec = 900\n'
    f.write_text(txt, encoding="utf-8")
    return f"  ✓ {f}"


def claude_code() -> str:
    exe = shutil.which("claude")
    if exe:
        try:
            subprocess.run([exe, "mcp", "remove", "--scope", "user", "hl-studio"], capture_output=True, timeout=60)
            r = subprocess.run([exe, "mcp", "add", "--scope", "user", "hl-studio", "--", SERVER["command"], *SERVER["args"]], capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                return "  ✓ Claude Code (claude mcp add --scope user)"
        except Exception:  # noqa: BLE001
            pass
    return merge_json(HOME / ".claude.json")


def main() -> None:
    print("Cài MCP HL Studio cho các AI trên máy")
    print("  lệnh chạy:", SERVER["command"], SERVER["args"][0])
    out = [
        merge_json(APPDATA / "Claude" / "claude_desktop_config.json", create=(APPDATA / "Claude").exists()),
        claude_code(),
        merge_json(HOME / ".gemini" / "settings.json", create=(HOME / ".gemini").exists()),
        merge_json(HOME / ".gemini" / "antigravity" / "mcp_config.json", create=(HOME / ".gemini" / "antigravity").exists()),
        codex(HOME / ".codex" / "config.toml"),
        merge_json(HOME / ".cursor" / "mcp.json", create=(HOME / ".cursor").exists()),
    ]
    got = [x for x in out if x]
    print("\n".join(got) if got else "  (không thấy phần mềm AI nào trên máy để cài)")
    snippet = json.dumps({"mcpServers": {"hl-studio": SERVER}}, ensure_ascii=False, indent=2)
    (APP / "mcp-config-mau.json").write_text(snippet, encoding="utf-8")
    print("\nĐoạn cấu hình mẫu (dán vào phần mềm AI khác nếu cần):", APP / "mcp-config-mau.json")
    print(snippet)
    print("\nXONG. Đóng hẳn rồi mở lại Claude Desktop / Antigravity / Codex để thấy công cụ hl-studio.")


if __name__ == "__main__":
    main()
