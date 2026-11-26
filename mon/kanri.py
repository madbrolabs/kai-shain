"""管理画面（このPCだけ）：社長の決め事を、みんなの画面から切り離して1か所に集めた別のクライアント。
（通達 T1795712323 2026-11-27「なんで同じクライアントで使いまわしちゃうの？ 手抜き、怠慢一切禁止」）

- 門番（mon.py）が同じ中で起こす。聞くのは 127.0.0.1:8807（KAI_KANRI_PORT）だけ。トンネル（Tailscale）にも公開の置き場（GitHub Pages）にも載せない。
- ここでだけ出来る事：仮の更新の採用／見送り・主任からの相談の採用／見送り・参加の希望の招待／見送り・お客（亀井さんたち）の案の入れて／見送り。
  中身（GitHub への merge・close・招待、主任への知らせ）は前と同じ関数（mon.kettei_suru・kamei.kettei）を呼ぶだけ。
- 守り：①Host が 127.0.0.1:8807 か localhost:8807 の時だけ答える（よそのサイトから名前を付け替えて届かせる手を断る）
  ②/api/ は、この画面に埋めた合言葉（門番を起こすたびに作り直す）と、同じ所からの Origin が無ければ断る
  ③よその枠の中に入れさせない・控えを残させない。
- 開き方：デスクトップの近道「KAI 管理画面」（kanri_hiraku.py を pythonw で。窓を出さずに門番を確かめ、管理画面だけを開く）。
"""
from __future__ import annotations

import asyncio
import secrets
from pathlib import Path

from aiohttp import web

HERE = Path(__file__).resolve().parent


def tsukuru(port: int, *, log, kousin_yomu, sanka_yomu, kettei_suru, atsumeru) -> web.Application:
    token = secrets.token_urlsafe(24)
    yoi_host = {f"127.0.0.1:{port}", f"localhost:{port}"}
    yoi_origin = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    @web.middleware
    async def mamori(req: web.Request, handler):
        if req.host not in yoi_host or req.remote not in ("127.0.0.1", "::1"):
            return web.Response(status=403, text="403 Forbidden")
        if req.path.startswith("/api/"):
            o = req.headers.get("Origin")
            if req.headers.get("X-Kanri") != token or (req.method != "GET" and o not in yoi_origin) or (o and o not in yoi_origin):
                return web.json_response({"ok": False, "err": "kanri_dake"}, status=403)
        res = await handler(req)
        res.headers["Cache-Control"] = "no-store"
        res.headers["X-Frame-Options"] = "DENY"
        res.headers["X-Content-Type-Options"] = "nosniff"
        res.headers["Referrer-Policy"] = "no-referrer"
        res.headers["Content-Security-Policy"] = ("default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                  "script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
        return res

    def kamei_mod():
        try:
            import kamei
            return kamei if kamei.iri() else None
        except Exception as e:
            log(f"管理画面：亀井ページの表を読めませんでした {e!r}")
            return None

    async def page(req):
        t = (HERE / "kanri.html").read_text(encoding="utf-8").replace("__KANRI_TOKEN__", token)
        return web.Response(text=t, content_type="text/html", charset="utf-8")

    async def genki(req):
        return web.json_response({"ok": True, "kanri": True})

    async def ichiran(req):
        j = await asyncio.to_thread(kousin_yomu)
        km = kamei_mod()
        kt, kyaku_na = None, []
        if km:
            kt = list(reversed(await asyncio.to_thread(km.tsukutta)))
            try:
                kyaku_na = [km.kyaku(g)["san"] for g in km.KYAKU]
            except Exception:
                kyaku_na = []
        return web.json_response({"ok": True, "tsukutta": j.get("tsukutta", ""), "soft": j.get("soft", []),
                                  "todoita": j.get("todoita", []), "sanka": await asyncio.to_thread(sanka_yomu),
                                  "kamei": kt, "kyaku_na": kyaku_na})

    async def kettei(req):
        try:
            d = await req.json()
        except Exception:
            return web.json_response({"ok": False, "err": "形が違います"}, status=400)
        shurui, k = d.get("shurui"), d.get("kettei")
        if shurui == "kamei":
            km = kamei_mod()
            if not km:
                return web.json_response({"ok": False, "err": "亀井ページが切りです"}, status=404)
            try:
                ok, e = await asyncio.to_thread(km.kettei, int(d.get("i")), str(k))
            except Exception:
                ok, e = False, "形が違います"
            log(f"管理画面：お客の案 {d.get('i')} → {k} {'OK' if ok else e}")
            return web.json_response({"ok": ok, "err": e}, status=200 if ok else 400)
        if shurui == "pr":
            o, s = await kettei_suru({"soft": d.get("soft"), "n": d.get("n"), "kettei": k})
        elif shurui in ("todoita", "sanka"):
            o, s = await kettei_suru({"shurui": shurui, "id": d.get("id"), "kettei": k})
        else:
            o, s = {"ok": False, "err": "形が違います"}, 400
        log(f"管理画面：{shurui} {d.get('soft', '')}{d.get('n', '')}{d.get('id', '')} → {k} {s}")
        return web.json_response(o, status=s, dumps=lambda x: __import__("json").dumps(x, ensure_ascii=False))

    async def yomi_naoshi(req):
        await asyncio.to_thread(atsumeru)
        return web.json_response({"ok": True})

    app = web.Application(middlewares=[mamori], client_max_size=1024 * 1024)
    app.router.add_get("/", page)
    app.router.add_get("/genki", genki)
    app.router.add_get("/kanri.ico", lambda req: web.FileResponse(HERE / "kanri.ico"))
    app.router.add_get("/api/ichiran", ichiran)
    app.router.add_post("/api/kettei", kettei)
    app.router.add_post("/api/yomi_naoshi", yomi_naoshi)
    return app
