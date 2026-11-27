"""KAI社員ページの門番（mon）：社員ページから入った人だけを、このPCで動くソフトへ通す。
あわせて「開発に参加したい」の受け付けと、届いた更新（GitHub のプルリクエスト＝仮の更新）の一覧を受け持つ。
社長の決め（採用／見送り・招待・亀井さんたちの案）は、みんなの画面には出さず、このPCだけの管理画面（kanri.py）で行う
（127.0.0.1:KANRI_PORT＝8807 だけで聞く別の口。トンネル・公開の置き場には載せない。通達 T1795712323 2026-11-27）。

使い方: pythonw -I -X utf8 mon.py <内緒の場所>      （窓を出さない。ログは <内緒の場所>/mon.log）
  内緒の場所に置く物: settei.json（kaihatsu＝載せるソフトの表）・secret/mon.json（shain／shachou／cookie の鍵）
外からの道: Tailscale Funnel 8443 → 127.0.0.1:8802（同時通訳が 443 を使っているので別の口）。
罠メモ: gh は read:org の無い鍵しか無い → `gh auth login` は通らない。GH_TOKEN に git の保存済みの鍵を入れて動かす。
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, WSMsgType, web

NAISHO = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\cl\kai_shain_private")
PORT = int(os.environ.get("KAI_MON_PORT", "8802"))
KANRI_PORT = int(os.environ.get("KAI_KANRI_PORT", "8807"))  # 管理画面の口（127.0.0.1 だけ）
GH = os.environ.get("KAI_GH", r"C:\Users\hiroy\tools\gh\bin\gh.exe")  # 試験の時だけ作り物の gh に替える
OWNER = "madbrolabs"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
JST = dt.timezone(dt.timedelta(hours=9))
YURUSU = {"https://madbrolabs.github.io", "http://localhost:8801", "http://127.0.0.1:8801"}
TAMESHI_DIR = NAISHO / "tameshi"
SANKA_DIR = NAISHO / "sanka"
JOUTAI = NAISHO / "mon_joutai.json"


def log(s: str) -> None:
    with open(NAISHO / "mon.log", "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now(JST):%Y-%m-%d %H:%M:%S} {s}\n")


def ima() -> str:
    return dt.datetime.now(JST).isoformat(timespec="minutes")


def kagi() -> dict:
    return json.loads((NAISHO / "secret" / "mon.json").read_text(encoding="utf-8"))


def kaihatsu() -> list[dict]:
    st = json.loads((NAISHO / "settei.json").read_text(encoding="utf-8"))
    return [dict(s["kaihatsu"], id=s["id"], namae=s["namae"]) for s in st["soft"] if s.get("kaihatsu")] \
        + list(st.get("kaihatsu_hoka", []))


def onaji(a: str, b: str) -> bool:
    return bool(a) and bool(b) and hmac.compare_digest(a.encode(), b.encode())


def dare(k: str) -> str | None:
    """鍵から、社長か社員かを見分ける。違えば None。"""
    K = kagi()
    if onaji(k, K["shachou"]):
        return "shachou"
    if onaji(k, K["shain"]):
        return "shain"
    return None


def rj(p: Path, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return d


def wj(p: Path, o) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix(p.suffix + ".tmp")
    t.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    t.replace(p)


# ---------- GitHub（gh）----------
_TOKEN: str | None = None


def gh_env() -> dict:
    global _TOKEN
    if not _TOKEN:
        r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                           capture_output=True, text=True, creationflags=NO_WINDOW, timeout=30)
        _TOKEN = next((l.split("=", 1)[1] for l in r.stdout.splitlines() if l.startswith("password=")), "")
    return dict(os.environ, GH_TOKEN=_TOKEN, GH_PROMPT_DISABLED="1", NO_COLOR="1")


def gh(*args: str, timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run([GH, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=gh_env(), creationflags=NO_WINDOW, timeout=timeout)


def oshiraseru(text: str) -> None:
    """社長へ：お屋敷に文字で知らせる（夜でも残る。声で起こすかはお屋敷の決まりに任せる）。"""
    if os.environ.get("KAI_MON_SHIKEN") == "1":  # 試験の時は知らせず、ログにだけ残す
        log(f"（試験）知らせ：{text}")
        return
    try:
        sys.path.insert(0, r"C:\cl\meido_cho")
        from meido_cho import kobo
        kobo("/api/msg", {"title": "KAI社員ページより", "text": text})
    except Exception as e:
        log(f"お屋敷へ知らせられませんでした {e!r}")
    try:  # 係長への報告帳にも残す（係長が各主任へ渡す）
        subprocess.run([sys.executable.replace("pythonw", "python"), "-I", "-X", "utf8",
                        r"C:\Users\hiroy\.claude\skills\shunin\tsuutatsu.py", "houkoku", "KAI社員ページの門番", text],
                       capture_output=True, timeout=30, creationflags=NO_WINDOW)
    except Exception as e:
        log(f"報告帳に書けませんでした {e!r}")


JOUTAI_NA = {"OPEN": "kari", "MERGED": "saiyou", "CLOSED": "miokuri"}
TODOITA_DIR = NAISHO / "todoita"
TODOITA_KETTEI = TODOITA_DIR / "_kettei.json"
MITTSU = {"中身": "naiyou", "良い所": "yoi", "よい所": "yoi", "危ない所": "abunai"}


def mittsu(body: str) -> dict:
    """主任の PR の本文3行『中身：／良い所：／危ない所：』を読む。無い行は空。"""
    o = {"naiyou": "", "yoi": "", "abunai": ""}
    for l in body.splitlines():
        l = l.strip().lstrip("-*・ ").strip()
        for k, v in MITTSU.items():
            if l.startswith(k) and l[len(k):len(k) + 1] in ("：", ":"):
                o[v] = kirei(l[len(k) + 1:], 200)
    return o


def todoita() -> list[dict]:
    """GitHub に倉庫が無い案件の口：todoita/<案件>.jsonl の1行1件
    {"at","shunin","daimei","naiyou","yoi","abunai","sumi":true|false}。社長の決め（相談の物）は _kettei.json に残す。"""
    na = {}
    for s in kaihatsu():
        for kk in (s["id"], s.get("todoita"), s["namae"]):
            if kk:
                na[kk] = s["namae"]
    kt = rj(TODOITA_KETTEI, {})
    out = []
    for fp in sorted(TODOITA_DIR.glob("*.jsonl")):
        for i, l in enumerate(fp.read_text(encoding="utf-8-sig").splitlines()):
            try:
                x = json.loads(l)
            except Exception:
                continue
            if not isinstance(x, dict) or not x.get("daimei"):
                continue
            tid = f"todoita:{fp.stem}#{i + 1}"
            k = kt.get(tid) or {}
            out.append({"id": tid, "anken": fp.stem,
                        "namae": na.get(fp.stem) or str(x.get("shunin") or fp.stem).replace("【主任】", ""),
                        "shunin": kirei(x.get("shunin"), 40), "daimei": kirei(x["daimei"], 120),
                        "naiyou": kirei(x.get("naiyou"), 300), "yoi": kirei(x.get("yoi"), 200),
                        "abunai": kirei(x.get("abunai"), 200), "sumi": bool(x.get("sumi")),
                        "hi": str(x.get("at", ""))[:16].replace("T", " "),
                        "kettei": k.get("kettei", ""), "kettei_hi": k.get("hi", "")})
    return out


def atsumeru() -> dict:
    """各ソフトの仮の更新（プルリクエスト）を集める。"""
    mae = rj(JOUTAI, {})
    mita = set(mae.get("mita", []))
    out = {"tsukutta": ima(), "soft": [], "mita": sorted(mita)}
    atarashii = []
    for s in kaihatsu():
        repo = s.get("repo")
        prs = []
        if repo:
            r = gh("pr", "list", "--repo", f"{OWNER}/{repo}", "--state", "all", "--limit", "100", "--json",
                   "number,title,body,author,state,createdAt,mergedAt,closedAt,url,labels,headRefName")
            if r.returncode:
                log(f"{repo} の一覧を読めませんでした: {r.stderr[-200:]}")
                prs = next((x["prs"] for x in mae.get("soft", []) if x["id"] == s["id"]), [])
            else:
                for p in json.loads(r.stdout or "[]"):
                    labels = [l["name"] for l in p.get("labels", [])]
                    body = (p.get("body") or "").strip()
                    prs.append({
                        "n": p["number"], "daimei": p["title"], "setsumei": body[:400],
                        "dare": (p.get("author") or {}).get("login", ""),
                        "joutai": JOUTAI_NA.get(p["state"], "kari"),
                        "hi": dt.datetime.fromisoformat((p.get("mergedAt") or p.get("closedAt") or p["createdAt"]).replace("Z", "+00:00")).astimezone(JST).strftime("%Y-%m-%d %H:%M"),
                        "kenpin": "主任の検品済み" in labels, "url": p["url"],
                        "soudan": "社長に相談" in labels, "ireta": "主任が入れた" in labels,
                        **mittsu(body),
                    })
                    kid = f'{repo}#{p["number"]}'
                    if kid not in mita:
                        mita.add(kid)
                        if p["state"] == "OPEN" and mae:  # 初回の読み込みでは鳴らさない
                            atarashii.append(f'{s["namae"]}：{p["title"]}（{(p.get("author") or {}).get("login", "")}）')
        out["soft"].append({"id": s["id"], "namae": s["namae"], "repo": repo or "", "prs": prs,
                            "tameshi": s.get("tameshi", "")})
    out["todoita"] = todoita()
    for x in out["todoita"]:
        if x["id"] not in mita:
            mita.add(x["id"])
            if not x["sumi"] and not x.get("kettei") and mae:
                atarashii.append(f'{x["namae"]}の主任から相談：{x["daimei"]}')
    out["mita"] = sorted(mita)
    wj(JOUTAI, out)
    if atarashii:
        oshiraseru("仮の更新が届きました。管理画面（デスクトップの近道「KAI 管理画面」）で、採用か見送りを決めてください。\n" + "\n".join(atarashii))
    return out


async def atsume_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(atsumeru)
        except Exception as e:
            log(f"集める係でつまずき {e!r}")
        await asyncio.sleep(180)


# ---------- 試す（PR ごとの試しの部屋）----------
TAMESHI: dict[str, dict] = {}  # "soft#n" → {port, proc, saigo}


def mirror(s: dict) -> Path:
    m = TAMESHI_DIR / "_kagami" / (s["repo"] + ".git")
    if not m.exists():
        m.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--bare", f"https://github.com/{OWNER}/{s['repo']}.git", str(m)],
                       capture_output=True, creationflags=NO_WINDOW, timeout=600)
    subprocess.run(["git", "--git-dir", str(m), "fetch", "-q", "origin", "+refs/pull/*/head:refs/pull/*/head",
                    "+refs/heads/*:refs/heads/*"], capture_output=True, creationflags=NO_WINDOW, timeout=600)
    return m


def aki_port() -> int:
    tsukau = {v["port"] for v in TAMESHI.values()}
    for p in range(8810, 8840):
        if p not in tsukau:
            return p
    raise RuntimeError("試しの部屋がいっぱいです")


def tameshi_dir(s: dict, n: int) -> Path:
    return TAMESHI_DIR / (f'{s["id"]}_pr{n}' if n else f'{s["id"]}_hon')


def hajime(s: dict, n: int) -> str:
    """入る所。{token} はその試しの部屋の合言葉ファイル（hajime_file）の中身に置き換える。"""
    h = s.get("hajime", "/")
    if "{token}" in h:
        f = Path(s.get("hajime_file", "").replace("{dir}", str(tameshi_dir(s, n))))
        for _ in range(30):
            if f.exists() and f.read_text(encoding="utf-8").strip():
                return h.replace("{token}", f.read_text(encoding="utf-8").strip())
            time.sleep(1)
        return "/"
    return h


def tameshi_okosu(s: dict, n: int) -> int:
    """PR #n（0＝いちばん新しい本流）の中身をこのPCで別の番号に起こす（30分さわらなければ止める）。"""
    key = f'{s["id"]}#{n}'
    t = TAMESHI.get(key)
    if t and t["proc"].poll() is None:
        t["saigo"] = time.time()
        return t["port"]
    m = mirror(s)
    d = tameshi_dir(s, n)
    if d.exists():
        subprocess.run(["git", "--git-dir", str(m), "worktree", "remove", "--force", str(d)], capture_output=True, creationflags=NO_WINDOW)
    subprocess.run(["git", "--git-dir", str(m), "worktree", "prune"], capture_output=True, creationflags=NO_WINDOW)
    r = subprocess.run(["git", "--git-dir", str(m), "worktree", "add", "-f", "--detach", str(d), f"refs/pull/{n}/head" if n else "HEAD"],
                       capture_output=True, text=True, creationflags=NO_WINDOW, timeout=300)
    if r.returncode:
        raise RuntimeError("仮の更新を取り出せませんでした: " + r.stderr[-200:])
    port = aki_port()
    cmd = [c.replace("{port}", str(port)).replace("{dir}", str(d)) for c in s["kidou"]]
    env = dict(os.environ, **{k: v.replace("{port}", str(port)) for k, v in s.get("kidou_env", {}).items()}, NO_BROWSER="1")
    lf = open(d / "_tameshi.log", "a", encoding="utf-8")
    p = subprocess.Popen(cmd, cwd=d, env=env, stdout=lf, stderr=lf, creationflags=NO_WINDOW)
    TAMESHI[key] = {"port": port, "proc": p, "saigo": time.time()}
    log(f"試しの部屋を起こした {key} → {port}")
    return port


