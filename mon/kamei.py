"""亀井ページ（門番 mon.py のアドオン）：係長相談室と各【主任】の部屋のやりとりを、亀井さんがスマホから見て、ちょこっと書き込める。

入口＝/kamei/<長い鍵>/（合言葉なし。鍵は 内緒の場所/secret/kamei.json の kamei・shachou。違えば 404）。
設定＝内緒の場所/kamei/settei.json（iri＝入/切、nozoku＝出さない部屋、renda＝連打よけ）。
書き込み＝内緒の場所/kamei/ukebako/<受付番号>.json に置き → すぐにプログラムだけで部屋の受け口へ書く（heya_pipe.py・AI は使わない・数十ミリ秒）。
  届いたかは、その部屋の会話の記録（jsonl）に受付番号が出たかで確かめる。届かない時は見張りフック kamei_mihari.py が次の一言で差し込む。
部屋＝係長相談室＋亀部屋名簿（【亀部屋】）＋主任名簿（【主任】）。名簿が増えれば一覧も増える。
新しく出来た物＝成果物台帳（seika.py・内緒の場所/seikabutsu/daichou.jsonl）を読んで大きな札で出す。権利まもりは亀井さんには出さない。
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
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
JST = dt.timezone(dt.timedelta(hours=9))
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
MEIBO = Path(os.environ.get("KAI_MEIBO", r"C:\Users\hiroy\Claude\主任名簿.json"))  # 試験の時だけ作り物の名簿に替える
KAMEBEYA = Path(os.environ.get("KAI_KAMEBEYA", r"C:\Users\hiroy\Claude\亀部屋名簿.json"))  # 亀井さんの仮の案件の部屋（係長が立てる）
PROJECTS = Path.home() / ".claude" / "projects"
NAISHO = Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))
HAITATSU_NA = "亀井ページの配達係"
JIREI = NAISHO / "kamei_jirei.json"  # 辞令の合図（係長が辞令を出した後に置く）。無い間は「辞令前」＝役職で呼ばない（社長のダメ出し 2026-11-25）
ATAMA_SHACHOU_KAKI = "【社長から（社員ページ経由）】"  # 社長が自分のページから書いた物
ATAMA_SHACHOU = "【社長の決め（亀井ページ経由）】"
ATAMA_ZEN = ("【亀井さんから（社員ページ経由）】", "【副社長（亀井さん）から（社員ページ経由）】",
             ATAMA_SHACHOU_KAKI, ATAMA_SHACHOU)  # 今と前の頭書き（記録に残っている物も二重に出さない）
KIMARI = ("――\n（この頼みの決まり）{tanomi}は、そのまま進めてよい（考える・作る・試すまでやってよい）。"
          "ただし本番には入れない＝作った物は別の枝（kari/kamei-<短い名前> など試しの版）に置き、本番のシステム・指示書の【決】・設定はそのまま。"
          "GitHub の倉庫がある部屋は kari/ の枝でプルリクエストを出し、札「亀井さんの頼み」を付ける。"
          "済んだら『{tanomi}で作った物』の一覧に1行足す（何を・どこに作ったか・試した結果）：\n"
          "{tsuika}\n"
          "{henji}は『承りました。作って社長に見てもらいます』の形で、この部屋のチャットにそのまま書く（{yobi}の画面にそのまま出る。配達係へ返さなくてよい）。"
          "{yakushoku_nashi}"
          "お金・法律に当たる物は今までどおり社長に確かめる。")


def jirei() -> str:
    """辞令の役職（例「副社長」）。合図のファイルが無い・役職が空なら ""＝辞令前。"""
    try:
        return str(json.loads(JIREI.read_text(encoding="utf-8-sig")).get("yakushoku") or "").strip()[:20]
    except Exception:
        return ""


KAKUSU = ("副社長",)  # 今まで使った肩書の名残。今の肩書（合図の yakushoku）と同じ物以外は、亀井さんの鍵で見える所に出さない
# （社長のダメ出し 2026-11-25・案A／通達 T1795592825：本人が望めば肩書を替える。替えたら前の肩書は隠す。肩書を替えたらここに足す）
KATAGAKI_NOZOMI = re.compile(r"肩書|役職|呼び方|呼び名|と呼んで|って呼んで|と呼ばれ|" + "|".join(map(re.escape, KAKUSU)))
TSUUTATSU = Path(os.environ.get("KAI_TSUUTATSU", "C:/Users/hiroy/.claude/skills/shunin/tsuutatsu.py"))


def kakusu_kotoba() -> tuple:
    y = jirei()
    return tuple(w for w in KAKUSU if w != y)


def kakusu(o, who):
    """亀井さんの鍵の時、今の肩書でない肩書（辞令前は全部）を含む行を返す物から外す（記録は消さない）。部屋の札は残し、題は言い換える。"""
    if who != "kamei":
        return o
    ng = kakusu_kotoba()
    return _kesu(o, ng, yobi()) if ng else o


def _aru(t: str, ng: tuple) -> bool:
    return any(w in t for w in ng)


def _kesu(o, ng: tuple, yb: str, key: str = ""):
    if isinstance(o, str):
        if not _aru(o, ng):
            return o
        if key in ("dai", "namae"):
            for w in ng:
                o = o.replace(w, yb)
            return o
        return ""
    if isinstance(o, list):
        out = []
        for x in o:
            if isinstance(x, dict) and "kakari" in x:  # 部屋の札は消さず、中の文だけ直す
                out.append(_kesu(x, ng, yb))
            elif not _aru(json.dumps(x, ensure_ascii=False), ng):
                out.append(x)
        return out
    if isinstance(o, dict):
        return {k: _kesu(v, ng, yb, k) for k, v in o.items()}
    return o


def katagaki_shiraseru(text: str, dai: str) -> bool:
    """亀井さんが肩書・呼び方の望みを書いたら、係長への報告帳に1行足す（機械が書くだけ。AI は使わない）。"""
    if not KATAGAKI_NOZOMI.search(text or ""):
        return False
    hon = " ".join(str(text).split())[:80]
    try:
        r = subprocess.run([PY, "-I", "-X", "utf8", str(TSUUTATSU), "houkoku", "亀井ページ",
                            f"亀井さんが肩書の望みを書きました：{hon}（部屋：{dai}）"],
                           capture_output=True, timeout=30, creationflags=NO_WINDOW)
        return r.returncode == 0
    except Exception as e:  # noqa: BLE001
        log(f"肩書の知らせを書けず {e!r}")
        return False


def atama_zen() -> tuple:
    return ATAMA_ZEN + (kotoba()["atama"],)


def yobi() -> str:
    """亀井さんの呼び方。辞令前は「亀井さん」、辞令の後は役職。"""
    return jirei() or "亀井さん"


def kotoba() -> dict:
    """亀井さんに見える所・部屋のAIに渡す言葉。辞令前は役職を一切出さない。"""
    y = jirei()
    if not y:
        return {"yobi": "亀井さん", "atama": "【亀井さんから（社員ページ経由）】", "tanomi": "亀井さんの頼み",
                "henji": "亀井さんへの返事", "aisatsu": "亀井さん、お越しいただきありがとうございます",
                "yakushoku_nashi": "亀井さんを役職で呼ばない（「亀井さん」と呼ぶ。役職は係長が辞令で決める）。"}
    return {"yobi": y, "atama": f"【{y}（亀井さん）から（社員ページ経由）】", "tanomi": f"{y}（亀井さん）の頼み",
            "henji": f"{y}への返事", "aisatsu": f"{y}、お越しいただきありがとうございます", "yakushoku_nashi": ""}


PY = next((x for x in [r"C:\Users\hiroy\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe"]
           + sorted(glob.glob(r"C:\Users\hiroy\AppData\Roaming\uv\python\cpython-3.1[1-9]*\python.exe"), reverse=True)
           + [r"C:\AI\ComfyUI\python_embeded\python.exe", sys.executable] if x and os.path.exists(x)), sys.executable)
# ↑ uv の「cpython-3.11-…」は版の入れ替えで中身の無い札になる事がある（2026-11-25 このPCで実測）。在る物を順に使う


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
         "nagasa": 1000, "machi_saidai": 5,
         # マイクのボタン（声を PC の Whisper で字にして届ける）。koe＝入/切、koe_byou 秒に koe_kazu 回まで、声は koe_mb まで
         "koe": "入", "koe_kazu": 4, "koe_byou": 60, "koe_mb": 15,
         # 成果物の欄に出さない物（出来た物だけ並べる）。settei.json に同じ名前で書くと既定と入れ替わる。
         # seika_dasanai＝題に当たれば出さない（正規表現）。seika_dasanai_tasu＝既定に足すだけの時。
         "seika_dasanai_shurui": ["報告書", "日報"],
         "seika_dasanai": [r"業務を停止しました", r"残タスクがなくなりました", r"^\s*⚠", r"一段落しませんでした", r"異常",
                           r"の報告書", r"出来上がりの報告", r"^\s*📣", r"報告（チーム", r"報告書$", r"日報"],
         "seika_dasanai_tasu": []}
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
    """係長相談室＋【亀部屋】＋【主任】の部屋全部（名簿から毎回作る＝増えれば増える）。nozoku に当たる部屋は出さない。"""
    m = rj(MEIBO, {})
    noz = [str(x) for x in settei().get("nozoku", [])]
    out = []
    kk = m.get("kakarichou") or {}
    if kk.get("session_id"):
        out.append({"id": kk["session_id"][:8], "sid": kk["session_id"], "dai": kk.get("dai") or "【係長】相談室",
                    "namae": "係長相談室", "basho": "", "kakari": True})
    for s in rj(KAMEBEYA, {}).get("kamebeya", []):
        sid = s.get("session_id") or ""
        if not sid or any(n and n.lower() in str(s.get("anken", "")).lower() for n in noz):
            continue
        out.append({"id": sid[:8], "sid": sid, "dai": s.get("dai") or f'【亀部屋】{s.get("anken", "")}',
                    "namae": s.get("anken", ""), "basho": "", "kakari": False, "kame": True})
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
CSM_RE = re.compile(r'<cross-session-message([^>]*)>(.*?)(?:</cross-session-message>|$)', re.S)
CSM_NA = re.compile(r'(?<![\w-])from-name="([^"]*)"')
CSM_KARA = re.compile(r'(?<![\w-])from="([^"]*)"')


class CSM:  # 送り主の名前＝from-name、無ければ from（社員ページの配達口は from-name を持たない）
    @staticmethod
    def findall(s: str) -> list[tuple[str, str]]:
        out = []
        for at, body in CSM_RE.findall(s):
            m = CSM_NA.search(at) or CSM_KARA.search(at)
            out.append((m.group(1) if m else "", body))
        return out
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
                    if kara == HAITATSU_NA or SR.sub("", body).strip().startswith(atama_zen()):
                        continue  # 亀井さんの書き込みは受け箱から出す（二重にしない）
                    _tasu(st, {"dare": "shirase", "kara": fuseru(kara)[:40], "text": fuseru(SR.sub("", body).strip())[:3000], "at": at})
                continue
            if d.get("isMeta"):
                continue
            h = _hito_text(s)
            if h is None or h.startswith(atama_zen()):
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
            _tasu(st, {"dare": "ai", "text": tx[:12000], "at": at, "owari": m.get("stop_reason") == "end_turn"})
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


def seika_dasu(shurui: str, namae: str) -> bool:
    """成果物の欄に出すか（停止の知らせ・異常・報告書そのものは出さない）。決まりは settei.json で足せる。"""
    S = settei()
    if shurui in S.get("seika_dasanai_shurui", []):
        return False
    for r in list(S.get("seika_dasanai", [])) + list(S.get("seika_dasanai_tasu", [])):
        try:
            if re.search(str(r), namae or ""):
                return False
        except re.error:
            if str(r) in (namae or ""):
                return False
    return True


# ---------- 部屋の一言（社長宛ての日本語の報告だけ）----------
KANA = re.compile(r"[぀-ヿ一-鿿]")
HIRA = re.compile(r"[぀-ゟ]")
HITORIGOTO = re.compile(r"(?i)^(?:let me|let's|i'll|i will|i need|i'm|now|ok|okay|first|next|good|great|perfect|done)\b"
                        r"|(?:を|も|に|で|から)?(?:見ます|見て(?:いき|み)ます|読みます|調べます|確かめます|探します|直します|作ります|書きます|"
                        r"進めます|始めます|続けます|撮ります|測ります|起こします|待ちます|試します|当たります|入れます|足します)[。．.!！]?$")
OTSUGE = re.compile(r"^\s*(?:お告げのとおり、?済ませました。?|お告げ、?承りました。?)\s*")


def _nihongo(t: str) -> bool:
    moji = re.sub(r"[\s\W\d_]", "", t)
    return bool(moji) and bool(HIRA.search(t)) and len(KANA.findall(moji)) / len(moji) >= 0.5


def _hitokoto_gyou(t: str) -> str:
    """報告文から、意味のある最初の1行（印・太字・箇条を外す）。"""
    t = re.sub(r"```.*?(?:```|$)", "", t, flags=re.S)
    for l in OTSUGE.sub("", t).splitlines():
        l = re.sub(r"^[\s#>\-*・\d.)）]+", "", l).replace("**", "").replace("`", "").strip()
        if l and _nihongo(l) and not re.match(r"^[\[{(（]?\s*\"", l):
            return l
    return ""


def hitokoto(st: dict) -> str:
    """部屋の一覧に出す一言。社長宛ての報告（「お告げのとおり、済ませました。」で始まる返事・区切りの返事）の最後の1件を短く。
    英語・作業途中の独り言・道具の出力は拾わない。見つからなければ空（画面は最後に動いた時刻だけ）。"""
    for x in reversed(st.get("items", [])):
        if x.get("dare") != "ai":
            continue
        t = (x.get("text") or "").strip()
        atama = t.splitlines()[0].strip() if t else ""
        if not t or not _nihongo(atama):
            continue
        otsuge = bool(re.match(r"^\s*お告げのとおり", t))
        if not otsuge:
            if not x.get("owari") or HITORIGOTO.search(atama) or re.search(r"(?i)^(?:let me|i'll|now )", t):
                continue
            if OTSUGE.sub("", t).strip() == "":  # 「承りました」だけ＝受けた知らせで報告ではない
                continue
        g = _hitokoto_gyou(t)
        if not g:
            if otsuge:
                return "お告げのとおり、済ませました。"
            continue
        return g if len(g) <= 60 else g[:59] + "…"
    return ""


def seika(h: dict, ooku: int = 30) -> list[dict]:
    out = []
    for d in houkoku_dirs(h):
        fs = [f for f in d.iterdir() if f.suffix in (".md", ".html") and not NOZOKU_FILE.search(f.name)]
        for f in sorted(fs, key=lambda x: x.stat().st_mtime, reverse=True)[:ooku]:
            if f.suffix == ".md" and f.with_suffix(".html").exists():
                continue
            shu = "日報" if "日報" in f.name or d.name == "日報" else "報告書"
            if shu in settei().get("seika_dasanai_shurui", []):
                continue
            na = midashi(f)
            if not seika_dasu(shu, na):
                continue
            out.append({"shurui": shu, "namae": na,
                        "at": dt.datetime.fromtimestamp(f.stat().st_mtime, JST).isoformat(timespec="seconds"),
                        "fid": f"{d.name}/{f.name}", "heya": h["id"], "heya_na": h["namae"]})
    st = KYOU.get(h["sid"]) or {}
    for u, at in list((st.get("links") or {}).items())[-12:]:
        na = u.replace("https://madbrolabs.github.io/", "")
        if "●" not in u and "#" not in u and seika_dasu("公開ページ", na):  # 鍵入りの入口（伏せた物）は成果物ではない
            out.append({"shurui": "公開ページ", "namae": na, "at": at, "url": u, "heya": h["id"], "heya_na": h["namae"]})
    for x in tsukutta():
        if x.get("heya_id") == h["id"] and seika_dasu("亀井さんの頼み", x.get("nani", "")):
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


# ---------- 新しく出来た物（成果物台帳を読むだけ）----------
def _seika():
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))  # -I で起こすと自分の場所が探す道に入らない
    os.environ.setdefault("KAI_NAISHO", str(NAISHO))
    import seika
    return seika


def daichou(who: str, heya_dai: str | None = None) -> list[dict]:
    """台帳の札（同じリンクは1枚・新しい順）。亀井さんには nozoku（権利まもり）の物を出さない。"""
    try:
        _s = _seika()
        rows = _s.matomeru()
    except Exception as e:
        log(f"台帳を読めませんでした {e!r}")
        return []
    noz = [str(x).lower() for x in settei().get("nozoku", []) if str(x)]
    hs = {h["dai"]: h["id"] for h in heya_ichiran()}
    out = []
    for x in rows:
        kan = " ".join(str(x.get(k, "")) for k in ("heya", "busho", "dai", "link", "e")).lower()
        if who != "shachou" and any(n in kan for n in noz):
            continue
        if heya_dai is not None and x.get("heya") != heya_dai:
            continue
        if not seika_dasu("台帳", str(x.get("dai", ""))):
            continue
        e = str(x.get("e", "") or "").strip()
        host = re.sub(r"^https?://([^/:]+).*$", r"\1", x["link"]).lower()
        naka = str(x.get("naka", "") or "")
        naka = naka if re.fullmatch(r"[a-z0-9_-]+/", naka) else ""  # 専用アドレスの下の写し（例 kaisha/）。画面が BASE を前に付ける
        out.append({"id": x["id"], "dai": fuseru(x["dai"])[:80], "hitokoto": fuseru(x.get("hitokoto", ""))[:200],
                    "link": x["link"], "heya": x.get("heya", ""), "heya_id": hs.get(x.get("heya", ""), ""),
                    "busho": x.get("busho", ""), "dekita": str(x.get("dekita", ""))[:10], "naoshita": x.get("naoshita", ""),
                    "at": x.get("at", ""), "kakunin": bool(x.get("kakarichou_kakunin")),
                    "e": e if e.startswith(("https://", "http://")) else (f"api/e/{x['id']}" if e else ""),
                    "naka": naka,
                    "shachou_dake": who == "shachou" and not naka and host.endswith("claude.ai") and not x.get("dare_demo")})
    return out


def e_fairu(fid: str) -> Path | None:
    """札の見本の絵（PC の中の絵）。台帳に書かれた絵だけ・絵の形だけ出す。"""
    try:
        _s = _seika()
        for x in _s.matomeru():
            if x["id"] == fid:
                p = Path(str(x.get("e", "")).strip())
                if p.suffix.lower() in _s.E_KAKUCHOU and p.is_file():
                    return p
    except Exception:
        pass
    return None


def zentai_matome(zentai: list[dict], fuda: list[dict], hs: list[dict]) -> list[dict]:
    """会社全体の成果物：台帳の行＋部屋の出来た物。同じリンクは1行（台帳の題を使う）。新しい順。"""
    na = {h["dai"]: h["namae"] for h in hs}
    out, mita = [], set()
    for x in fuda:
        out.append({"shurui": "出来た物", "namae": x["dai"], "at": x.get("naoshita") or x.get("at") or x.get("dekita", ""),
                    "url": x["link"], "naka": x.get("naka", ""), "heya": x.get("heya_id", ""), "heya_na": na.get(x.get("heya", "")) or x.get("busho") or re.sub(r"^【[^】]*】", "", x.get("heya", ""))})
        mita.add(x["link"].rstrip("/"))
    for x in zentai:
        u = (x.get("url") or "").rstrip("/")
        if u and u in mita:
            continue
        if u:
            mita.add(u)
        out.append(x)
    out.sort(key=lambda x: x.get("at", ""), reverse=True)
    return out


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
    w = kotoba()
    aisatsu = "社長、お越しいただきありがとうございます" if x.get("dare") == "shachou" else w["aisatsu"]
    rei = (f'\n（この部屋への初めての書き込みです。最初の返事は「{aisatsu}」から始めてください。'
           f'言うのは最初の一言だけで、毎回くり返さなくてよい）') if x.get("hajimete") else ""
    if x.get("dare") == "shachou":  # 社長が自分のページから書いた物＝社長の言葉（亀井さんの頼みの決まりは付けない）
        return f'{ATAMA_SHACHOU_KAKI}受付 {x["id"]}\n{x["text"]}{rei}'
    tsuika = (f'`{PY} -I -X utf8 {HERE / "kamei.py"} tsuika --heya "{x["dai"]}" --uketsuke {x["id"]} '
              f'--nani "何を作ったか" --oki "置き場（枝・フォルダ）" --kekka "試した結果"`')
    return f'{w["atama"]}受付 {x["id"]}\n{x["text"]}{rei}\n{KIMARI.format(tsuika=tsuika, **w)}'


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
    # その部屋で、この人の（今の呼び方での）初めての書き込みだけ、最初のお礼を頼む（辞令で呼び方が変われば、もう一度）
    yb = yobi() if who != "shachou" else "社長"
    hajimete = shurui == "kamei" and not any(o.get("sid") == h["sid"] and o.get("dare") == who and "hajimete" in o
                                            and o.get("yobi", "副社長" if o.get("dare") != "shachou" else "社長") == yb
                                            for o in okutta())
    x = {"id": "K" + dt.datetime.now(JST).strftime("%Y%m%d%H%M%S") + secrets.token_hex(2), "at": ima(), "t": time.time(),
         "heya_id": hid, "sid": h["sid"], "dai": h["dai"], "dare": who, "shurui": shurui, "text": text,
         "joutai": "machi", "tamesi": 0}
    if shurui == "kamei":
        x["hajimete"] = hajimete
        x["yobi"] = yb
    wj(ukebako() / f'{x["id"]}.json', x)
    log(f'受け付け {x["id"]} → {h["dai"]}（{len(text)}字・{shurui}）')
    if shurui == "kamei" and who == "kamei":
        threading.Thread(target=katagaki_shiraseru, args=(text, h["dai"]), daemon=True).start()
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


def _pipe():
    if str(HERE) not in sys.path:  # python -I は自分のフォルダを sys.path に入れない
        sys.path.insert(0, str(HERE))
    import heya_pipe
    return heya_pipe


def haitatsu_1(x: dict) -> str:
    """AI を使わず、プログラムだけでその部屋の受け口へ本文を書く（数十ミリ秒）。戻り＝todoita／nemuri／dame"""
    try:
        kekka, hito = _pipe().todokeru(x["sid"], todokeru_bun(x))
    except Exception as e:
        kekka, hito = "dame", repr(e)[:80]
    log(f'配達 {x["id"]} → {kekka}（{hito}・{time.time() - x.get("t", time.time()):.1f}秒）')
    return kekka


HAITATSU_JOU = __import__("threading").Lock()


def haitatsu_mawari() -> None:
    """届けていない書き込みを古い順に1件ずつ届ける。"""
    with HAITATSU_JOU:
        _haitatsu_mawari()


def _haitatsu_mawari() -> None:
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
            x.update(joutai="todoita", todoita_at=ima(), michi=x.get("michi") or "hook", yonda_at=ima(),
                     byou=round(time.time() - x.get("t", time.time()), 1))
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
            x.update(joutai="todoita", todoita_at=ima(), michi="pipe", kara=kara, byou=round(time.time() - x.get("t", time.time()), 1))
        else:
            x["nemuri"] = kekka == "nemuri"
            x["tsugi"] = time.time() + min(300, 5 * 2 ** x["tamesi"])  # 部屋が開けばすぐ届くよう短めにやり直す
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
        tn = kotoba()["tanomi"]
        bun = (f'社長が「入れて」と決めました：{tn}で作った物「{x["nani"]}」（置き場 {x["oki"]}）。'
               f'主任が本番に入れてください（kari/ の枝ならマージ、ほかは主任の手で入れる）。入れたら一覧の状態を「入れた」にしてください：'
               f'`{PY} -I -X utf8 {HERE / "kamei.py"} joutai {i} 入れた`') if k == "irete" else \
              f'社長が「見送り」にしました：{tn}で作った物「{x["nani"]}」。本番には入れません。試しの版はそのまま残してかまいません。'
        uketsukeru(x["heya_id"], bun, who="shachou", shurui="shachou")
    log(f"作った物 {i} → {k}")
    return True, ""


# ---------- マイクのボタン（声 → PC の Whisper の字 → 部屋へ）----------
# 声を字にする係＝koe_moji.py（Whisper large-v3 を起こしっぱなし・127.0.0.1:8849）。ここは声を中継するだけで、声をファイルにしない。
KOE_PORT = int(os.environ.get("KAI_KOE_PORT", "8849"))
KOE_JOU = __import__("threading").Lock()
KOE_OKOSHITA = [0.0]
KOE_KAI: dict[str, list[float]] = {}  # 人 → 送った時刻（1分に数回まで）
KOE_RIYUU = {"yomenai": "声を読めませんでした", "mijikai": "声が短すぎました", "nagai": "声が長すぎました",
             "koe_nashi": "声が入っていませんでした", "kara": "声から字が出ませんでした", "shippai": "PCで字にできませんでした",
             "junbichuu": "PCの文字起こしが準備中でした", "tsunagaranai": "PCの文字起こしにつながりませんでした",
             "nashi": "声が届きませんでした", "ookisa": "声が大きすぎました"}


def koe_iri() -> bool:
    return iri() and settei().get("koe") == "入"


def koe_py() -> Path:
    return Path(os.environ.get("KAI_KOE_PY", str(NAISHO / "venv_koe" / "Scripts" / "pythonw.exe")))


def _koe(path: str, data: bytes | None = None, timeout: float = 3) -> dict:
    import urllib.error
    import urllib.request
    rq = urllib.request.Request(f"http://127.0.0.1:{KOE_PORT}{path}", data=data, method="POST" if data is not None else "GET",
                                headers={"Content-Type": "application/octet-stream"} if data is not None else {})
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "riyuu": "shippai"}


def koe_okosu() -> bool:
    """声を字にする係が起きていなければ、窓なしで起こす（多重起動は係の側でも止める）。戻り＝もう答えられるか。"""
    try:
        return bool(_koe("/genki", timeout=1).get("dekiru"))
    except Exception:
        pass
    with KOE_JOU:
        if time.time() - KOE_OKOSHITA[0] < 120:  # 起こしたばかり（読み込み中）
            return False
        py = koe_py()
        if not py.exists():
            log(f"声を字にする係の Python がありません {py}")
            return False
        import subprocess
        subprocess.Popen([str(py), "-I", "-X", "utf8", str(HERE / "koe_moji.py"), str(NAISHO)],
                         creationflags=NO_WINDOW | 0x00000008 | 0x00000200,  # 窓なし・門番と切り離す
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        KOE_OKOSHITA[0] = time.time()
        log("声を字にする係を起こしました")
    return False


def koe_mojini(data: bytes) -> dict:
    """声を PC の Whisper で字にする。係が寝ていれば起こして、読み込み（十数秒）を待つ。"""
    t_owari = time.time() + 90
    while not koe_okosu():
        if time.time() > t_owari:
            return {"ok": False, "riyuu": "junbichuu"}
        time.sleep(1)
    try:
        return _koe("/moji", data, timeout=180)
    except Exception as e:
        log(f"声を字にする係につながりませんでした {e!r}")
        return {"ok": False, "riyuu": "tsunagaranai"}


def koe_uketsukeru(hid: str, data: bytes, gamen: str, who: str, mae: str = "") -> dict:
    """声を字にして、その字を本文として受け付ける。声がうまく取れなかった時だけ、画面の字のまま。
    mae＝話し始める前に欄に打ってあった字（PC の字の前にそのまま付ける）。"""
    S = settei()
    now = time.time()
    kai = [t for t in KOE_KAI.get(who, []) if now - t < int(S["koe_byou"])]
    if len(kai) >= int(S["koe_kazu"]):
        return {"ok": False, "err": f'少し間をあけてください（声は{S["koe_byou"]}秒に{S["koe_kazu"]}回まで）'}
    KOE_KAI[who] = kai + [now]
    gamen = str(gamen or "").strip()
    t0 = time.time()
    r = koe_mojini(data) if data else {"ok": False, "riyuu": "nashi"}
    del data
    moji_byou = round(time.time() - t0, 2)
    pc = (r.get("text") or "").strip() if r.get("ok") else ""
    mae = str(mae or "").strip()
    text, moji = ((mae + "\n" + pc if mae else pc), "pc") if pc else (gamen, "gamen")
    log(f'声 → {"PCの字" if pc else "画面の字"}（{r.get("riyuu", "")}・声{r.get("onsei_byou", "?")}秒・{moji_byou}秒）')
    if not text:
        return {"ok": False, "err": "声が取れませんでした（" + KOE_RIYUU.get(r.get("riyuu", ""), "") + "）。もう一度どうぞ"}
    if len(text) > int(S["nagasa"]):
        text = text[:int(S["nagasa"]) - 1] + "…"
    ok, v = uketsukeru(hid, text, who)
    if not ok:
        return {"ok": False, "err": v}
    return {"ok": True, "id": v, "text": text, "moji": moji, "gamen": gamen, "moji_byou": moji_byou,
            "riyuu": "" if pc else KOE_RIYUU.get(r.get("riyuu", ""), "")}


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
                hs.append({"id": h["id"], "dai": h["dai"], "namae": h["namae"], "kakari": h["kakari"], "kame": h.get("kame", False),
                           "ugoki": st.get("ugoki", ""), "saigo": hitokoto(st)})
                zentai += seika(h, 8)
            fuda = daichou(who)
            return kakusu({"dare": who, "koe": koe_iri(), "heya": hs, "seika": zentai_matome(zentai, fuda, hs)[:40], "atarashii": fuda[:30], "ima": ima()}, who)
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
        ai_at = [x["at"] for x in its if x["dare"] == "ai" and x.get("at")]
        ok = [{"id": x["id"], "at": x["at"], "text": fuseru(x["text"]), "joutai": x["joutai"],
               "nemuri": x.get("nemuri", False), "dare": x["dare"], "yonda": bool(x.get("yonda_at")),
               "byou": x.get("byou"),
               "henji": bool(x.get("todoita_at")) and any(a >= x["todoita_at"] for a in ai_at[-50:])}
              for x in okutta(h["id"]) if x.get("shurui") == "kamei"]
        ugoki = st.get("ugoki", "")
        return jr(kakusu({"items": out, "okutta": ok, "ugoki": ugoki, "saisho": its[0]["n"] if its else 0,
                          "ima": ima(), "dai": h["dai"], "namae": h["namae"]}, who))

    async def seika_api(req):
        who = mon(req)
        h = heya(req.match_info["hid"])
        if not who or not h or not iri():
            return web.Response(status=404, text="404 Not Found")
        await asyncio.to_thread(yomu, h["sid"])
        return jr(kakusu({"seika": await asyncio.to_thread(seika, h), "fuda": await asyncio.to_thread(daichou, who, h["dai"])}, who))

    async def e_api(req):
        if not mon(req) or not iri():
            return web.Response(status=404, text="404 Not Found")
        p = await asyncio.to_thread(e_fairu, req.match_info["fid"])
        if not p:
            return web.Response(status=404, text="404 Not Found")
        r = web.FileResponse(p)
        r.headers["Cache-Control"] = "private, max-age=600"
        return r

    async def fairu(req):
        who = mon(req)
        h = heya(req.match_info["hid"])
        if not who or not h or not iri():
            return web.Response(status=404, text="404 Not Found")
        r = await asyncio.to_thread(seika_file, h, req.query.get("f", ""))
        if not r or kakusu(r[1], who) != r[1]:  # 辞令前の亀井さんには「副社長」を含む資料を開かせない
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
        if not ok:
            return jr({"ok": False, "err": v}, 400)
        if os.environ.get("KAI_KAMEI_HAITATSU", "1") == "1":  # 5秒おきの見回りを待たず、すぐ届ける
            await asyncio.to_thread(haitatsu_mawari)
        x = rj(ukebako() / f"{v}.json", {})
        return jr({"ok": True, "id": v, "at": x.get("at"), "joutai": x.get("joutai"), "byou": x.get("byou"), "nemuri": x.get("nemuri", False)})

    async def koe_api(req):
        """マイクのボタン：声（koe）と画面の字（text）を受け、PC の字で届ける。鍵が違えば 404。声はメモリの中だけ。"""
        who = mon(req)
        h = heya(req.match_info["hid"])
        if not who or not h or not iri() or not koe_iri():
            return web.Response(status=404, text="404 Not Found")
        saidai = int(settei()["koe_mb"]) * 1024 * 1024
        data, gamen, mae = b"", "", ""
        try:
            rd = await req.multipart()
            while True:
                part = await rd.next()
                if part is None:
                    break
                if part.name == "text":
                    gamen = (await part.text())[:5000]
                elif part.name == "mae":
                    mae = (await part.text())[:5000]
                elif part.name == "koe":
                    buf = bytearray()
                    while True:
                        c = await part.read_chunk(65536)
                        if not c:
                            break
                        buf += c
                        if len(buf) > saidai:
                            return jr({"ok": False, "err": f'声が長すぎます（{settei()["koe_mb"]}MBまで）'}, 413)
                    data = bytes(buf)
        except Exception:
            return jr({"ok": False, "err": "形が違います"}, 400)
        r = await asyncio.to_thread(koe_uketsukeru, h["id"], data, gamen, who, mae)
        del data
        if not r.get("ok"):
            return jr(r, 400)
        if os.environ.get("KAI_KAMEI_HAITATSU", "1") == "1":
            await asyncio.to_thread(haitatsu_mawari)
        x = rj(ukebako() / f'{r["id"]}.json', {})
        r.update(at=x.get("at"), joutai=x.get("joutai"), byou=x.get("byou"), nemuri=x.get("nemuri", False))
        return jr(r)

    async def koe_okoshi(a):
        if koe_iri():  # 門番と一緒に起こしておく（最初の1回も待たせない）
            await asyncio.to_thread(koe_okosu)

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
    r.add_get("/kamei/{k}/api/e/{fid}", e_api)
    r.add_post("/kamei/{k}/api/heya/{hid}/kaku", kaku)
    r.add_post("/kamei/{k}/api/heya/{hid}/koe", koe_api)
    r.add_get("/kamei/{k}/api/tsukutta", tsukutta_api)
    r.add_post("/kamei/{k}/api/kettei", kettei_api)
    r.add_route("*", "/kamei/{k}/{tail:.*}", nai)
    r.add_route("*", "/kamei", nai)
    if os.environ.get("KAI_KAMEI_HAITATSU", "1") == "1":
        app.on_startup.append(mawari)
    app.on_startup.append(koe_okoshi)


def kagi_tsukuru() -> None:
    p = NAISHO / "secret" / "kamei.json"
    if p.exists():
        print("鍵はもうあります（作り直しません）")
        return
    wj(p, {"kamei": secrets.token_urlsafe(32), "shachou": secrets.token_urlsafe(32), "tsukutta": ima()})
    print("鍵を作りました：", p)


def kamebeya_toroku(anken: str, sid: str, dai: str = "") -> dict:
    """亀部屋名簿に1件足す（同じ案件名なら上書き）。係長が亀部屋を立てた時に使う。"""
    anken = anken.strip()
    sid = sid.strip().lower()
    if not anken:
        raise SystemExit("案件名が空です")
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", sid):
        raise SystemExit("部屋の番号（session_id）は 8-4-4-4-12 の形にしてください")
    m = rj(KAMEBEYA, {})
    ls = [x for x in m.get("kamebeya", []) if x.get("anken") != anken]
    x = {"anken": anken, "session_id": sid, "dai": dai.strip() or f"【亀部屋】{anken}", "toroku_at": ima()}
    ls.append(x)
    m["kamebeya"] = ls
    wj(KAMEBEYA, m)
    return x


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
    kb = sub.add_parser("kamebeya-toroku", help="亀部屋を名簿に足す（亀井ページ・社長ページの部屋一覧に出る）")
    kb.add_argument("anken", help="案件名（部屋の題は【亀部屋】案件名 になる）")
    kb.add_argument("session_id", help="その部屋の番号（ListAgents などで分かる 8-4-4-4-12 の形）")
    kb.add_argument("--dai", default="", help="部屋の題が【亀部屋】案件名 と違う時だけ")
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
    elif a.cmd == "kamebeya-toroku":
        x = kamebeya_toroku(a.anken, a.session_id, a.dai)
        print("亀部屋を名簿に足しました：" + x["dai"])
        print(json.dumps(x, ensure_ascii=False))


if __name__ == "__main__":
    main()
