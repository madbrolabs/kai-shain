"""アドオン：仕事の種類で頭を選ぶ（L9・2026-11-25 係長の頼み）。言い直し係（yaku.py）が AI に頼む所だけで使う。
  言い直し（短い言い換え）＝karui（haiku）／1日のまとめ＝futsuu（sonnet）。表は C:\\cl\\ai_norikae\\atama\\shurui.json（AI乗り換えの正本）。
入/切＝内緒の場所/atama_tsunagi.json の iri（無ければ入）。切・atama が読めない・答えが空 → 今までどおり opus medium で頼む（何も壊さない）。
ゲージ（決2）：AI を使ったこのソフトが1回だけ、内緒の場所/gauge/<年月>.jsonl に書く（soft=kai_shain・atama つき）。
  内緒の場所/secret/gauge.json {"url","k"} が置かれたら、まだ送っていない行を超議事録の q=gauge_tsukau へ送る（中身の文は送らない・数だけ）。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

ATAMA_DIR = Path(os.environ.get("AINORIKAE_ATAMA", r"C:\cl\ai_norikae\atama"))
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_lock = threading.Lock()


def _rj(p: Path, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return d


def iri(naisho: Path) -> bool:
    return _rj(naisho / "atama_tsunagi.json", {}).get("iri", True) is not False


def _atama():
    if str(ATAMA_DIR) not in sys.path:
        sys.path.insert(0, str(ATAMA_DIR))
    import atama  # noqa: PLC0415
    return atama


def mukashi(exe: str, prompt: str) -> str:
    """今までどおりの頼み方（opus medium・道具なし）。"""
    r = subprocess.run([exe, "-p", "--model", "opus", "--effort", "medium", "--tools", "",
                        "--output-format", "text", "--no-session-persistence"],
                       input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=900, creationflags=NO_WINDOW, cwd=os.environ.get("TEMP", "."))
    return r.stdout or ""


def kiku(naisho: Path, exe: str | None, prompt: str, shurui: str, naiyou: str) -> str:
    """種類で頭を選んで1回頼み、返事の文を返す。使った量をゲージに1行書く。"""
    out, atama_na = "", "claude-opus"
    if iri(naisho):
        try:
            a = _atama()
            atama_na = a.erabu(shurui).get("atama") or atama_na
            out = a.kiku(prompt, shurui=shurui, tools="", timeout=900) or ""
        except Exception as e:  # noqa: BLE001
            print("頭えらびが使えず今までどおり:", type(e).__name__, file=sys.stderr)
            out = ""
    if not out.strip() and exe:
        atama_na = "claude-opus"
        out = mukashi(exe, prompt)
    if out.strip():
        gauge_kaku(naisho, naiyou, len(prompt) + len(out), atama_na)
    return out


def gauge_kaku(naisho: Path, naiyou: str, token: int, atama_na: str) -> None:
    p = naisho / "gauge" / (dt.datetime.now().strftime("%Y%m") + ".jsonl")
    row = {"id": "kai_shain-" + dt.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(4),
           "soft": "kai_shain", "yobimoto": "kai_shain", "naiyou": naiyou, "token": int(token), "oto_fun": 0,
           "atama": atama_na, "hi": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "okutta": False}
    with _lock:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def gauge_okuru(naisho: Path) -> int:
    """まだ送っていない行を超議事録へ送る。つなぎ先が無ければ何もしない。送れた数を返す。"""
    s = _rj(naisho / "secret" / "gauge.json", {})
    url, k = s.get("url"), s.get("k")
    if not url or not k:
        return 0
    n = 0
    for p in sorted((naisho / "gauge").glob("*.jsonl")):
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        kawatta = False
        for r in rows:
            if r.get("okutta"):
                continue
            body = {x: r[x] for x in ("id", "soft", "yobimoto", "naiyou", "token", "oto_fun", "atama")}
            try:
                req = urllib.request.Request(url + ("&" if "?" in url else "?") + "q=gauge_tsukau&k=" + k,
                                             data=json.dumps(body).encode(), method="POST",
                                             headers={"Content-Type": "text/plain"})
                with urllib.request.urlopen(req, timeout=60) as res:
                    o = json.loads(res.read().decode("utf-8", "replace"))
                if o.get("ok") or o.get("err") == "mou":  # 同じ id は1回分（受け口が数え済みと言えば済み）
                    r["okutta"] = True
                    kawatta = True
                    n += 1
            except Exception as e:  # noqa: BLE001
                print("ゲージを送れず（次に送る）:", type(e).__name__, file=sys.stderr)  # 鍵・アドレスは出さない
                break
        if kawatta:
            t = p.with_suffix(".tmp")
            t.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
            os.replace(t, p)
    return n
