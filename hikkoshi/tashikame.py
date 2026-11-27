"""引っ越しの後（と前）に、社員ページの門番が外から正しく見えるかを確かめる（Python だけ・部品は要らない）。

使い方：
  python -I -X utf8 hikkoshi/tashikame.py https://shain.kailab.co.jp
  python -I -X utf8 hikkoshi/tashikame.py https://shain.kailab.co.jp --id iwata --shoki <内緒の場所>/secret/kai_id_shoki.json
    --id を付けた時だけ、その ID で入って箱を見て、ログアウトする（パスワードは中で読むだけ・画面に出さない）。
    初めのパスワードを替えた人の ID では入れない（その時は付けない）。
  --server ＝ 借りたサーバーの時だけ見る物（https の印 HSTS・管理画面の口 8807 が外から開かない）も見る。
書き込みはしない（広場・感想・参加したいには何も送らない＝本物の部屋や社長のスマホに知らせが飛ばない）。
ログインの間違いの試しは、無い ID で1回だけ（本物の ID を止めない）。
"""
from __future__ import annotations

import json
import secrets
import socket
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

args = sys.argv[1:]
if not args or args[0].startswith("-"):
    sys.exit(__doc__)
BASE = args[0].rstrip("/")
SERVER = "--server" in args
ID = args[args.index("--id") + 1] if "--id" in args else ""
SHOKI = args[args.index("--shoki") + 1] if "--shoki" in args else ""
kekka: list[tuple[str, bool]] = []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OP = urllib.request.build_opener(NoRedirect)


def ok(na: str, b) -> None:
    kekka.append((na, bool(b)))
    print(("OK  " if b else "NG  ") + na, flush=True)


def req(path: str, body=None, h=None, method=None):
    hh = {"User-Agent": "kai-tashikame/1"}
    if body is not None:
        hh["Content-Type"] = "application/json"
    hh.update(h or {})
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                               headers=hh, method=method)
    try:
        with OP.open(r, timeout=40) as f:
            return f.status, f.read(), f.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers
    except Exception as e:  # つながらない・証明書が違う など
        return 0, repr(e).encode(), {}


# 1 入口
s, b, hd = req("/kai/")
ok("入口 /kai/ は /kai/shain/ へ回す", s == 302 and (hd.get("Location") or "").endswith("/kai/shain/"))
s, b, hd = req("/kai/shain/")
ok("社員ページが ID の形で出る（https の証明書も正しい）", s == 200 and b"const IDMODE=true;" in b)
if SERVER:
    ok("https の印（HSTS）が付いている", "max-age" in (hd.get("Strict-Transport-Security") or ""))
s, b, _ = req("/kai/iriguchi/ichiran.json")
try:
    ok("テスト中のアプリの一覧が読める", s == 200 and any(x.get("tesuto") for x in json.loads(b)["soft"]))
except Exception:
    ok("テスト中のアプリの一覧が読める", False)

# 2 入る前は何も見せない・間違いは断る
s, _, _ = req("/kai/api/hako")
ok("入る前は箱を出さない（401）", s == 401)
s, b, _ = req("/kai/api/login", {"id": "tashikame_nai_" + secrets.token_hex(3), "pw": "x" * 12}, {"X-KAI": "1"})
ok("無い ID では入れない（401・ID かパスワードが違います）", s == 401 and "違います" in b.decode("utf-8", "replace"))
s, _, _ = req("/kai/api/login", {"id": "x", "pw": "x"})
ok("印（X-KAI）の無いログインは断る（403）", s == 403)
s, _, _ = req("/kai/kyouryoku/api/yomu")
ok("入る前は広場を読めない", s in (302, 401, 403, 404))
s, _, _ = req("/kamei/" + secrets.token_urlsafe(32) + "/")
ok("違う鍵の専用ページは 404", s == 404)

# 3 門番の口
s, b, _ = req("/kai_mon/genki")
ok("門番が起きている（/kai_mon/genki）", s == 200 and b'"ok": true' in b)
s, _, _ = req("/kai_mon/kettei", {})
ok("決めの口は外から断る（403）", s == 403)
s, _, _ = req("/kai/api/kai_id")
ok("ID の発行の口（管理画面だけの物）は外に無い", s in (403, 404, 405))
s, b, _ = req("/kai_mon/pages/shain/")
ok("門番の住所の社員ページ（公開の置き場の写し）が出る", s == 200 and b"IDMODE" in b)

# 4 管理画面の口が外から開かない
if SERVER:
    host = urlsplit(BASE).hostname or ""
    try:
        socket.create_connection((host, 8807), timeout=4).close()
        ok("管理画面の口 8807 が外から開かない", False)
    except OSError:
        ok("管理画面の口 8807 が外から開かない", True)

# 5 （望む時だけ）入って箱を見て、ログアウト
if ID:
    try:
        pw = json.load(open(SHOKI, encoding="utf-8"))["id"][ID]["pw"]
    except Exception:
        pw = ""
    ok(f"{ID} の初めのパスワードを読めた", bool(pw))
    if pw:
        s, b, hd = req("/kai/api/login", {"id": ID, "pw": pw}, {"X-KAI": "1"})
        sc = hd.get("Set-Cookie", "") if hd else ""
        ok(f"{ID} で入れる（札は HttpOnly・Secure・道 /kai）", s == 200 and all(x in sc for x in ("HttpOnly", "Secure", "Path=/kai")))
        if s == 200 and "kai_s=" in sc:
            H = {"X-KAI": "1", "Cookie": "kai_s=" + sc.split("kai_s=")[1].split(";")[0]}
            s, b, _ = req("/kai/api/hako", h=H)
            ok("箱が来る", s == 200 and len(b) > 1000)
            if json.loads(req("/kai/api/ore", h=H)[1] or b"{}").get("kubun") != "shachou":
                ok("社員の箱に「ハイロ」が無い", "ハイロ" not in b.decode("utf-8", "replace"))
            s, _, _ = req("/kai/kyouryoku/api/yomu", h=H)
            ok("同じ札で広場を読める", s == 200)
            req("/kai/api/logout", {}, H)
            s, _, _ = req("/kai/api/ore", h=H)
            ok("ログアウトで札が切れる", s == 401)

print("ぜんぶ OK" if kekka and all(x for _, x in kekka) else "NG あり")
sys.exit(0 if kekka and all(x for _, x in kekka) else 1)
