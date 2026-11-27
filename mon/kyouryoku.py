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
写真・ファイル（2026-11-27）：チャット・掲示板・返信に付けられる（1つ20MBまで・写真は送る前に端末で縮める）。
  置き場＝内緒の場所/kyouryoku/fairu/<番号>（中身）と <番号>.json（名前・大きさ・誰が）。出すのは鍵の道の下だけ
  （/…/kyouryoku/fairu/<番号>/<名前>）。見える書き込みに付いた物と、付ける前の自分の物だけ出す。
  社長が書き込みを消すと、付いていた物は 内緒の場所/kyouryoku/fairu/_kieta/ へ移し、もう出さない。
知らせ（2026-11-27）：Web Push（アプリを入れない）。広場の「🔔 知らせを受け取る」で端末を登録→新しい書き込み・投稿・返信で知らせる
  （自分の書き込みは知らせない）。登録＝内緒の場所/kyouryoku/tsuuchi.json（人ごと）。送り主の鍵＝内緒の場所/secret/kyouryoku_vapid.json。
  暗号の部品は 内緒の場所/pylib の cryptography（webpush.py）。
入/切：内緒の場所/kyouryoku.json の fairu・tsuuchi（false で、その働きだけ止まる・ボタンも消える）。
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
FAIRU_MAX = 20 * 1024 * 1024  # 1つの大きさの上限
FAIRU_KAZU = 6  # 1つの書き込みに付けられる数
FID = re.compile(r"[0-9a-f]{24}")


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def _rj(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def iri() -> bool:
    return _rj(naisho() / "kyouryoku.json").get("iri", True) is not False


def kinou() -> dict:
    """足した働きの入/切（無ければ入）。知らせは暗号の部品が読める時だけ。"""
    c = _rj(naisho() / "kyouryoku.json")
    t = c.get("tsuuchi", True) is not False
    if t:
        try:
            import webpush
            t = webpush.tsukaeru()
        except Exception:
            t = False
    return {"fairu": c.get("fairu", True) is not False, "tsuuchi": t}


def fairu_d() -> Path:
    return naisho() / "kyouryoku" / "fairu"


def fairu_meta(fid: str) -> dict | None:
    if not FID.fullmatch(fid or ""):
        return None
    m = _rj(fairu_d() / (fid + ".json"))
    return m if m and (fairu_d() / fid).is_file() else None


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

    def kieta(self) -> set:
        """消した書き込み（消した投稿の返信も含む）。"""
        k = {g["moto"] for g in self.gyou if g.get("shu") == "kesu"}
        k |= {g["id"] for g in self.gyou if g.get("shu") == "hen" and g.get("oya") in k}
        return k

    def fairu_moto(self) -> dict:
        """付けた物の番号 → 付いている書き込みの番号。"""
        m = {}
        for g in self.gyou:
            for f in g.get("fairu") or []:
                m[f.get("id")] = g["id"]
        return m

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
        kieta = self.kieta()
        pin: dict[str, bool] = {}
        for g in self.gyou:
            if g.get("shu") == "pin":
                pin[g["moto"]] = bool(g.get("pin"))

        def mise(g):
            o = {"id": g["id"], "t": g["t"], "na": g.get("na", ""), "bun": g.get("bun", "")}
            if g.get("fairu"):
                o["fairu"] = [{"id": f["id"], "na": f.get("na", ""), "ookisa": f.get("ookisa", 0), "gazou": bool(f.get("gazou"))} for f in g["fairu"]]
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
        return {"v": self.v, "chat": chat, "ita": ita, "shachou": shachou, "na": namae(who), "kinou": kinou()}


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


# ---------- 写真・ファイル ----------
def nakami_shu(atama: bytes) -> tuple[str, bool]:
    """中身の頭の字で種類を決める（送ってきた側の言う種類は使わない）。返り値＝(出す種類, 写真か)。"""
    if atama[:3] == b"\xff\xd8\xff":
        return "image/jpeg", True
    if atama[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", True
    if atama[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", True
    if atama[:4] == b"RIFF" and atama[8:12] == b"WEBP":
        return "image/webp", True
    if atama[:5] == b"%PDF-":
        return "application/pdf", False
    return "application/octet-stream", False


def fairu_na(s: str) -> str:
    s = kirei(s, 120).replace("\n", " ")
    s = re.sub(r'[\\/:*?"<>|]', "_", s).strip(" .")
    return s or "fairu"


def fairu_sutete(c: "Chou", moto_ids: set) -> None:
    """消した書き込みに付いていた物を _kieta へ移す（もう出さない）。"""
    d = fairu_d()
    k = d / "_kieta"
    for g in c.gyou:
        if g["id"] in moto_ids:
            for f in g.get("fairu") or []:
                fid = f.get("id", "")
                if not FID.fullmatch(fid):
                    continue
                for nm in (fid, fid + ".json"):
                    try:
                        if (d / nm).exists():
                            k.mkdir(parents=True, exist_ok=True)
                            os.replace(d / nm, k / nm)
                    except Exception:
                        pass


# ---------- 知らせ（Web Push） ----------
def tsuuchi_p() -> Path:
    return naisho() / "kyouryoku" / "tsuuchi.json"


TSUUCHI_LOCK = threading.Lock()


def tsuuchi_yomu() -> dict:
    d = _rj(tsuuchi_p())
    return d if isinstance(d, dict) else {}


def tsuuchi_kaku(d: dict) -> None:
    p = tsuuchi_p()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


async def shiraseru(o: dict) -> None:
    """新しい書き込みを、書いた人以外の登録した端末へ知らせる。"""
    if not kinou()["tsuuchi"]:
        return
    try:
        import aiohttp
        import webpush
    except Exception:
        return
    bun = (o.get("bun") or "").replace("\n", " ")
    if not bun and o.get("fairu"):
        bun = "📷 写真" if all(f.get("gazou") for f in o["fairu"]) else "📎 ファイル"
    if len(bun) > 80:
        bun = bun[:80] + "…"
    if o["shu"] == "chat":
        dai, michi = f"💬 {o['na']}", "#chat"
    elif o["shu"] == "sure":
        dai, michi = f"📋 新しい投稿：{o.get('dai', '')}", "#ita/" + o["id"]
        bun = f"{o['na']}：{bun}"
    else:
        oya = next((g for g in chou().gyou if g["id"] == o.get("oya")), {})
        dai, michi = f"↩ 返信：{oya.get('dai', '')}", "#ita/" + str(o.get("oya", ""))
        bun = f"{o['na']}：{bun}"
    nakami = {"dai": dai[:80], "bun": bun, "michi": michi, "id": o["id"]}
    d = tsuuchi_yomu()
    kesu_ep = []
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as ses:
            for who, l in d.items():
                if who == o.get("dare") or not isinstance(l, list):
                    continue
                for sb in l:
                    moto = str(sb.get("moto", ""))
                    sub = moto if moto.startswith("https://") else "mailto:kyouryoku@kai.invalid"
                    try:
                        st = await webpush.okuru(ses, sb, nakami, sub)
                    except Exception as e:
                        st = 0
                        print("[kyouryoku] 知らせを送れませんでした:", type(e).__name__, flush=True)
                    if st in (404, 410):
                        kesu_ep.append(sb.get("endpoint"))
                    elif st and st >= 300:
                        print("[kyouryoku] 知らせの答え:", st, flush=True)
    except Exception as e:
        print("[kyouryoku] 知らせの道でつまずきました:", type(e).__name__, flush=True)
    if kesu_ep:  # もう居ない端末は登録から外す
        with TSUUCHI_LOCK:
            d = tsuuchi_yomu()
            for who in list(d):
                d[who] = [x for x in d[who] if x.get("endpoint") not in kesu_ep]
            tsuuchi_kaku(d)


SW_JS = r"""// 協力者の広場の知らせ（Web Push）を受けて出す係
self.addEventListener("install", function(e){ self.skipWaiting(); });
self.addEventListener("activate", function(e){ e.waitUntil(self.clients.claim()); });
self.addEventListener("push", function(e){
  var d = {}; try{ d = e.data ? e.data.json() : {}; }catch(x){}
  var url = new URL("./" + (d.michi || ""), self.registration.scope).href;
  e.waitUntil(self.registration.showNotification(d.dai || "KAI 協力者の広場", {
    body: d.bun || "新しい書き込みがあります", icon: "./icon-192.png", badge: "./badge-96.png",
    tag: d.id || undefined, data: {url: url, michi: d.michi || ""}
  }));
});
self.addEventListener("notificationclick", function(e){
  e.notification.close();
  var dd = e.notification.data || {}, url = dd.url || self.registration.scope;
  e.waitUntil(self.clients.matchAll({type: "window", includeUncontrolled: true}).then(function(cs){
    for(var i = 0; i < cs.length; i++){
      var c = cs[i];
      if(c.url.split("#")[0] === url.split("#")[0] && "focus" in c){ c.postMessage({michi: dd.michi}); return c.focus(); }
    }
    return self.clients.openWindow(url);
  }));
});
"""


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
        """入ってよい人なら who（shachou／kamei／iwata／katsuyama／…）。ダメなら None。"""
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
                                                "connect-src 'self'; img-src 'self' data: blob:; manifest-src 'self'; worker-src 'self'; "
                                                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
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

    def hito_no(req, who, tan) -> str:
        return who + "|" + str(tan or "")[:40] + "|" + (req.headers.get("X-Forwarded-For") or req.remote or "")

    async def kaku(req):
        who = dare(req)
        if not who:
            return nai()
        if req.headers.get("X-KAI") != "1":  # よそのページから押させない（この印はよそからは付けられない）
            return jres({"ok": False, "naze": "印がありません"}, 403)
        shu = req.match_info["shu"]
        if shu == "fairu":
            return await fairu_ire(req, who)
        try:
            x = await req.json()
        except Exception:
            return jres({"ok": False, "naze": "形が違います"}, 400)
        if shu in ("tsuuchi_ire", "tsuuchi_tomeru"):
            return tsuuchi_te(req, who, shu, x)
        hito = hito_no(req, who, x.get("tanmatsu"))
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
            else:
                mae = c.kieta()
            c.tasu(o)
            if shu == "kesu":
                fairu_sutete(c, c.kieta() - mae)  # 付いていた写真・ファイルも消す
            return jres({"ok": True, "v": c.v})
        if shu not in ("chat", "sure", "hen"):
            return nai()
        na = namae(who)  # 名前は入ったアドレスの鍵で決まる（送られて来た名前は使わない）
        bun = kirei(x.get("bun"), NAGASA["bun"])
        tsuke = []
        fl = x.get("fairu") or []
        if fl:
            if not kinou()["fairu"] or not isinstance(fl, list) or len(fl) > FAIRU_KAZU:
                return jres({"ok": False, "naze": f"写真・ファイルは1回に{FAIRU_KAZU}つまでです"}, 400)
            tsuita = c.fairu_moto()
            for fid in fl:
                m = fairu_meta(str(fid))
                if not m or m.get("dare") != who or fid in tsuita or any(t["id"] == fid for t in tsuke):
                    return jres({"ok": False, "naze": "写真・ファイルが見つかりません。付け直してください"}, 400)
                tsuke.append({"id": fid, "na": m["na"], "ookisa": m["ookisa"], "gazou": bool(m.get("gazou"))})
        if not bun and not tsuke:
            return jres({"ok": False, "naze": "中身を入れてください"}, 400)
        if not renda_ok(hito):
            return jres({"ok": False, "naze": "続けて書きすぎです。少し待ってください"}, 429)
        o = {"shu": shu, "na": na, "bun": bun, "dare": who}
        if tsuke:
            o["fairu"] = tsuke
        if shu == "sure":
            dai = kirei(x.get("dai"), NAGASA["dai"]).replace("\n", " ")
            if not dai:
                return jres({"ok": False, "naze": "題を入れてください"}, 400)
            o["dai"] = dai
        if shu == "hen":
            oya = str(x.get("oya", ""))
            if oya in c.kieta() or not any(g["id"] == oya and g.get("shu") == "sure" for g in c.gyou):
                return jres({"ok": False, "naze": "その投稿はもうありません"}, 404)
            o["oya"] = oya
        g = c.tasu(o)
        asyncio.get_running_loop().create_task(shiraseru(g))
        return jres({"ok": True, "id": g["id"], "v": c.v})

    async def fairu_ire(req, who):
        """写真・ファイルを受け取って置く（書き込みに付けるのはこの後）。中身はそのまま流し込む。"""
        if not kinou()["fairu"]:
            return nai()
        if not renda_ok(hito_no(req, "f:" + who, req.headers.get("X-Tan"))):
            return jres({"ok": False, "naze": "続けて送りすぎです。少し待ってください"}, 429)
        try:
            n = int(req.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n > FAIRU_MAX:
            return jres({"ok": False, "naze": "大きすぎます（1つ20MBまで）"}, 413)
        from urllib.parse import unquote
        na = fairu_na(unquote(req.headers.get("X-Na", "")))
        d = fairu_d()
        d.mkdir(parents=True, exist_ok=True)
        fid = secrets.token_hex(12)
        tmp = d / (fid + ".ire")
        ookisa = 0
        atama = b""
        try:
            with tmp.open("wb") as f:
                async for kire in req.content.iter_chunked(65536):
                    ookisa += len(kire)
                    if ookisa > FAIRU_MAX:
                        raise OverflowError
                    if len(atama) < 16:
                        atama += kire[:16 - len(atama)]
                    f.write(kire)
        except OverflowError:
            tmp.unlink(missing_ok=True)
            return jres({"ok": False, "naze": "大きすぎます（1つ20MBまで）"}, 413)
        except Exception:
            tmp.unlink(missing_ok=True)
            return jres({"ok": False, "naze": "途中で切れました。もう一度送ってください"}, 400)
        if ookisa == 0:
            tmp.unlink(missing_ok=True)
            return jres({"ok": False, "naze": "中身が空です"}, 400)
        mime, gazou = nakami_shu(atama)
        meta = {"na": na, "ookisa": ookisa, "mime": mime, "gazou": gazou, "dare": who, "t": ima()}
        (d / (fid + ".json")).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, d / fid)
        return jres({"ok": True, "id": fid, "na": na, "ookisa": ookisa, "gazou": gazou})

    async def fairu_dasu(req):
        who = dare(req)
        if not who or not kinou()["fairu"]:
            return nai()
        fid = req.match_info.get("fid", "")
        m = fairu_meta(fid)
        if not m:
            return nai()
        c = chou()
        moto = c.fairu_moto().get(fid)
        if moto is None:
            if m.get("dare") != who:  # 付ける前の物は、送った本人だけ
                return nai()
        elif moto in c.kieta():
            return nai()
        from urllib.parse import quote
        r = web.FileResponse(fairu_d() / fid)
        mime = m.get("mime", "application/octet-stream")
        mise = m.get("gazou") or mime == "application/pdf"
        r.content_type = mime
        r.headers["Content-Disposition"] = ("inline" if mise else "attachment") + "; filename*=UTF-8''" + quote(m.get("na", "fairu"))
        r.headers["Cache-Control"] = "private, max-age=604800"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["X-Robots-Tag"] = "noindex, nofollow"
        r.headers["X-Content-Type-Options"] = "nosniff"
        if m.get("gazou"):
            r.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"
        return r

    def tsuuchi_te(req, who, shu, x):
        if not kinou()["tsuuchi"]:
            return nai()
        if shu == "tsuuchi_tomeru":
            ep = str(x.get("endpoint", ""))
            with TSUUCHI_LOCK:
                d = tsuuchi_yomu()
                d[who] = [s for s in d.get(who, []) if s.get("endpoint") != ep]
                if not d[who]:
                    d.pop(who)
                tsuuchi_kaku(d)
            return jres({"ok": True})
        sb = x.get("sub") or {}
        ep = str(sb.get("endpoint", ""))
        keys = sb.get("keys") or {}
        if not ep.startswith("https://") or len(ep) > 1000 or not keys.get("p256dh") or not keys.get("auth"):
            return jres({"ok": False, "naze": "端末の登録の形が違います"}, 400)
        moto = req.headers.get("Origin", "")
        if not re.fullmatch(r"https?://[A-Za-z0-9.:\[\]-]+", moto or ""):
            moto = ""
        s = {"endpoint": ep, "keys": {"p256dh": str(keys["p256dh"])[:200], "auth": str(keys["auth"])[:100]},
             "moto": moto, "t": ima(), "tanmatsu": str(x.get("tanmatsu", ""))[:40]}
        with TSUUCHI_LOCK:
            d = tsuuchi_yomu()
            l = [z for z in d.get(who, []) if z.get("endpoint") != ep]
            l.append(s)
            d[who] = l[-10:]  # 1人10台まで
            tsuuchi_kaku(d)
        return jres({"ok": True})

    async def tsuuchi_kagi(req):
        if not dare(req) or not kinou()["tsuuchi"]:
            return nai()
        import webpush
        return jres({"kagi": webpush.koukai_kagi()})

    async def sw(req):
        if not dare(req) or not kinou()["tsuuchi"]:
            return nai()
        r = web.Response(text=SW_JS, content_type="text/javascript")
        return kabuse(r)

    async def manifest(req):
        if not dare(req):
            return nai()
        o = {"name": "KAI 協力者の広場", "short_name": "KAI広場", "id": "./", "start_url": "./", "scope": "./",
             "display": "standalone", "background_color": "#f6f4ef", "theme_color": "#1f6f5c", "lang": "ja",
             "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                       {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
                       {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
        r = web.Response(text=json.dumps(o, ensure_ascii=False), content_type="application/manifest+json")
        return kabuse(r)

    async def ezu(req):
        if not dare(req):
            return nai()
        nm = {"icon-192.png": "kyouryoku_icon192.png", "icon-512.png": "kyouryoku_icon512.png",
              "apple-touch-icon.png": "kyouryoku_icon180.png", "badge-96.png": "kyouryoku_badge96.png"}.get(req.match_info["e"])
        if not nm or not (HERE / nm).is_file():
            return nai()
        r = web.Response(body=(HERE / nm).read_bytes(), content_type="image/png")
        r.headers["Cache-Control"] = "private, max-age=86400"
        return r

    r = app.router
    # 頭の言葉は決まった字で書く（頭を「{m}」の形にすると、門番の振り分けが亀井ページの「その他は404」（/kamei/{k}/{tail}）を先に当ててしまう）
    for atama in ("/kamei/{k}/kyouryoku", "/kyaku/{k}/kyouryoku"):
        r.add_get(atama, page)
        r.add_get(atama + "/", page)
        r.add_get(atama + "/api/yomu", yomu)
        r.add_get(atama + "/api/tsuuchi_kagi", tsuuchi_kagi)
        r.add_post(atama + "/api/{shu}", kaku)
        r.add_get(atama + "/fairu/{fid}/{na}", fairu_dasu)
        r.add_get(atama + "/sw.js", sw)
        r.add_get(atama + "/kyouryoku.webmanifest", manifest)
        r.add_get(atama + "/{e:(icon-192|icon-512|apple-touch-icon|badge-96)\\.png}", ezu)
