"""アドオン：はじめての人の入口を、亀井ページ（社長・亀井さんの専用アドレス）の下で読めるようにする。

道＝/kamei/<鍵>/hajimete/（鍵は 内緒の場所/secret/kamei.json の値のどれか。違えば 404）。
中身＝社員ページの手引き（core の settei.json の tebiki_dir）にある「0_はじめての人の入口.md」1枚だけ。社員ページと同じ文を出す（2か所に書かない）。
絵＝この倉庫の docs/img/hajimete/ の物だけ（../img/hajimete/x.jpg → ./img/x.jpg）。
入/切＝内緒の場所/hajimete.json の iri（無ければ入）。亀井ページ（kamei.py）は呼ばない。門番 mon.py が kamei より先に付ける。
"""
from __future__ import annotations

import hmac
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMG = HERE.parent / "docs" / "img" / "hajimete"
FAIRU = "0_はじめての人の入口.md"


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def _rj(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def iri() -> bool:
    return _rj(naisho() / "hajimete.json").get("iri", True) is not False


def kagi_ok(k: str) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,}", k or ""):
        return False
    # 鍵の形（43文字の英数字）の値だけ。作った日時（tsukutta）などは鍵にしない
    ks = [v for v in _rj(naisho() / "secret" / "kamei.json").values() if isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{32,}", v)]
    return any(hmac.compare_digest(k, v) for v in ks)


def md_yomu() -> str | None:
    tb = _rj(naisho() / "settei.json").get("tebiki_dir")
    if not tb:
        return None
    p = Path(tb) / FAIRU
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8")
    return t.replace("](../img/hajimete/", "](./img/")


def tsukeru(app) -> None:
    from aiohttp import web

    def nai():
        return web.Response(status=404, text="404 Not Found")

    def kabuse(r):
        r.headers["Cache-Control"] = "no-store"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["X-Robots-Tag"] = "noindex"
        return r

    def ok(req) -> bool:
        return iri() and kagi_ok(req.match_info.get("k", ""))

    async def page(req):
        if not ok(req):
            return nai()
        if not req.path.endswith("/"):
            raise web.HTTPFound(req.path + "/")
        return kabuse(web.Response(text=(HERE / "hajimete.html").read_text(encoding="utf-8"), content_type="text/html"))

    async def md(req):
        if not ok(req):
            return nai()
        t = md_yomu()
        if t is None:
            return nai()
        return kabuse(web.json_response({"md": t}, dumps=lambda v: json.dumps(v, ensure_ascii=False)))

    async def img(req):
        n = req.match_info.get("n", "")
        if not ok(req) or not re.fullmatch(r"[a-z0-9_]+\.(jpg|png)", n) or not (IMG / n).is_file():
            return nai()
        r = web.FileResponse(IMG / n)
        r.headers["Cache-Control"] = "max-age=3600"
        return r

    r = app.router
    r.add_get("/kamei/{k}/hajimete", page)
    r.add_get("/kamei/{k}/hajimete/", page)
    r.add_get("/kamei/{k}/hajimete/md", md)
    r.add_get("/kamei/{k}/hajimete/img/{n}", img)
