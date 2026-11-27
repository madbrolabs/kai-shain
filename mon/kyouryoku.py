"""アドオン：協力者の広場（門番 mon.py のアドオン）＝協力者だけが入れる、クローズドなチャットと掲示板。

入口（合言葉なし・当てずっぽうでは当たらない長い鍵のアドレス・違えば 404）＝一人ずつのアドレス：
  /kamei/<鍵>/kyouryoku/・/kyaku/<鍵>/kyouryoku/ … 社長・亀井さん・岩田くん・勝山さんの専用ページの鍵（secret/kamei.json）。
  専用ページの札「💬 協力者の広場」から入る。新しい協力者は、専用ページを作れば（kamei.py の KYAKU に1行＋鍵）広場にも自動で入れる。
  みんなで共通の鍵のアドレス（/kyouryoku/<鍵>/）は 2026-11-27 社長の言葉で止めた（404）。
名前：入ったアドレスの鍵で決まる（名前の欄は無い）。社長の鍵＝「社長」、ほかは専用ページの呼び方（KYAKU の san）。
  呼び方を替える時は 内緒の場所/kyouryoku.json の namae（例 {"iwata": "岩田くん"}）。「社長」の札は社長の鍵から書いた物だけ。
  社長の鍵の時だけ、書き込みを消す・掲示板のピン留め（お知らせ）ができる。
中身：①チャット（みんなで話す。新しい書き込みは待ち受け（長く待つ読み）ですぐ出る）②掲示板（題をつけて投稿→返信。お知らせはピン留め）。
書き込みの置き場＝内緒の場所/kyouryoku/kaki.jsonl（1行1件・足すだけ。消した物も行は残し「消した」の行を足す＝画面から消える）。
入/切＝内緒の場所/kyouryoku.json の iri（無ければ入）。切れば全部の道が 404。
外の道＝443番の入口の /kamei・/kyaku の道（亀井ページと同じ）。
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
JST = dt.timezone(dt.timedelta(hours=9))
KAGI_KATACHI = re.compile(r"[A-Za-z0-9_-]{32,}")
NAGASA = {"na": 20, "bun": 2000, "dai": 60}
CHAT_MISERU = 300  # チャットは新しい物から300件まで出す
RENDA = (12, 60)  # 60秒に12件まで（同じ人＝同じ鍵＋同じ端末の印）


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def _rj(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def iri() -> bool:
    return _rj(naisho() / "kyouryoku.json").get("iri", True) is not False


def ima() -> str:
    return dt.datetime.now(JST).isoformat(timespec="seconds")


def kaki_p() -> Path:
    return naisho() / "kyouryoku" / "kaki.jsonl"


def namae(who: str) -> str:
    """書き込みに付ける名前（入ったアドレスの鍵で決まる）。"""
    n = _rj(naisho() / "kyouryoku.json").get("namae") or {}
    if isinstance(n.get(who), str) and n[who].strip():
        return n[who].strip()[:20]
    if who == "shachou":
        return "社長"
    try:
        import kamei
        if who in kamei.KYAKU:
            return kamei.KYAKU[who]["san"]
    except Exception:
        pass
    return "協力者"


def senyou_dare(k: str) -> str | None:
    """専用ページの鍵（社長・亀井さん・岩田さん・勝山さん）の持ち主。"""
    if not KAGI_KATACHI.fullmatch(k or ""):
        return None
    try:
        import kamei
        return kamei.dare(k)
    except Exception:
        K = _rj(naisho() / "secret" / "kamei.json")
        for who, v in K.items():
            if isinstance(v, str) and KAGI_KATACHI.fullmatch(v) and hmac.compare_digest(k, v):
                return who
        return None


# ---------- 書き込みの帳面（足すだけ） ----------
class Chou:
    def __init__(self, p: Path):
        self.p = p
        self.lock = threading.Lock()
        self.gyou: list[dict] = []
        self.kawatta: asyncio.Event | None = None  # 門番の中（イベントループの中）で作る
        try:
            for s in p.read_text(encoding="utf-8").splitlines():
                s = s.strip()
                if s:
                    try:
                        self.gyou.append(json.loads(s))
                    except Exception:
                        pass
        except FileNotFoundError:
            pass

    @property
    def v(self) -> int:
        return len(self.gyou)

    def tasu(self, o: dict) -> dict:
        with self.lock:
            o = {"id": secrets.token_hex(6), "t": ima(), **o}
            self.p.parent.mkdir(parents=True, exist_ok=True)
            with self.p.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
            self.gyou.append(o)
        if self.kawatta is not None:
            ev, self.kawatta = self.kawatta, asyncio.Event()
            ev.set()
        return o

    def katachi(self, who: str) -> dict:
        shachou = who == "shachou"
        kieta = {g["moto"] for g in self.gyou if g.get("shu") == "kesu"}
        pin: dict[str, bool] = {}
        for g in self.gyou:
            if g.get("shu") == "pin":
                pin[g["moto"]] = bool(g.get("pin"))

        def mise(g):
            o = {"id": g["id"], "t": g["t"], "na": g.get("na", ""), "bun": g.get("bun", "")}
            if g.get("dare") == "shachou":
                o["shachou"] = True
            if g.get("dare") == who:
                o["jibun"] = True
            return o

        chat = [mise(g) for g in self.gyou if g.get("shu") == "chat" and g["id"] not in kieta][-CHAT_MISERU:]
        sure = {}
        for g in self.gyou:
            if g.get("shu") == "sure" and g["id"] not in kieta:
                sure[g["id"]] = {**mise(g), "dai": g.get("dai", ""), "hen": [], "ato": g["t"], "pin": False}
        for g in self.gyou:
            if g.get("shu") == "hen" and g["id"] not in kieta and g.get("oya") in sure:
                s = sure[g["oya"]]
                s["hen"].append(mise(g))
                s["ato"] = g["t"]
        for i, p in pin.items():
            if i in sure:
                sure[i]["pin"] = p
        ita = sorted(sure.values(), key=lambda s: s["ato"], reverse=True)  # 新しく動いた順
        ita.sort(key=lambda s: not s["pin"])  # お知らせ（ピン留め）を上に
        return {"v": self.v, "chat": chat, "ita": ita, "shachou": shachou, "na": namae(who)}


CHOU: Chou | None = None
RENDA_KIROKU: dict[str, list[float]] = {}


def chou() -> Chou:
    global CHOU
    if CHOU is None:
        CHOU = Chou(kaki_p())
    if CHOU.kawatta is None:
        CHOU.kawatta = asyncio.Event()
    return CHOU


def renda_ok(hito: str) -> bool:
    n, byou = RENDA
    t = time.time()
    a = [x for x in RENDA_KIROKU.get(hito, []) if t - x < byou]
    if len(a) >= n:
        RENDA_KIROKU[hito] = a
        return False
    a.append(t)
    RENDA_KIROKU[hito] = a
    if len(RENDA_KIROKU) > 2000:
        RENDA_KIROKU.clear()
    return True


def kirei(s, n: int) -> str:
    s = str(s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f\u202a-\u202e\u2066-\u2069]", "", s)
    s = re.sub(r"\n{4,}", "\n\n\n", s).strip()
    return s[:n]


def tsukeru(app) -> None:
    from aiohttp import web

    def nai():
        return web.Response(status=404, text="404 Not Found")

    def kabuse(r):
        r.headers["Cache-Control"] = "no-store"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["X-Robots-Tag"] = "noindex, nofollow"
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        return r

    def jres(o, status=200):
        return kabuse(web.json_response(o, status=status, dumps=lambda v: json.dumps(v, ensure_ascii=False)))

    def dare(req) -> str | None:
        """入ってよい人なら who（shachou／kamei／iwata／katsuyama／kyouryoku）。ダメなら None。"""
        if not iri():
            return None
        return senyou_dare(req.match_info.get("k", ""))

    async def page(req):
        if not dare(req):
            return nai()
        if not req.path.endswith("/"):
            raise web.HTTPFound(req.path + "/")
        r = web.Response(text=(HERE / "kyouryoku.html").read_text(encoding="utf-8"), content_type="text/html")
        r.headers["Content-Security-Policy"] = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                                                "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        return kabuse(r)

    async def yomu(req):
        who = dare(req)
        if not who:
            return nai()
        c = chou()
        try:
            v = int(req.query.get("v", "-1"))
        except ValueError:
            v = -1
        if v == c.v:  # 変わるまで最大25秒待つ（新しい書き込みがすぐ出る）
            try:
                await asyncio.wait_for(c.kawatta.wait(), 25)
            except asyncio.TimeoutError:
                pass
        o = c.katachi(who)
        return jres(o)

    async def kaku(req):
        who = dare(req)
        if not who:
            return nai()
        if req.headers.get("X-KAI") != "1":  # よそのページから押させない（この印はよそからは付けられない）
            return jres({"ok": False, "naze": "印がありません"}, 403)
        try:
            x = await req.json()
        except Exception:
            return jres({"ok": False, "naze": "形が違います"}, 400)
        shu = req.match_info["shu"]
        hito = who + "|" + str(x.get("tanmatsu", ""))[:40] + "|" + (req.headers.get("X-Forwarded-For") or req.remote or "")
        c = chou()
        if shu in ("kesu", "pin"):
            if who != "shachou":
                return jres({"ok": False, "naze": "社長だけができます"}, 403)
            moto = str(x.get("moto", ""))
            if not any(g["id"] == moto and g.get("shu") in ("chat", "sure", "hen") for g in c.gyou):
                return jres({"ok": False, "naze": "見つかりません"}, 404)
            o = {"shu": shu, "moto": moto, "dare": who}
            if shu == "pin":
                o["pin"] = bool(x.get("pin"))
            c.tasu(o)
            return jres({"ok": True, "v": c.v})
        if shu not in ("chat", "sure", "hen"):
            return nai()
        na = namae(who)  # 名前は入ったアドレスの鍵で決まる（送られて来た名前は使わない）
        bun = kirei(x.get("bun"), NAGASA["bun"])
        if not bun:
            return jres({"ok": False, "naze": "中身を入れてください"}, 400)
        if not renda_ok(hito):
            return jres({"ok": False, "naze": "続けて書きすぎです。少し待ってください"}, 429)
        o = {"shu": shu, "na": na, "bun": bun, "dare": who}
        if shu == "sure":
            dai = kirei(x.get("dai"), NAGASA["dai"]).replace("\n", " ")
            if not dai:
                return jres({"ok": False, "naze": "題を入れてください"}, 400)
            o["dai"] = dai
        if shu == "hen":
            oya = str(x.get("oya", ""))
            kieta = {g["moto"] for g in c.gyou if g.get("shu") == "kesu"}
            if oya in kieta or not any(g["id"] == oya and g.get("shu") == "sure" for g in c.gyou):
                return jres({"ok": False, "naze": "その投稿はもうありません"}, 404)
            o["oya"] = oya
        g = c.tasu(o)
        return jres({"ok": True, "id": g["id"], "v": c.v})

    r = app.router
    # 頭の言葉は決まった字で書く（頭を「{m}」の形にすると、門番の振り分けが亀井ページの「その他は404」（/kamei/{k}/{tail}）を先に当ててしまう）
    for atama in ("/kamei/{k}/kyouryoku", "/kyaku/{k}/kyouryoku"):
        r.add_get(atama, page)
        r.add_get(atama + "/", page)
        r.add_get(atama + "/api/yomu", yomu)
        r.add_post(atama + "/api/{shu}", kaku)