async def tameshi_soji() -> None:
    while True:
        await asyncio.sleep(120)
        for k, v in list(TAMESHI.items()):
            if time.time() - v["saigo"] > 1800 or v["proc"].poll() is not None:
                try:
                    v["proc"].kill()
                except Exception:
                    pass
                TAMESHI.pop(k, None)
                log(f"試しの部屋を止めた {k}")


async def matsu_port(port: int, sec: int = 60) -> bool:
    for _ in range(sec * 2):
        try:
            _, w = await asyncio.open_connection("127.0.0.1", port)
            w.close()
            return True
        except OSError:
            await asyncio.sleep(0.5)
    return False


# ---------- 門 ----------
def shirushi(soft: str, n: str) -> str:
    return hmac.new(kagi()["cookie"].encode(), f"{soft}|{n}".encode(), hashlib.sha256).hexdigest()


def cors(req: web.Request, res: web.StreamResponse) -> web.StreamResponse:
    o = req.headers.get("Origin", "")
    if o in YURUSU:
        res.headers["Access-Control-Allow-Origin"] = o
        res.headers["Access-Control-Allow-Headers"] = "Content-Type"
        res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        res.headers["Vary"] = "Origin"
    return res


def jres(req, o, status=200):
    return cors(req, web.json_response(o, status=status, dumps=lambda x: json.dumps(x, ensure_ascii=False)))


