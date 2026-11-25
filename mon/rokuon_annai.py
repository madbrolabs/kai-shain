"""アドオン：録音君の入れ方と使い方（案内ページ）を、鍵のある人だけが開けるようにする。

中身＝内緒の場所/rokuon_annai/（index.html と e/ の絵）。公開の倉庫には置かない（写真に案内ページの画面が写るため）。
道：
- /kai_mon/rokuon_annai/<社員か社長の鍵>/[道]   社員ページの「まずはここから」札から
- /kamei|kyaku/<鍵>/rokuon_annai/[道]           社長・お客の専用ページの札から（鍵は hajimete.kagi_ok と同じ決まり）
違う鍵・中身の外への道は 404。入/切＝内緒の場所/rokuon_annai.json の iri（無ければ入）。門番 mon.py が kamei より先に付ける。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REL = re.compile(r"(index\.html|e/[A-Za-z0-9_]+\.(jpg|png))")


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def iri() -> bool:
    try:
        return json.loads((naisho() / "rokuon_annai.json").read_text(encoding="utf-8")).get("iri", True) is not False
    except Exception:
        return True


def fairu(rel: str) -> Path | None:
    rel = rel or "index.html"
    if not REL.fullmatch(rel):
        return None
    p = naisho() / "rokuon_annai" / rel
    return p if p.is_file() else None


def tsukeru(app, dare) -> None:
    from aiohttp import web

    def nai():
        return web.Response(status=404, text="404 Not Found")

    def dasu(req, rel):
        if not req.path.endswith("/") and not rel:
            raise web.HTTPFound(req.path + "/")  # 絵を相対の道 e/… で読むため
        p = fairu(rel)
        if not p:
            return nai()
        r = web.FileResponse(p)
        r.headers["Cache-Control"] = "private, no-cache"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["X-Robots-Tag"] = "noindex"
        return r

    async def shain(req):
        if not iri() or not dare(req.match_info.get("k", "")):
            return nai()
        return dasu(req, req.match_info.get("rel", ""))

    async def kyaku(req):
        try:
            import hajimete
            ok = hajimete.kagi_ok(req.match_info.get("k", ""))
        except Exception:
            ok = False
        if not iri() or not ok:
            return nai()
        return dasu(req, req.match_info.get("rel", ""))

    r = app.router
    r.add_get("/kai_mon/rokuon_annai/{k}", shain)
    r.add_get("/kai_mon/rokuon_annai/{k}/", shain)
    r.add_get("/kai_mon/rokuon_annai/{k}/{rel:.+}", shain)
    for m in ("kamei", "kyaku"):
        r.add_get(f"/{m}/{{k}}/rokuon_annai", kyaku)
        r.add_get(f"/{m}/{{k}}/rokuon_annai/", kyaku)
        r.add_get(f"/{m}/{{k}}/rokuon_annai/{{rel:.+}}", kyaku)
