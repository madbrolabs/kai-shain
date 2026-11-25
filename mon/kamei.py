"""亀井ページ（門番 mon.py のアドオン）：係長相談室と各【主任】の部屋のやりとりを、亀井さんがスマホから見て、ちょこっと書き込める。

入口＝/kamei/<長い鍵>/（合言葉なし。鍵は 内緒の場所/secret/kamei.json の kamei・shachou。違えば 404）。
設定＝内緒の場所/kamei/settei.json（iri＝入/切、nozoku＝出さない部屋、renda＝連打よけ）。
書き込み＝内緒の場所/kamei/ukebako/<受付番号>.json に置き → 配達係（窓なしの claude -p を1回）が SendMessage でその部屋へ届ける。
  届いたかは、その部屋の会話の記録（jsonl）に受付番号が出たかで確かめる。届かない時は見張りフック kamei_mihari.py が次の一言で差し込む。
作った物の一覧＝内緒の場所/kamei/tsukutta.jsonl（部屋の AI が `python kamei.py tsuika …` で1行足す）。社長の入口で見て「入れて／見送り」。
罠メモ：部屋の記録は 30MB を超える＝読んだ所（pos）を覚えて足された分だけ読む。伏せはここで済ませてから外へ出す。
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import glob
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
JST = dt.timezone(dt.timedelta(hours=9))
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
MEIBO = Path(r"C:\Users\hiroy\Claude\主任名簿.json")
PROJECTS = Path.home() / ".claude" / "projects"
NAISHO = Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))
HAITATSU_NA = "亀井ページの配達係"
ATAMA = "【亀井さんから（社員ページ経由）】"
ATAMA_SHACHOU = "【社長の決め（亀井ページ経由）】"
KIMARI = ("――\n（この頼みの決まり）亀井さんの頼みは、そのまま進めてよい（考える・作る・試すまでやってよい）。"
          "ただし本番には入れない＝作った物は別の枝（kari/kamei-<短い名前> など試しの版）に置き、本番のシステム・指示書の【決】・設定はそのまま。"
          "GitHub の倉庫がある部屋は kari/ の枝でプルリクエストを出し、札「亀井さんの頼み」を付ける。"
          "済んだら『亀井さんの頼みで作った物』の一覧に1行足す（何を・どこに作ったか・試した結果）：\n"
          "{tsuika}\n"
          "亀井さんへの返事は『承りました。作って社長に見てもらいます』の形で、この部屋のチャットにそのまま書く（亀井さんの画面にそのまま出る。配達係へ返さなくてよい）。"
          "お金・法律に当たる物は今までどおり社長に確かめる。")
PY = r"C:\Users\hiroy\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe"


def ima() -> str:
    return dt.datetime.now(JST).isoformat(timespec="seconds")


def rj(p: Path, d):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return d


def wj(p: Path, o) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + f".{os.getpid()}.tmp")
    t.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    t.replace(p)


def D() -> Path:
    return NAISHO / "kamei"


def settei() -> dict:
    s = {"iri": "入", "nozoku": ["権利まもり", r"C:\cl\kenri_private"], "renda_kazu": 3, "renda_byou": 60,
         "nagasa": 1000, "machi_saidai": 5}
    s.update(rj(D() / "settei.json", {}))
    return s


def iri() -> bool:
    return settei().get("iri") == "入"


def kagi() -> dict:
    return rj(NAISHO / "secret" / "kamei.json", {})


def dare(k: str) -> str | None:
    K = kagi()
    for who in ("shachou", "kamei"):
        v = K.get(who, "")
        if len(v) >= 32 and k and hmac.compare_digest(k.encode(), v.encode()):
            return who
    return None


def log(s: str) -> None:
    try:
        D().mkdir(parents=True, exist_ok=True)
        with open(D() / "kamei.log", "a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now(JST):%Y-%m-%d %H:%M:%S} {s}\n")
    except Exception:
        pass


# ---------- 伏せる ----------
_HIMITSU: tuple[float, list[str]] = (0.0, [])


def himitsu_mojiretsu() -> list[str]:
    """内緒の場所の鍵・合言葉の中身そのもの（字そのままで消す）。1分覚える。"""
    global _HIMITSU
    if time.time() - _HIMITSU[0] < 60:
        return _HIMITSU[1]
    out: set[str] = set()

    def hirou(o):
        if isinstance(o, dict):
            for v in o.values():
                hirou(v)
        elif isinstance(o, list):
            for v in o:
                hirou(v)
        elif isinstance(o, str) and len(o) >= 6:
            out.add(o)
    for f in (NAISHO / "secret").glob("*.json"):
        hirou(rj(f, {}))
    _HIMITSU = (time.time(), sorted(out, key=len, reverse=True))
    return _HIMITSU[1]


FUSE = [
    re.compile(r"/kamei/[A-Za-z0-9_\-]{8,}"),                                   # 専用URLの鍵
    re.compile(r"(?i)\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),              # GitHub の鍵
    re.compile(r"(?i)\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), re.compile(r"\bxai-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"), re.compile(r"\bya29\.[0-9A-Za-z_\-]{20,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}"),  # JWT
    re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+"),                              # メール
    re.compile(r"(?<![\d\-])(?:\+81[\-\s]?|0)\d{1,4}[\-\s]?\d{1,4}[\-\s]?\d{3,4}(?![\d\-])"),  # 電話らしき
    re.compile(r"(?i)((?:password|passwd|pass|pw|token|secret|api[_\-]?key|apikey|合言葉|パスワード|暗証番号|トークン)\s*[:=：は]\s*[\"'「]?)([^\s\"'」、。,]{4,})"),
    re.compile(r"(?i)([?&](?:k|key|token|code|sig|kagi)=)[^&\s\"'<>]{6,}"),     # URL の鍵
    re.compile(r"\b[A-Fa-f0-9]{40,}\b"), re.compile(r"\b[A-Za-z0-9_\-]{43,}\b(?<![/\\])"),  # 長い乱数
]
DATE_LIKE = re.compile(r"^(?:\+81[\-\s]?|0)?\d{4}[\-\s]\d{1,2}[\-\s]\d{1,2}$")


YOBINA = re.compile(r"ハイロ(様|さん|さま)?")  # 会社のページでは「社長」（atsume.py と同じ決まり）


def fuseru(s: str) -> str:
    if not s:
        return ""
    s = YOBINA.sub("社長", s)
    for h in himitsu_mojiretsu():
        if h in s:
            s = s.replace(h, "●●●")
    for i, r in enumerate(FUSE):
        if i == 10 or i == 11:
            s = r.sub(lambda m: m.group(1) + "●●●", s)
        elif i == 9:
            s = r.sub(lambda m: m.group(0) if DATE_LIKE.match(m.group(0)) or re.match(r"^20\d\d", m.group(0)) else "●●●", s)
        elif i == 12 or i == 13:
            s = r.sub(lambda m: m.group(0) if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", m.group(0)) else "●●●", s)
        else:
            s = r.sub("●●●", s)
    return s


# ---------- 部屋 ----------
def heya_ichiran() -> list[dict]:
    """係長相談室＋【主任】の部屋全部（名簿から毎回作る＝増えれば増える）。nozoku に当たる部屋は出さない。"""
    m = rj(MEIBO, {})
    noz = [str(x) for x in settei().get("nozoku", [])]
    out = []
    kk = m.get("kakarichou") or {}
    if kk.get("session_id"):
        out.append({"id": kk["session_id"][:8], "sid": kk["session_id"], "dai": kk.get("dai") or "【係長】相談室",
                    "namae": "係長相談室", "basho": "", "kakari": True})
    for s in m.get("shunin", []):
        sid = s.get("session_id") or ""
        kan = [s.get("anken", ""), s.get("kyuu_mei", ""), s.get("dai", ""), s.get("basho", ""), sid]
        if not sid or any(n and any(n.lower() in str(k).lower() for k in kan if k) for n in noz):
            continue
        out.append({"id": sid[:8], "sid": sid, "dai": s.get("dai") or f'【主任】{s.get("anken", "")}',
                    "namae": s.get("anken", ""), "basho": s.get("basho", ""), "kakari": False})
    return out


def heya(hid: str) -> dict | None:
    return next((h for h in heya_ichiran() if h["id"] == hid), None)


def kiroku_basho(sid: str) -> Path | None:
    g = glob.glob(str(PROJECTS / "*" / f"{sid}.jsonl"))
    return Path(max(g, key=os.path.getmtime)) if g else None


# ---------- 会話の読み取り（足された分だけ）----------
SR = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
CSM = re.compile(r'<cross-session-message[^>]*?from-name="([^"]*)"[^>]*>(.*?)(?:</cross-session-message>|$)', re.S)
KYOU = {}  # sid → {"path","pos","items","n","links","rest"}
PUB = re.compile(r"https://madbrolabs\.github\.io/[^\s)\]」>\"'`]+")
SAGYOU_NA = {"Bash": "PCで作業", "PowerShell": "PCで作業", "Read": "資料を読む", "Grep": "資料を探す", "Glob": "資料を探す",
             "Write": "書く", "Edit": "書き直す", "Agent": "手下に頼む", "WebSearch": "調べる", "WebFetch": "ページを読む",
             "SendMessage": "ほかの部屋へ連絡", "Skill": "道具を用意", "Artifact": "ページを作る"}


def _ji(d: dict) -> str:
    t = d.get("timestamp") or ""
    try:
        return dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(JST).isoformat(timespec="seconds")
    except Exception:
        return ""


def _tasu(st: dict, item: dict) -> None:
    st["n"] += 1
    item["n"] = st["n"]
    st["items"].append(item)


def _hito_text(s: str) -> str | None:
    s = SR.sub("", s).strip()
    if not s or s.startswith("[Request interrupted") or re.match(r"^<[a-zA-Z][\w\-]*[ />]", s):
        return None
    if s.startswith("Caveat:") or s.startswith("This session is being continued"):
        return None
    return s


def _gyou(st: dict, d: dict) -> None:
    t = d.get("type")
    if t not in ("user", "assistant") or d.get("isSidechain") or d.get("isCompactSummary"):
        return
    m = d.get("message") or {}
    c = m.get("content")
    at = _ji(d)
    if t == "user":
        texts = [c] if isinstance(c, str) else [b.get("text", "") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text"]
        for s in texts:
            if "<cross-session-message" in s:
                for kara, body in CSM.findall(s):
                    if kara == HAITATSU_NA:
                        continue  # 亀井さんの書き込みは受け箱から出す（二重にしない）
                    _tasu(st, {"dare": "shirase", "kara": fuseru(kara)[:40], "text": fuseru(SR.sub("", body).strip())[:3000], "at": at})
                continue
            if d.get("isMeta"):
                continue
            h = _hito_text(s)
            if h is None or h.startswith(ATAMA) or h.startswith(ATAMA_SHACHOU):
                continue
            _tasu(st, {"dare": "hito", "text": fuseru(h)[:6000], "at": at})
        return
    for b in c or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text" and b.get("text", "").strip():
            tx = fuseru(SR.sub("", b["text"]).strip())
            for u in PUB.findall(tx):
                st["links"][u.rstrip(".,。、")] = at
            _tasu(st, {"dare": "ai", "text": tx[:12000], "at": at})
        elif b.get("type") == "tool_use":
            na = SAGYOU_NA.get(b.get("name", ""), "道具を使う")
            last = st["items"][-1] if st["items"] else None
            if last and last["dare"] == "sagyou":
                last["kazu"] += 1
                last["at"] = at
                if na not in last["nani"]:
                    last["nani"].append(na)
                st["koushin"] = last
            else:
                _tasu(st, {"dare": "sagyou", "kazu": 1, "nani": [na], "at": at})


def yomu(sid: str) -> dict:
    """その部屋の会話を、前に読んだ所から足された分だけ読む。"""
    p = kiroku_basho(sid)
    st = KYOU.get(sid)
    if not st or (p and st["path"] != p):
        st = KYOU[sid] = {"path": p, "pos": 0, "items": [], "n": 0, "links": {}, "rest": b"", "koushin": None}
    st["koushin"] = None
    if not p:
        return st
    size = p.stat().st_size
    if size < st["pos"]:
        st.update(pos=0, items=[], n=0, rest=b"")
    if size > st["pos"]:
        with open(p, "rb") as f:
            f.seek(st["pos"])
            buf = st["rest"] + f.read(size - st["pos"])
        st["pos"] = size
        lines = buf.split(b"\n")
        st["rest"] = lines.pop()
        for l in lines:
            if not l.strip() or (b'"type":"user"' not in l and b'"type":"assistant"' not in l
                                 and b'"type": "user"' not in l and b'"type": "assistant"' not in l):
                continue
            try:
                _gyou(st, json.loads(l))
            except Exception:
                continue
        if len(st["items"]) > 3000:
            st["items"] = st["items"][-2000:]
    st["ugoki"] = dt.datetime.fromtimestamp(p.stat().st_mtime, JST).isoformat(timespec="seconds")
    return st


# ---------- 成果物 ----------
NOZOKU_FILE = re.compile(r"録音|文字起こし|顧客|お客様|議事録本文|個人")


def houkoku_dirs(h: dict) -> list[Path]:
    b = h.get("basho") or ""
    if not b:
        return []
    b = Path(b)
    return [d for d in (b / "報告書", b / "日報", b / "madbro" / "報告書", b / "madbro" / "日報") if d.is_dir()]


def midashi(p: Path) -> str:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            for _ in range(15):
                l = f.readline()
                if not l:
                    break
                if p.suffix == ".md" and l.startswith("#"):
                    return fuseru(l.lstrip("#").strip())[:80]
                mm = re.search(r"<title>(.*?)</title>", l, re.I)
                if mm:
                    return fuseru(mm.group(1).strip())[:80]
    except Exception:
        pass
    return fuseru(p.stem)[:80]


def seika(h: dict, ooku: int = 30) -> list[dict]:
    out = []
    for d in houkoku_dirs(h):
        fs = [f for f in d.iterdir() if f.suffix in (".md", ".html") and not NOZOKU_FILE.search(f.name)]
        for f in sorted(fs, key=lambda x: x.stat().st_mtime, reverse=True)[:ooku]:
            if f.suffix == ".md" and f.with_suffix(".html").exists():
                continue
            out.append({"shurui": "日報" if "日報" in f.name or d.name == "日報" else "報告書", "namae": midashi(f),
                        "at": dt.datetime.fromtimestamp(f.stat().st_mtime, JST).isoformat(timespec="seconds"),
                        "fid": f"{d.name}/{f.name}", "heya": h["id"], "heya_na": h["namae"]})
    st = KYOU.get(h["sid"]) or {}
    for u, at in list((st.get("links") or {}).items())[-12:]:
        out.append({"shurui": "公開ページ", "namae": u.replace("https://madbrolabs.github.io/", ""), "at": at, "url": u,
                    "heya": h["id"], "heya_na": h["namae"]})
    for x in tsukutta():
        if x.get("heya_id") == h["id"]:
            out.append({"shurui": "亀井さんの頼み", "namae": x.get("nani", "")[:80], "at": x.get("at", ""),
                        "heya": h["id"], "heya_na": h["namae"], "tsukutta": x["i"], "joutai": x.get("joutai", "")})
    out.sort(key=lambda x: x.get("at", ""), reverse=True)
    return out


def seika_file(h: dict, fid: str) -> tuple[str, str] | None:
    """報告書1枚（読める形）。その部屋の報告書・日報の棚の中だけ。"""
    try:
        dn, fn = fid.split("/", 1)
    except ValueError:
        return None
    if "/" in fn or "\\" in fn or ".." in fn or NOZOKU_FILE.search(fn):
        return None
    for d in houkoku_dirs(h):
        if d.name == dn:
            f = d / fn
            if f.is_file() and f.suffix in (".md", ".html") and f.resolve().parent == d.resolve():
                return f.suffix[1:], fuseru(f.read_text(encoding="utf-8", errors="replace"))
    return None


# ---------- 受け箱（書き込み）と配達 ----------
def ukebako() -> Path:
    return D() / "ukebako"


def okutta(hid: str | None = None) -> list[dict]:
    out = [rj(f, None) for f in ukebako().glob("*.json")]
    out = [x for x in out if x and (hid is None or x.get("heya_id") == hid)]
    return sorted(out, key=lambda x: (x.get("t", 0), x.get("id", "")))


def todokeru_bun(x: dict) -> str:
    if x.get("shurui") == "shachou":
        return f'{ATAMA_SHACHOU}受付 {x["id"]}\n{x["text"]}'
    tsuika = (f'`{PY} -I -X utf8 {HERE / "kamei.py"} tsuika --heya "{x["dai"]}" --uketsuke {x["id"]} '
              f'--nani "何を作ったか" --oki "置き場（枝・フォルダ）" --kekka "試した結果"`')
    return f'{ATAMA}受付 {x["id"]}\n{x["text"]}\n{KIMARI.format(tsuika=tsuika)}'


def uketsukeru(hid: str, text: str, who: str = "kamei", shurui: str = "kamei") -> tuple[bool, str]:
    h = heya(hid)
    if not h:
        return False, "その部屋はありません"
    S = settei()
    text = "\n".join(l.rstrip() for l in str(text or "").strip().splitlines())
    if not text:
        return False, "書く事が空です"
    if len(text) > int(S["nagasa"]):
        return False, f'長すぎます（{S["nagasa"]}字まで）'
    if shurui == "kamei":
        mae = [x for x in okutta() if x.get("dare") == who and x.get("shurui") == "kamei"]
        now = time.time()
        if sum(1 for x in mae if now - x.get("t", 0) < int(S["renda_byou"])) >= int(S["renda_kazu"]):
            return False, f'少し間をあけてください（{S["renda_byou"]}秒に{S["renda_kazu"]}件まで）'
        if sum(1 for x in mae if x.get("heya_id") == hid and x.get("joutai") == "machi") >= int(S["machi_saidai"]):
            return False, "まだ届けていない書き込みがたまっています。少し待ってください"
    x = {"id": "K" + dt.datetime.now(JST).strftime("%Y%m%d%H%M%S") + secrets.token_hex(2), "at": ima(), "t": time.time(),
         "heya_id": hid, "sid": h["sid"], "dai": h["dai"], "dare": who, "shurui": shurui, "text": text,
         "joutai": "machi", "tamesi": 0}
    wj(ukebako() / f'{x["id"]}.json', x)
    log(f'受け付け {x["id"]} → {h["dai"]}（{len(text)}字・{shurui}）')
    return True, x["id"]


def kiroku_ni_aru(sid: str, uid: str, kara: int = 0) -> bool:
    p = kiroku_basho(sid)
    if not p:
        return False
    try:
        with open(p, "rb") as f:
            f.seek(max(0, min(kara, p.stat().st_size) - 4096))
            return uid.encode() in f.read()
    except Exception:
        return False


def find_claude() -> str | None:
    """版ごとにフォルダが変わる＝毎回いちばん新しい claude.exe を探す（メイド長と同じ道）。"""
    root = Path(os.environ.get("LOCALAPPDATA", r"C:\Users\hiroy\AppData\Local")) / "Claude-Data"
    best, key = None, None
    for p in glob.glob(str(root / "*" / "claude-code" / "*" / "*" / "claude.exe")):
        k = tuple(int(v) if v.isdigit() else 0 for v in re.split(r"[.\-]", Path(p).parent.parent.name))
        if key is None or k > key:
            best, key = p, k
    return best


def haitatsu_1(x: dict) -> str:
    """窓なしの claude -p を1回起こし、SendMessage でその部屋へ本文を届けさせる。戻り＝todoita／nemuri／dame"""
    exe = find_claude()
    if not exe:
        return "dame"
    p = kiroku_basho(x["sid"])
    kara = p.stat().st_size if p else 0
    honbun = todokeru_bun(x)
    tanomi = (f"あなたは「{HAITATSU_NA}」です。次の手順だけをして、ほかの事は一切しないでください。\n"
              f"1. ToolSearch で query=\"select:ListAgents,SendMessage\" を読み込む。\n"
              f"2. ListAgents で、名前が「{x['dai']}」の部屋があるか見る。\n"
              f"3. あれば SendMessage で to=その名前、message=下の【本文】の中身を一字も変えず、足さず、そのまま送る。\n"
              f"4. 送れたら「送りました」、部屋が一覧に無ければ「ありません」とだけ答えて終わる。\n"
              f"【本文】\n{honbun}\n【本文ここまで】")
    cmd = [exe, "-p", "--output-format", "json", "--model", "opus", "--effort", "low",
           "--permission-mode", "auto", "--permission-prompts", "none", "-n", HAITATSU_NA,
           "--tools", "ToolSearch,ListAgents,SendMessage"]
    try:
        r = subprocess.run(cmd, input=tanomi, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=str(D()), timeout=240, creationflags=NO_WINDOW,
                           env=dict(os.environ, CLAUDE_CODE_ENTRYPOINT=os.environ.get("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")))
        kotae = ""
        try:
            kotae = json.loads(r.stdout or "{}").get("result", "")
        except Exception:
            kotae = (r.stdout or "")[-300:]
        log(f'配達 {x["id"]} rc={r.returncode} 答え={kotae[:80]!r}')
    except Exception as e:
        log(f'配達 {x["id"]} つまずき {e!r}')
        return "dame"
    if "送りました" in kotae:  # 部屋の受け箱に入った。部屋のAIが読むのは次の番（読んだかは yonda で後から見る）
        return "todoita"
    for _ in range(10):  # 答えが崩れていても、部屋の記録に受付番号が出ていれば届いている
        if kiroku_ni_aru(x["sid"], x["id"], kara):
            return "todoita"
        time.sleep(3)
    return "nemuri" if "ありません" in kotae else "dame"


def haitatsu_mawari() -> None:
    """届けていない書き込みを古い順に1件ずつ届ける。"""
    for x0 in okutta():
        f = ukebako() / f'{x0["id"]}.json'
        x = rj(f, None)  # 並べた後に取り消された物を届けないよう、1件ごとに読み直す
        if x and x.get("joutai") == "todoita" and not x.get("yonda_at") and time.time() - x.get("t", 0) < 86400:
            if kiroku_ni_aru(x["sid"], x["id"], x.get("kara", 0)):  # 部屋のAIが読んだ（部屋の記録に受付番号が出た）
                x["yonda_at"] = ima()
                wj(f, x)
            continue
        if not x or x.get("joutai") != "machi":
            continue
        if x.get("tsugi", 0) > time.time():
            continue
        if kiroku_ni_aru(x["sid"], x["id"]):  # 見張りフックが先に届けていた
            x.update(joutai="todoita", todoita_at=ima(), michi=x.get("michi") or "hook", yonda_at=ima())
            wj(f, x)
            continue
        p0 = kiroku_basho(x["sid"])
        kara = p0.stat().st_size if p0 else 0
        kekka = haitatsu_1(x)
        x = rj(f, x)
        if x.get("joutai") != "machi":
            continue
        x["tamesi"] = x.get("tamesi", 0) + 1
        if kekka == "todoita":
            x.update(joutai="todoita", todoita_at=ima(), michi="SendMessage", kara=kara)
        else:
            x["nemuri"] = kekka == "nemuri"
            x["tsugi"] = time.time() + min(1800, 60 * 2 ** x["tamesi"])
        wj(f, x)
        log(f'{x["id"]} → {x["joutai"]}（{kekka}・{x["tamesi"]}回目）')


# ---------- 作った物の一覧 ----------
def tsukutta() -> list[dict]:
    out = []
    try:
        for i, l in enumerate((D() / "tsukutta.jsonl").read_text(encoding="utf-8-sig").splitlines()):
            try:
                x = json.loads(l)
            except Exception:
                continue
            if isinstance(x, dict):
                x["i"] = i + 1
                out.append(x)
    except FileNotFoundError:
        pass
    kt = rj(D() / "kettei.json", {})
    for x in out:
        k = kt.get(str(x["i"]))
        if k:
            x["joutai"] = {"irete": "入れて（主任へ渡した）", "miokuri": "見送り"}.get(k["kettei"], x.get("joutai"))
            x["kettei_at"] = k["at"]
        for kk in ("tanomi", "nani", "oki", "kekka"):
            x[kk] = fuseru(str(x.get(kk, "")))[:600]
    return out


def tsuika(heya_na: str, nani: str, oki: str, kekka: str, tanomi: str = "", uketsuke: str = "", joutai: str = "試し中") -> dict:
    hs = heya_ichiran()
    h = next((h for h in hs if heya_na in (h["dai"], h["namae"], h["id"], h["sid"])), None)
    if uketsuke and not tanomi:
        u = rj(ukebako() / f"{Path(uketsuke).name}.json", {})
        tanomi = u.get("text", "")
        h = h or heya(u.get("heya_id", ""))
    x = {"at": ima(), "heya": h["dai"] if h else heya_na, "heya_id": h["id"] if h else "", "uketsuke": uketsuke,
         "tanomi": tanomi, "nani": nani, "oki": oki, "kekka": kekka, "joutai": joutai}
    D().mkdir(parents=True, exist_ok=True)
    with open(D() / "tsukutta.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")
    return x


def kettei(i: int, k: str) -> tuple[bool, str]:
    x = next((t for t in tsukutta() if t["i"] == i), None)
    if not x or k not in ("irete", "miokuri"):
        return False, "ありません"
    kt = rj(D() / "kettei.json", {})
    kt[str(i)] = {"kettei": k, "at": ima()}
    wj(D() / "kettei.json", kt)
    if x.get("heya_id"):
        bun = (f'社長が「入れて」と決めました：亀井さんの頼みで作った物「{x["nani"]}」（置き場 {x["oki"]}）。'
               f'主任が本番に入れてください（kari/ の枝ならマージ、ほかは主任の手で入れる）。入れたら一覧の状態を「入れた」にしてください：'
               f'`{PY} -I -X utf8 {HERE / "kamei.py"} joutai {i} 入れた`') if k == "irete" else \
              f'社長が「見送り」にしました：亀井さんの頼みで作った物「{x["nani"]}」。本番には入れません。試しの版はそのまま残してかまいません。'
        uketsukeru(x["heya_id"], bun, who="shachou", shurui="shachou")
    log(f"作った物 {i} → {k}")
    return True, ""


# ---------- 門番へつなぐ ----------
def tsukeru(app) -> None:
    from aiohttp import web

    def jr(o, status=200):
        r = web.json_response(o, status=status, dumps=lambda v: json.dumps(v, ensure_ascii=False))
        r.headers["Cache-Control"] = "no-store"
        r.headers["X-Robots-Tag"] = "noindex"
        return r

    def mon(req):
        return dare(req.match_info.get("k", ""))

    async def nai(req):
        return web.Response(status=404, text="404 Not Found")

    async def page(req):
        if not mon(req) or not iri():
            return web.Response(status=404, text="404 Not Found")
        if not req.path.endswith("/"):
            raise web.HTTPFound(req.path + "/")
        r = web.Response(text=(HERE / "kamei.html").read_text(encoding="utf-8"), content_type="text/html")
        r.headers["Cache-Control"] = "no-store"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["X-Robots-Tag"] = "noindex"
        return r

    async def ichiran(req):
        who = mon(req)
        if not who or not iri():
            return web.Response(status=404, text="404 Not Found")

        def tsukuru():
            hs, zentai = [], []
            for h in heya_ichiran():
                st = yomu(h["sid"])
                last = next((x for x in reversed(st["items"]) if x["dare"] in ("hito", "ai")), None)
                hs.append({"id": h["id"], "dai": h["dai"], "namae": h["namae"], "kakari": h["kakari"],
                           "ugoki": st.get("ugoki", ""), "saigo": (last or {}).get("text", "")[:60]})
                zentai += seika(h, 8)
            zentai.sort(key=lambda x: x.get("at", ""), reverse=True)
            return {"dare": who, "heya": hs, "seika": zentai[:40], "ima": ima()}
        return jr(await asyncio.to_thread(tsukuru))

    async def chat(req):
        who = mon(req)
        h = heya(req.match_info["hid"])
        if not who or not h or not iri():
            return web.Response(status=404, text="404 Not Found")
        try:
            after = int(req.query.get("after", "-1"))
            before = int(req.query.get("before", "0"))
        except ValueError:
            after, before = -1, 0
        st = await asyncio.to_thread(yomu, h["sid"])
        its = st["items"]
        if before:
            out = [x for x in its if x["n"] < before][-60:]
        elif after < 0:
            out = its[-80:]
        else:
            out = [x for x in its if x["n"] > after]
            if its and its[-1]["dare"] == "sagyou" and its[-1]["n"] <= after:
                out = [its[-1]] + out  # 作業中の札は数が増えるので毎回送る（画面は data-key で差し替え）
        ok = [{"id": x["id"], "at": x["at"], "text": fuseru(x["text"]), "joutai": x["joutai"],
               "nemuri": x.get("nemuri", False), "dare": x["dare"], "yonda": bool(x.get("yonda_at"))}
              for x in okutta(h["id"]) if x.get("shurui") == "kamei"]
        ugoki = st.get("ugoki", "")
        return jr({"items": out, "okutta": ok, "ugoki": ugoki, "saisho": its[0]["n"] if its else 0,
                   "ima": ima(), "dai": h["dai"], "namae": h["namae"]})

    async def seika_api(req):
        who = mon(req)
        h = heya(req.match_info["hid"])
        if not who or not h or not iri():
            return web.Response(status=404, text="404 Not Found")
        await asyncio.to_thread(yomu, h["sid"])
        return jr({"seika": await asyncio.to_thread(seika, h)})

    async def fairu(req):
        who = mon(req)
        h = heya(req.match_info["hid"])
        if not who or not h or not iri():
            return web.Response(status=404, text="404 Not Found")
        r = await asyncio.to_thread(seika_file, h, req.query.get("f", ""))
        if not r:
            return web.Response(status=404, text="404 Not Found")
        if r[0] == "html":
            res = web.Response(text=r[1], content_type="text/html")
            res.headers["Content-Security-Policy"] = "default-src 'none'; img-src data: https:; style-src 'unsafe-inline'; font-src https: data:"
            return res
        return jr({"md": r[1]})

    async def kaku(req):
        who = mon(req)
        h = heya(req.match_info["hid"])
        if not who or not h or not iri():
            return web.Response(status=404, text="404 Not Found")
        try:
            d = await req.json()
        except Exception:
            return jr({"ok": False, "err": "形が違います"}, 400)
        ok, v = await asyncio.to_thread(uketsukeru, h["id"], d.get("text", ""), who)
        return jr({"ok": ok, "id": v} if ok else {"ok": False, "err": v}, 200 if ok else 400)

    async def tsukutta_api(req):
        if mon(req) != "shachou" or not iri():
            return web.Response(status=404, text="404 Not Found")
        return jr({"tsukutta": list(reversed(await asyncio.to_thread(tsukutta)))})

    async def kettei_api(req):
        if mon(req) != "shachou" or not iri():
            return web.Response(status=404, text="404 Not Found")
        try:
            d = await req.json()
            ok, e = await asyncio.to_thread(kettei, int(d.get("i")), str(d.get("kettei")))
        except Exception:
            ok, e = False, "形が違います"
        return jr({"ok": ok, "err": e}, 200 if ok else 400)

    async def mawari(a):
        async def loop():
            while True:
                try:
                    if iri():
                        await asyncio.to_thread(haitatsu_mawari)
                except Exception as e:
                    log(f"配達の見回りでつまずき {e!r}")
                await asyncio.sleep(5)
        a["kamei_haitatsu"] = asyncio.create_task(loop())

    r = app.router
    r.add_get("/kamei/{k}", page)
    r.add_get("/kamei/{k}/", page)
    r.add_get("/kamei/{k}/api/ichiran", ichiran)
    r.add_get("/kamei/{k}/api/heya/{hid}/chat", chat)
    r.add_get("/kamei/{k}/api/heya/{hid}/seika", seika_api)
    r.add_get("/kamei/{k}/api/heya/{hid}/f", fairu)
    r.add_post("/kamei/{k}/api/heya/{hid}/kaku", kaku)
    r.add_get("/kamei/{k}/api/tsukutta", tsukutta_api)
    r.add_post("/kamei/{k}/api/kettei", kettei_api)
    r.add_route("*", "/kamei/{k}/{tail:.*}", nai)
    r.add_route("*", "/kamei", nai)
    if os.environ.get("KAI_KAMEI_HAITATSU", "1") == "1":
        app.on_startup.append(mawari)


def kagi_tsukuru() -> None:
    p = NAISHO / "secret" / "kamei.json"
    if p.exists():
        print("鍵はもうあります（作り直しません）")
        return
    wj(p, {"kamei": secrets.token_urlsafe(32), "shachou": secrets.token_urlsafe(32), "tsukutta": ima()})
    print("鍵を作りました：", p)


def main() -> None:
    ap = argparse.ArgumentParser(description="亀井ページの道具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tsuika", help="亀井さんの頼みで作った物を一覧に1行足す")
    t.add_argument("--heya", required=True)
    t.add_argument("--nani", required=True)
    t.add_argument("--oki", default="")
    t.add_argument("--kekka", default="")
    t.add_argument("--tanomi", default="")
    t.add_argument("--uketsuke", default="")
    j = sub.add_parser("joutai", help="一覧の状態を変える（試し中／入れた／見送り）")
    j.add_argument("i", type=int)
    j.add_argument("joutai")
    sub.add_parser("kagi", help="専用URLの鍵を作る（初回だけ）")
    a = ap.parse_args()
    if a.cmd == "tsuika":
        print(json.dumps(tsuika(a.heya, a.nani, a.oki, a.kekka, a.tanomi, a.uketsuke), ensure_ascii=False))
    elif a.cmd == "joutai":
        p = D() / "tsukutta.jsonl"
        ls = p.read_text(encoding="utf-8-sig").splitlines()
        x = json.loads(ls[a.i - 1])
        x["joutai"] = a.joutai
        ls[a.i - 1] = json.dumps(x, ensure_ascii=False)
        p.write_text("\n".join(ls) + "\n", encoding="utf-8")
        kt = rj(D() / "kettei.json", {})
        if a.joutai in ("入れた", "見送り"):
            kt.pop(str(a.i), None)
            wj(D() / "kettei.json", kt)
        print("済みました")
    elif a.cmd == "kagi":
        kagi_tsukuru()


if __name__ == "__main__":
    main()