MON_HTML = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>KAI Lab 社員の入口</title><body style="font:16px/1.8 system-ui,sans-serif;max-width:460px;margin:15vh auto;padding:0 16px;color:#1d1f24">
<h1 style="font-size:20px">ここは KAI Lab 社員の入口です</h1><p>社員ページの「試す」ボタンから入ってください。</p>
<p><a href="https://madbrolabs.github.io/kai-shain/shain/">社員ページへ</a></p></body>"""


async def t_iriguchi(req: web.Request) -> web.StreamResponse:
    """/t/<soft>?k=鍵[&n=PR番号] → 印を渡して、そのソフトへ。"""
    soft, k, n = req.match_info["soft"], req.query.get("k", ""), req.query.get("n", "")
    s = next((x for x in kaihatsu() if x["id"] == soft), None)
    if not dare(k) or not s or s.get("tameshi") != "pc" or (n and not n.isdigit()):
        return web.Response(text=MON_HTML, content_type="text/html", status=403)
    if n or not s.get("port"):
        try:
            port = await asyncio.to_thread(tameshi_okosu, s, int(n or 0))
        except Exception as e:
            return web.Response(text=f"試しの部屋を用意できませんでした：{e}", status=500)
        if not await matsu_port(port):
            return web.Response(text="試しの部屋が起きませんでした。少し待ってもう一度どうぞ。", status=503)
    res = web.HTTPFound(await asyncio.to_thread(hajime, s, int(n or 0)))
    for c, v in (("kai_soft", soft), ("kai_n", n), ("kai_mon", shirushi(soft, n))):
        res.set_cookie(c, v, max_age=12 * 3600, secure=True, httponly=True, samesite="Lax", path="/")
    return res


HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade", "host", "content-length", "content-encoding"}


async def chuukei(req: web.Request) -> web.StreamResponse:
    """印がある人だけ、ソフト（または PR の試しの部屋）へ中継する。"""
    soft, n, m = req.cookies.get("kai_soft", ""), req.cookies.get("kai_n", ""), req.cookies.get("kai_mon", "")
    if not soft or not onaji(m, shirushi(soft, n)):
        return web.Response(text=MON_HTML, content_type="text/html", status=403)
    s = next((x for x in kaihatsu() if x["id"] == soft), None)
    if not s:
        return web.Response(text=MON_HTML, content_type="text/html", status=403)
    if n or not s.get("port"):
        t = TAMESHI.get(f"{soft}#{n or 0}")
        if not t:
            return web.Response(text="試しの部屋は止まっています。社員ページの「試す」から入り直してください。", status=410)
        t["saigo"] = time.time()
        port = t["port"]
    else:
        port = s["port"]
    url = f"http://127.0.0.1:{port}{req.rel_url}"
    hdr = {k: v for k, v in req.headers.items() if k.lower() not in HOP and k.lower() != "cookie"}
    hdr["X-Forwarded-Proto"] = "https"
    hdr["X-Forwarded-Host"] = req.headers.get("Host", "")
    if req.headers.get("Upgrade", "").lower() == "websocket":
        ws = web.WebSocketResponse(max_msg_size=0)
        await ws.prepare(req)
        async with ClientSession() as cs:
            async with cs.ws_connect(url.replace("http", "ws", 1), headers={k: v for k, v in hdr.items() if not k.lower().startswith("sec-websocket")}, max_msg_size=0) as up:
                async def kara(a, b):
                    async for msg in a:
                        if msg.type == WSMsgType.TEXT:
                            await b.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await b.send_bytes(msg.data)
                        else:
                            break
                await asyncio.wait([asyncio.create_task(kara(ws, up)), asyncio.create_task(kara(up, ws))],
                                   return_when=asyncio.FIRST_COMPLETED)
        return ws
    body = await req.read()
    async with ClientSession(timeout=ClientTimeout(total=600), auto_decompress=False) as cs:
        async with cs.request(req.method, url, headers=hdr, data=body or None, allow_redirects=False) as up:
            res = web.StreamResponse(status=up.status)
            for k, v in up.headers.items():
                if k.lower() not in HOP or k.lower() == "content-encoding":
                    res.headers.add(k, v)
            await res.prepare(req)
            async for chunk in up.content.iter_chunked(65536):
                await res.write(chunk)
            await res.write_eof()
            return res


async def api_kousin(req: web.Request) -> web.StreamResponse:
    try:
        d = await req.json()
    except Exception:
        d = {}
    who = dare(d.get("k", ""))
    if not who:
        return jres(req, {"ok": False, "err": "kagi"}, 403)
    j = rj(JOUTAI, {"soft": []})
    # みんなの画面は一覧を見るだけ（社長の鍵でも同じ中身）。参加の希望の一覧と決めは管理画面だけ（通達 T1795712323）
    o = {"ok": True, "tsukutta": j.get("tsukutta", ""), "soft": j.get("soft", []), "todoita": j.get("todoita", [])}
    return jres(req, o)


def kirei(s, n):
    return " ".join(str(s or "").split())[:n]


async def api_sanka(req: web.Request) -> web.StreamResponse:
    try:
        d = await req.json()
    except Exception:
        return jres(req, {"ok": False, "err": "katachi"}, 400)
    if not dare(d.get("k", "")):
        return jres(req, {"ok": False, "err": "kagi"}, 403)
    x = {"id": dt.datetime.now(JST).strftime("%Y%m%d_%H%M%S_") + secrets.token_hex(2),
         "hi": ima(), "soft": kirei(d.get("soft"), 40), "namae": kirei(d.get("namae"), 40),
         "nani": kirei(d.get("nani"), 600), "ai": kirei(d.get("ai"), 80),
         "github": kirei(d.get("github"), 40).lstrip("@"), "renraku": kirei(d.get("renraku"), 120), "joutai": "machi"}
    if not x["namae"] or not x["nani"]:
        return jres(req, {"ok": False, "err": "tarinai"}, 400)
    wj(SANKA_DIR / f'{x["id"]}.json', x)
    namae = next((s["namae"] for s in kaihatsu() if s["id"] == x["soft"]), x["soft"])
    await asyncio.to_thread(oshiraseru, f'「開発に参加したい」が届きました：{x["namae"]}さん（{namae}・使うAI {x["ai"] or "未記入"}）\nやりたい事：{x["nani"]}\n管理画面（デスクトップの近道「KAI 管理画面」）で、招待するか決めてください。')
    log(f'参加の希望 {x["id"]} {x["soft"]}')
    return jres(req, {"ok": True})


def sanka_ichiran() -> list[dict]:
    """参加の希望（新しい順）。管理画面だけが読む。"""
    return sorted((rj(p, {}) for p in SANKA_DIR.glob("*.json")), key=lambda x: x.get("hi", ""), reverse=True)


async def kettei_suru(d: dict) -> tuple[dict, int]:
    """採用／見送り・招待（中身は前のまま）。呼ぶのは管理画面（kanri.py・127.0.0.1 の口）だけ。外の道には出さない。"""
    kettei = d.get("kettei")
    if kettei not in ("saiyou", "miokuri"):
        return {"ok": False, "err": "katachi"}, 400
    if d.get("shurui") == "sanka":
        p = SANKA_DIR / f'{Path(str(d.get("id", ""))).name}.json'
        x = rj(p, None)
        if not x:
            return {"ok": False, "err": "nai"}, 404
        if kettei == "saiyou":
            if not x.get("github"):
                return {"ok": False, "err": "GitHub の名前が書かれていないので、招待を送れません"}, 400
            repos = [s["repo"] for s in kaihatsu() if s.get("repo") and (s["id"] == x["soft"] or s.get("renshuu"))]
            dame = []
            for r in repos:
                g = await asyncio.to_thread(gh, "api", "-X", "PUT", f"repos/{OWNER}/{r}/collaborators/{x['github']}", "-f", "permission=push")
                if g.returncode:
                    dame.append(f"{r}: {g.stderr.strip()[-120:]}")
            if dame:
                return {"ok": False, "err": "招待を送れませんでした：" + " / ".join(dame)}, 500
            x["joutai"], x["kettei_hi"], x["repos"] = "shoutai", ima(), repos
        else:
            x["joutai"], x["kettei_hi"] = "miokuri", ima()
        wj(p, x)
        log(f'参加 {x["id"]} → {x["joutai"]}')
        return {"ok": True, "joutai": x["joutai"]}, 200
    if d.get("shurui") == "todoita":  # 倉庫の無い案件の相談：決めを残し、その主任へ知らせる
        tid = str(d.get("id", ""))
        x = next((t for t in todoita() if t["id"] == tid and not t["sumi"]), None)
        if not x:
            return {"ok": False, "err": "nai"}, 404
        kt = rj(TODOITA_KETTEI, {})
        kt[tid] = {"kettei": kettei, "hi": ima()}
        wj(TODOITA_KETTEI, kt)
        log(f"{tid} → {kettei}")
        await asyncio.to_thread(oshiraseru, f'社長が{"採用" if kettei == "saiyou" else "見送り"}にしました：{x["namae"]}の相談「{x["daimei"]}」。' + (f'{x["namae"]}の主任は、入れてから todoita の行を "sumi": true にしてください。' if kettei == "saiyou" else "行はそのままで構いません。"))
        await asyncio.to_thread(atsumeru)
        return {"ok": True}, 200
    s = next((x for x in kaihatsu() if x["id"] == d.get("soft")), None)
    n = str(d.get("n", ""))
    if not s or not s.get("repo") or not n.isdigit():
        return {"ok": False, "err": "nai"}, 404
    R = f'{OWNER}/{s["repo"]}'
    if kettei == "saiyou":
        g = await asyncio.to_thread(gh, "pr", "merge", n, "--repo", R, "--merge")
    else:
        g = await asyncio.to_thread(gh, "pr", "close", n, "--repo", R, "--comment",
                                    "社長の判断で、今回は見送りになりました。出してくださって、ありがとうございました。")
    if g.returncode:
        return {"ok": False, "err": g.stderr.strip()[-200:]}, 500
    log(f"{R}#{n} → {kettei}")
    if kettei == "saiyou":
        await asyncio.to_thread(oshiraseru, f'社長が採用しました：{s["namae"]} の仮の更新 #{n}。GitHub の本線（{R}）に入りました。{s["namae"]}の主任は、作業場へ取り込んでください。')
    await asyncio.to_thread(atsumeru)
    return {"ok": True}, 200


PAGES = os.environ.get("KAI_PAGES", "https://madbrolabs.github.io/kai-shain")
PAGES_MAE = "/kai_mon/pages"


async def pages(req: web.Request) -> web.StreamResponse:
    """公開の置き場（GitHub Pages）の社員ページを、門番の住所でもそのまま見せる（中身は公開の物と同じ・毎回取りに行く）。
    わけ：このPC（Tailscale の内側）では門番の住所が内側の番地に引かれ、公開のページから門番を呼ぶと Chrome が
    「ローカルの相手」として止める（Local Network Access）。同じ住所のページからの呼び出しなら止められない。"""
    tail = req.match_info.get("tail", "")
    if any(p in ("..", ".") for p in tail.split("/")) or "\\" in tail:
        return web.Response(status=404, text="404 Not Found")
    try:
        async with ClientSession(timeout=ClientTimeout(total=40)) as cs:
            async with cs.get(f"{PAGES}/{tail}", params=req.rel_url.query, allow_redirects=False,
                              headers={"Accept-Encoding": "identity"}) as r:
                if r.status in (301, 302, 307, 308):
                    to = r.headers.get("Location", "")
                    michi = "/" + PAGES.split("://", 1)[-1].partition("/")[2]  # 例 /kai-shain
                    for mae in (PAGES, michi):  # 置き場の外へ飛ばす答えは通さない
                        if to == mae or to.startswith(mae + "/"):
                            return web.HTTPFound(PAGES_MAE + to[len(mae):])
                    return web.Response(status=404, text="404 Not Found")
                body = await r.read()
                res = web.Response(body=body, status=r.status)
                res.headers["Content-Type"] = r.headers.get("Content-Type", "application/octet-stream")
                res.headers["Cache-Control"] = "no-cache"
                res.headers["X-Content-Type-Options"] = "nosniff"
                return res
    except Exception as e:
        log(f"公開の置き場を取りに行けませんでした {tail} {e!r}")
        return web.Response(status=502, text="公開の置き場を読めませんでした。少しして、もう一度どうぞ。")


async def pages_mae(req):
    return web.HTTPFound(PAGES_MAE + "/")


async def kanri_dake(req):
    return jres(req, {"ok": False, "err": "kanri_gamen_dake"}, 403)


async def preflight(req):
    return cors(req, web.Response(status=204))


async def genki(req):
    return jres(req, {"ok": True, "toki": ima()})


def main() -> None:
    app = web.Application(client_max_size=50 * 1024 * 1024)
    app.router.add_get("/kai_mon/genki", genki)
    app.router.add_get("/t/{soft}", t_iriguchi)
    app.router.add_post("/kai_mon/kousin", api_kousin)
    app.router.add_post("/kai_mon/sanka", api_sanka)
    app.router.add_route("*", "/kai_mon/kettei", kanri_dake)  # 決めの口は外の道では断る（管理画面だけ・通達 T1795712323）
    app.router.add_route("*", "/kai_mon/kanri{x:.*}", kanri_dake)
    app.router.add_get(PAGES_MAE, pages_mae)  # 社員ページの写し（このPCの Chrome 用・中身は公開の置き場のまま）
    app.router.add_get(PAGES_MAE + "/{tail:.*}", pages)
    app.router.add_route("OPTIONS", "/kai_mon/{x}", preflight)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault("KAI_NAISHO", str(NAISHO))
    try:  # アドオン：はじめての人の入口（hajimete.py・入/切＝内緒の場所/hajimete.json）。亀井ページの「その他は404」より先に付ける
        import hajimete
        hajimete.tsukeru(app)
    except Exception as e:
        log(f"はじめての人の入口を付けられませんでした {e!r}")
    try:  # アドオン：会社紹介ページ（kaisha.py・中身＝内緒の場所/kaisha_shoukai・入/切＝内緒の場所/kaisha.json）。亀井ページより先に付ける
        import kaisha
        kaisha.tsukeru(app)
    except Exception as e:
        log(f"会社紹介ページを付けられませんでした {e!r}")
    try:  # アドオン：ご意見の札（goiken_fuda.py・L6・入/切＝内緒の場所/goiken_fuda.json）。社員ページ「届いた更新」の枠
        import goiken_fuda
        goiken_fuda.tsukeru(app, dare, jres)
    except Exception as e:
        log(f"ご意見の札を付けられませんでした {e!r}")
    try:  # アドオン：営業用資料の棚の社員だけの写し（eigyou.py・写し＝内緒の場所/eigyou・入/切＝内緒の場所/eigyou.json）。亀井ページより先に付ける
        import eigyou
        eigyou.tsukeru(app, dare, jres, cors)
    except Exception as e:
        log(f"営業用資料の口を付けられませんでした {e!r}")
    try:  # アドオン：録音君の案内（rokuon_annai.py・中身＝内緒の場所/rokuon_annai・入/切＝内緒の場所/rokuon_annai.json）。亀井ページより先に付ける
        import rokuon_annai
        rokuon_annai.tsukeru(app, dare)
    except Exception as e:
        log(f"録音君の案内を付けられませんでした {e!r}")
    try:  # アドオン：社内向けの資料（shanai.py・中身＝内緒の場所/shanai・決めた人の専用ページだけ）。亀井ページより先に付ける
        import shanai
        shanai.tsukeru(app)
    except Exception as e:
        log(f"社内向けの資料を付けられませんでした {e!r}")
    try:  # アドオン：協力者の広場（kyouryoku.py・チャットと掲示板・書き込み＝内緒の場所/kyouryoku/kaki.jsonl・入/切＝内緒の場所/kyouryoku.json）。亀井ページより先に付ける
        import kyouryoku
        kyouryoku.tsukeru(app)
    except Exception as e:
        log(f"協力者の広場を付けられませんでした {e!r}")
    try:  # アドオン：亀井ページ（kamei.py・設定 内緒の場所/kamei/settei.json の iri＝入/切）。無くても門番は動く
        import kamei
        kamei.tsukeru(app)
    except Exception as e:
        log(f"亀井ページを付けられませんでした {e!r}")
    app.router.add_route("*", "/{tail:.*}", chuukei)

    async def hajime(a):
        a["t1"] = asyncio.create_task(atsume_loop())
        a["t2"] = asyncio.create_task(tameshi_soji())
        try:  # 管理画面（kanri.py）：同じ門番の中で、別の口 127.0.0.1:KANRI_PORT だけで聞く。外の入口（トンネル）には載せない
            import kanri
            r = web.AppRunner(kanri.tsukuru(KANRI_PORT, log=log, kousin_yomu=lambda: rj(JOUTAI, {"soft": []}),
                                            sanka_yomu=sanka_ichiran, kettei_suru=kettei_suru, atsumeru=atsumeru))
            await r.setup()
            await web.TCPSite(r, "127.0.0.1", KANRI_PORT).start()
            a["kanri"] = r
            log(f"管理画面の口を開いた（127.0.0.1:{KANRI_PORT}）")
        except Exception as e:
            log(f"管理画面の口を開けませんでした {e!r}")
    app.on_startup.append(hajime)
    log(f"門番を起こした（{PORT}）")
    web.run_app(app, host="127.0.0.1", port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
