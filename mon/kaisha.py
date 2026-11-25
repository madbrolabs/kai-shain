"""アドオン：会社紹介ページ（外向けの「話すだけで、会社がつながる」）を、亀井ページ（社長・亀井さんの専用アドレス）の下で開けるようにする。

道＝/kamei/<鍵>/kaisha/（鍵は 内緒の場所/secret/kamei.json の値のどれか。違えば 404）。
中身＝内緒の場所/kaisha_shoukai/ の index.html と img/*.jpg（写しそのまま・文言は変えない）。公開の倉庫には入れない。
入/切＝内緒の場所/kaisha.json の iri（無ければ入）。亀井ページ（kamei.py）・はじめての入口（hajimete.py）は呼ばない。門番 mon.py が kamei より先に付ける。
"""
from __future__ import annotations

import hmac
import json
import os
import re
from pathlib import Path


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def basho() -> Path:
    return naisho() / "kaisha_shoukai"


def _rj(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def iri() -> bool:
    return _rj(naisho() / "kaisha.json").get("iri", True) is not False and (basho() / "index.html").is_file()


def kagi_ok(k: str) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,}", k or ""):
        return False
    # 鍵の形（43文字の英数字）の値だけ。作った日時（tsukutta）などは鍵にしない
    ks = [v for v in _rj(naisho() / "secret" / "kamei.json").values() if isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{32,}", v)]
    return any(hmac.compare_digest(k, v) for v in ks)


def tsukeru(app) -> None:
    from aiohttp import web

    def nai():
        return web.Response(status=404, text="404 Not Found")

    def kabuse(r):
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["X-Robots-Tag"] = "noindex"
        return r

    def ok(req) -> bool:
        return iri() and kagi_ok(req.match_info.get("k", ""))

    async def page(req):
        if not ok(req):
            return nai()
        if not req.path.endswith("/"):
            raise web.HTTPFound(req.path + "/")  # 絵を img/ の相対で読むため、斜線で終わる道にそろえる
        r = web.Response(body=(basho() / "index.html").read_bytes(), content_type="text/html", charset="utf-8")  # 写しをそのまま（改行も変えない）
        r.headers["Cache-Control"] = "no-store"
        return kabuse(r)

    async def img(req):
        n = req.match_info.get("n", "")
        if not ok(req) or not re.fullmatch(r"[a-z0-9_-]+\.(jpg|jpeg|png|webp)", n) or not (basho() / "img" / n).is_file():
            return nai()
        r = web.FileResponse(basho() / "img" / n)
        r.headers["Cache-Control"] = "private, max-age=3600"
        return kabuse(r)

    r = app.router
    for m in ("kamei", "kyaku"):  # /kyaku/<鍵>/＝お客の表の人の専用URL（kamei.py の MICHI と同じ）
        r.add_get(f"/{m}/{{k}}/kaisha", page)
        r.add_get(f"/{m}/{{k}}/kaisha/", page)
        r.add_get(f"/{m}/{{k}}/kaisha/img/{{n}}", img)
