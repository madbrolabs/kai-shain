"""部屋（Claude の会話）へ、AI を使わずにプログラムだけで一言を届ける（亀井ページのアドオンの部品）。

しくみ（2026-11-25 claude.exe 2.1.330 の中身を読んで決めた）：
  ~/.claude/sessions/<pid>.json に部屋ごとの受け口（messagingSocketPath＝\\\\.\\pipe\\LOCAL\\cc-msg-…）が書いてある。
  同じ場所の <pid>.<64桁>.key に合図の札（peerToken）がある。SendMessage はこの札を1行目に、本文を2行目に書いて送っている。
  1行目 {"type":"auth","token":札}  2行目 {"type":"user","message":{"content":本文},"from":…,"session_id":…,"priority":"next"}
罠メモ：札は中身を外へ出さない（ログにも書かない）。session_id を付けると、部屋が別の会話に替わっていた時は捨てられる＝誤配しない。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

SESSIONS = Path(os.environ.get("KAI_CC_SESSIONS", str(Path.home() / ".claude" / "sessions")))
FROM = "社員ページの配達口"


def _ikiteru(pid: int) -> bool:
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    except Exception:
        return True


def ukeguchi(sid: str) -> dict | None:
    """その会話（session_id）を今開いている部屋の受け口。無ければ None。"""
    best = None
    for f in SESSIONS.glob("*.json"):
        try:
            o = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if o.get("sessionId") != sid or not o.get("messagingSocketPath"):
            continue
        if not isinstance(o.get("pid"), int) or not _ikiteru(o["pid"]):  # 札の pid が壊れていれば使わない
            continue
        if best is None or o.get("updatedAt", 0) > best.get("updatedAt", 0):
            best = o
    return best


def _fuda(pid: int) -> str | None:
    for k in SESSIONS.glob(f"{int(pid)}.*.key"):
        try:
            t = json.loads(k.read_text(encoding="utf-8")).get("peerToken")
            if isinstance(t, str) and len(t) == 32:
                return t
        except Exception:
            continue
    return None


def todokeru(sid: str, honbun: str, kara: str = FROM) -> tuple[str, str]:
    """戻り＝("todoita"|"nemuri"|"dame", 一言)。nemuri＝その部屋が今開いていない。"""
    u = ukeguchi(sid)
    if not u:
        return "nemuri", "部屋が開いていません"
    tok = _fuda(u["pid"])
    gyou = ""
    if tok:
        gyou += json.dumps({"type": "auth", "token": tok}) + "\n"
    gyou += json.dumps({"type": "user", "message": {"content": honbun}, "from": kara, "session_id": sid,
                        "msg_id": str(uuid.uuid4()), "priority": "next"}, ensure_ascii=False) + "\n"
    data = gyou.encode("utf-8")
    last = ""
    for i in range(4):  # 受け口が他の送り手で埋まっている時（ERROR_PIPE_BUSY）は少し待ってやり直す
        try:
            with open(u["messagingSocketPath"], "wb", buffering=0) as p:
                p.write(data)
            return "todoita", ("札あり" if tok else "札なし")
        except OSError as e:
            last = f"{type(e).__name__}:{getattr(e, 'winerror', '')}"
            time.sleep(0.2 * (i + 1))
    return "dame", last
