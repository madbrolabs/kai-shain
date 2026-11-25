"""アドオン：社内向けの資料（営業用資料の棚・公式・お客のページには出さない物）を、決めた人の専用ページだけに出す（2026-11-26）。

中身＝内緒の場所/shanai/<id>/（写し）と 内緒の場所/shanai/shanai.json（一覧）。公開の倉庫には置かない。
shanai.json＝{"shiryou": [{"id": "enything_present", "dai": "題", "dare": {"shachou": "一言", "kamei": "一言"},
  "heya": "【主任】縁ything", "dekita": "2026-11-26", "at": "…", "hiraku": "index.html", "sumaho": "sumaho.html", "e": "e.jpg"}]}
dare に名前のある人（shachou／kamei など kamei.dare の答え）にだけ、「新しく出来た物」の札と中身の道が出る。それ以外は 404。
道＝/kamei|kyaku/<鍵>/shanai/<id>/<ファイル>。札は hiraku（パソコン用）／sumaho（スマホ用）を画面の幅で開き分ける。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ID = re.compile(r"[a-z0-9_-]{1,40}")
REL = re.compile(r"[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*")


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def basho() -> Path:
    return Path(os.environ.get("KAI_SHANAI") or naisho() / "shanai")  # KAI_SHANAI＝試しの時だけ別の場所


def ichiran() -> list[dict]:
    try:
        j = json.loads((basho() / "shanai.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    return [x for x in j.get("shiryou", []) if isinstance(x, dict) and ID.fullmatch(str(x.get("id", ""))) and isinstance(x.get("dare"), dict)]


def miseru(who: str | None) -> list[dict]:
    """その人に見せてよい社内向けの資料（札の材料）。"""
    return [x for x in ichiran() if who and who in x["dare"]]


def fairu(fid: str, rel: str) -> Path | None:
    if not ID.fullmatch(fid or "") or not REL.fullmatch(rel or "") or ".." in rel:
        return None
    ne = (basho() / fid).resolve()
    p = (ne / rel).resolve()
    return p if p.is_file() and ne in p.parents else None


def tsukeru(app) -> None:
    from aiohttp import web

    def nai():
        return web.Response(status=404, text="404 Not Found")

    async def michi(req):
        try:
            import kamei
            who = kamei.dare(req.match_info.get("k", ""))
        except Exception:
            who = None
        fid = req.match_info.get("id", "")
        x = next((x for x in miseru(who) if x["id"] == fid), None)
        if not x:
            return nai()
        rel = req.match_info.get("rel", "")
        if not rel:
            if not req.path.endswith("/"):
                raise web.HTTPFound(req.path + "/")
            rel = str(x.get("hiraku") or "index.html")
        p = fairu(fid, rel)
        if not p:
            return nai()
        r = web.FileResponse(p)
        r.headers["Cache-Control"] = "private, no-cache"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["X-Robots-Tag"] = "noindex"
        return r

    r = app.router
    for m in ("kamei", "kyaku"):
        r.add_get(f"/{m}/{{k}}/shanai/{{id}}", michi)
        r.add_get(f"/{m}/{{k}}/shanai/{{id}}/", michi)
        r.add_get(f"/{m}/{{k}}/shanai/{{id}}/{{rel:.+}}", michi)
