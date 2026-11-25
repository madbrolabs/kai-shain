"""アドオン：営業用資料の棚の「社員だけ」の写し（検めに当たって公式ページに出さない物）を開く口。

写しと一覧は atsume/eigyou.py が 内緒の場所/eigyou/ に作る（kakushi/<id>/・tana.json・moji/<id>.txt）。公開の物は GitHub Pages の docs/eigyou/ にあり、ここは通らない。
- POST /kai_mon/eigyou {k}            社員・社長の鍵 → 社員だけの物の一覧（公開の物は docs/eigyou/tana.json を画面が読む）
- GET /kai_mon/eigyou_mi/<社員か社長の鍵>/<id>/[道][?dl=1]  社員ページから開く・保存する（HTML の絵・動画も相対の道で読める）
- GET /kamei|kyaku/<鍵>/eigyou/<id>/[道]  社長・お客の専用アドレス → 写し（HTML の絵も相対の道で読める）。
  お客の鍵では、そのお客に隠す言葉（kamei.kakusu_kotoba・hoka_kotoba）が本文にある資料は 404。
入/切＝内緒の場所/eigyou.json の iri（無ければ入）。門番 mon.py が kamei より先に付ける。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ID = re.compile(r"[0-9a-f]{12}")


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def _rj(p: Path, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return d


def iri() -> bool:
    return _rj(naisho() / "eigyou.json", {}).get("iri", True) is not False


def kakushi_tana() -> list[dict]:
    """社員だけの物（kouhou でない物）。返す項目は棚の札に要る物だけ。"""
    out = []
    for t in _rj(naisho() / "eigyou" / "tana.json", {}).get("tana", []):
        if t.get("kouhou"):
            continue
        out.append({k: t.get(k, "") for k in ("id", "dai", "hitokoto", "dekita", "naoshita", "at", "shurui", "hiraku", "zentai",
                                              "ookisa", "ookisa_zentai", "dl_na", "dl_na_zentai", "e", "soto",
                                              "sumaho", "ookisa_sumaho")})
    return out


def fairu(fid: str, rel: str) -> Path | None:
    """社員だけの写しの中の1つ（道の外へは出ない）。"""
    if not ID.fullmatch(fid or ""):
        return None
    t = next((t for t in _rj(naisho() / "eigyou" / "tana.json", {}).get("tana", []) if t.get("id") == fid and not t.get("kouhou")), None)
    if not t:
        return None
    base = (naisho() / "eigyou" / "kakushi" / fid).resolve()
    rel = rel or t.get("hiraku") or ""
    if not rel or "\\" in rel or ".." in rel.split("/"):
        return None
    p = (base / rel).resolve()
    return p if p.is_file() and base in p.parents else None


def okyaku_ok(who: str, fid: str) -> bool:
    """その人のページの成果物に出ている資料だけ開ける（亀井ページと同じ決まり＝nozoku・隠す言葉・お客ごとの出し分け）。"""
    try:
        import kamei
        return any(x.get("eigyou") and x["id"] == fid for x in kamei.daichou(who))
    except Exception:
        return False


def tsukeru(app, dare, jres, cors) -> None:
    from aiohttp import web

    def nai():
        return web.Response(status=404, text="404 Not Found")

    async def ichiran(req):
        try:
            d = await req.json()
        except Exception:
            d = {}
        if not dare(d.get("k", "")):
            return jres(req, {"ok": False, "err": "kagi"}, 403)
        if not iri():
            return jres(req, {"ok": True, "iri": False, "tana": []})
        return jres(req, {"ok": True, "tana": kakushi_tana()})

    async def mi(req):
        """社員ページから開く：/kai_mon/eigyou_mi/<社員か社長の鍵>/<id>/[道]（HTML の絵・動画も相対の道で読める）。?dl=1 で保存。"""
        if not dare(req.match_info.get("k", "")) or not iri():
            return nai()
        rel = req.match_info.get("rel", "")
        if not rel and not req.path.endswith("/"):
            raise web.HTTPFound(req.path + "/")
        p = fairu(req.match_info.get("id", ""), rel)
        if not p:
            return nai()
        r = web.FileResponse(p)
        r.headers["Cache-Control"] = "private, no-cache"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["X-Robots-Tag"] = "noindex"
        if req.query.get("dl"):
            t = next((t for t in kakushi_tana() if t["id"] == req.match_info.get("id")), {})
            na = (t.get("dl_na_zentai") if rel and rel == t.get("zentai") else t.get("dl_na")) or p.name
            from urllib.parse import quote
            r.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(na)}"
        return r

    async def michi(req):
        try:
            import kamei
            who = kamei.dare(req.match_info.get("k", ""))
        except Exception:
            who = None
        fid = req.match_info.get("id", "")
        if not who or not iri() or not okyaku_ok(who, fid):
            return nai()
        rel = req.match_info.get("rel", "")
        if not rel and not req.path.endswith("/"):
            raise web.HTTPFound(req.path + "/")  # HTML が絵を相対の道で読むため、斜線で終わる道にそろえる
        p = fairu(fid, rel)
        if not p:
            return nai()
        r = web.FileResponse(p)
        r.headers["Cache-Control"] = "private, no-cache"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["X-Robots-Tag"] = "noindex"
        return r

    r = app.router
    r.add_post("/kai_mon/eigyou", ichiran)
    r.add_get("/kai_mon/eigyou_mi/{k}/{id}", mi)
    r.add_get("/kai_mon/eigyou_mi/{k}/{id}/", mi)
    r.add_get("/kai_mon/eigyou_mi/{k}/{id}/{rel:.+}", mi)
    for m in ("kamei", "kyaku"):
        r.add_get(f"/{m}/{{k}}/eigyou/{{id}}", michi)
        r.add_get(f"/{m}/{{k}}/eigyou/{{id}}/", michi)
        r.add_get(f"/{m}/{{k}}/eigyou/{{id}}/{{rel:.+}}", michi)
