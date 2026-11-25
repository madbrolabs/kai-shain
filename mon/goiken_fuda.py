"""アドオン：ご意見の札（L6・2026-11-25 係長採用）。全ソフトのご意見の口に付いた札番号を、社員ページの「届いた更新」に並べる。

読む所＝超議事録の受け口の q=goiken_fuda（決3：ご意見の口の持ち主は超議事録）。つなぎ先と鍵は 内緒の場所/secret/goiken_fuda.json
  {"url": "<受け口>", "k": "<KAI社員ページ用の鍵>"} にだけ置く（倉庫・画面に出さない）。
5分おきに読み、写しを 内緒の場所/goiken_fuda/utsushi.json に置く。社員ページは POST /kai_mon/goiken_fuda（社員の鍵）で写しを読む。
返すのは 札番号（会社の通し番号 G-0001）・元の名前の短い形・ソフト・改善要望かバグか・一言の題・状態・日付・返事 だけ（声・写真・本文・送った人は受け取っても捨てる）。
入/切＝内緒の場所/goiken_fuda.json の iri（無ければ入）。切ると口は {"ok":true,"iri":false} を返し、枠は出ない。コア（mon.py）はこれが無くても動く。
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
from pathlib import Path

SOFT_NA = {"gijiroku": "超議事録", "tsuuyaku": "同時通訳", "enything": "縁ything", "kai_shain": "KAI社員ページ", "iriguchi": "入口アプリ"}
JOUTAI = ("uketsuke", "naoshichuu", "naotta", "miokuri")  # 受付・直し中・直った・見送り
MAI = 300  # 何秒おきに読むか


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def _rj(p: Path, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return d


def iri() -> bool:
    return _rj(naisho() / "goiken_fuda.json", {}).get("iri", True) is not False


def utsushi_p() -> Path:
    return naisho() / "goiken_fuda" / "utsushi.json"


def kirei(s, n: int) -> str:
    return " ".join(str(s or "").split())[:n]


def seiri(x) -> dict | None:
    """受け口から来た1件を、出してよい欄だけにそろえる。形が違う物は捨てる。"""
    if not isinstance(x, dict):
        return None
    ban = kirei(x.get("fudaban"), 20)
    if not re.fullmatch(r"[A-Za-z]{0,4}-?\d{1,8}", ban):
        return None
    soft = kirei(x.get("soft") or "gijiroku", 30)
    j = x.get("joutai") if x.get("joutai") in JOUTAI else "uketsuke"
    return {"fudaban": ban, "soft": soft, "soft_na": SOFT_NA.get(soft, soft),
            "shurui": "bug" if x.get("shurui") == "bug" or x.get("fuda") == "bug" else "goiken",
            "dai": kirei(x.get("dai"), 30), "joutai": j, "hi": kirei(x.get("hi"), 16),
            "naotta_hi": kirei(x.get("naotta_hi"), 16), "henji": kirei(x.get("henji"), 120),
            "moto": mijikaku(x.get("moto"))}


def mijikaku(moto) -> str:
    """元の名前 enything_20261125_162200_001 → 「enything 1125-1622」（主任の決め 2026-11-25）。形が違えば出さない。"""
    m = re.fullmatch(r"([A-Za-z0-9-]{1,40})_\d{4}(\d{4})_(\d{4})\d{2}_\d{3}(?:\.\w+)?", str(moto or ""))
    return f"{m.group(1)} {m.group(2)}-{m.group(3)}" if m else ""


def seiri_zenbu(o) -> list[dict]:
    if not isinstance(o, dict) or not o.get("ok"):
        raise ValueError("受け口の返事が ok ではありません")
    out, mita = [], set()
    for x in o.get("fuda") or []:
        y = seiri(x)
        if y and y["fudaban"] not in mita:
            mita.add(y["fudaban"])
            out.append(y)
    out.sort(key=lambda y: y["hi"], reverse=True)
    return out[:300]


def kaku(fuda: list[dict], err: str = "") -> None:
    p = utsushi_p()
    p.parent.mkdir(parents=True, exist_ok=True)
    mae = _rj(p, {})
    o = {"yonda": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "fuda": fuda if not err else mae.get("fuda", []), "err": err}
    t = p.with_suffix(".tmp")
    t.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(t, p)


async def yomu_ichido(sess) -> None:
    s = _rj(naisho() / "secret" / "goiken_fuda.json", {})
    url, k = s.get("url"), s.get("k")
    if not url or not k:
        return  # つなぎ先がまだ無い＝何もしない（枠は「まだ札はありません」）
    try:
        async with sess.get(url, params={"k": k, "q": "goiken_fuda"}, allow_redirects=True) as r:
            o = json.loads(await r.text())
        kaku(seiri_zenbu(o))
    except Exception as e:
        kaku([], err=f"{type(e).__name__}")  # 中身（鍵・アドレス）はログに出さない


def tsukeru(app, dare, jres) -> None:
    from aiohttp import ClientSession, ClientTimeout

    async def kuchi(req):
        try:
            d = await req.json()
        except Exception:
            d = {}
        if not dare(d.get("k", "")):
            return jres(req, {"ok": False, "err": "kagi"}, 403)
        if not iri():
            return jres(req, {"ok": True, "iri": False, "fuda": []})
        u = _rj(utsushi_p(), {})
        return jres(req, {"ok": True, "iri": True, "yonda": u.get("yonda", ""), "fuda": u.get("fuda", [])})

    async def loop():
        async with ClientSession(timeout=ClientTimeout(total=60)) as sess:
            while True:
                if iri():
                    await yomu_ichido(sess)
                await asyncio.sleep(MAI)

    async def hajime(a):
        a["goiken_fuda"] = asyncio.create_task(loop())

    app.router.add_post("/kai_mon/goiken_fuda", kuchi)
    app.on_startup.append(hajime)
