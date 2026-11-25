"""KAI社員ページ 言い直し係：開発の記録（機械の言葉まじり）を、誰が読んでも分かる普通の日本語に直す。
使い方: python -I -X utf8 yaku.py <内緒の場所> <data.json> [<data_shain.json> ...]
各項目に "yasashi": {欄の名前: 直した文} を書き足す。原文の欄はそのまま残す（ページの「原文」ボタン用）。
直した文は <内緒の場所>/yaku_cache.json に原文の指紋で覚える＝同じ文は二度と頼まない。
罠メモ: 裏の Claude は道具なし（--tools ""）で文字だけ返させる。JSON の外に何か付いても { } の間だけ拾う。
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
KUGIRI = 30          # 1回に頼む文の数
DOUJI = 4            # 同時に頼む数
RAN = {"susumi": ["text"], "kimatta": ["text"], "fusaiyou": ["text"], "omoi": ["text"], "kobanashi": ["text"],
       "commit": ["text"], "houkoku": ["daimei", "naiyou"], "dameshi": ["setsumei", "honbun", "naze"]}

TANOMI = """あなたは、ソフト開発の記録を社員向けに書き直す係です。
下の JSON の各文は、開発者が自分用に書いた走り書きで、ファイル名・部品の英字名・版番号・コミット番号などが混じり、普通の人には意味が通りません。
これを「ソフト開発を知らない日本人の社員が読んで、何が起きたか・何が出来たかが分かり、読んでいて楽しい」普通の日本語に直してください。

決まり：
- 事実は変えない・足さない・盛らない。分からない部分は無理に説明せず省く。
- ファイル名・英字の部品名・版番号・コミット番号・時刻の細かい数字は、要らなければ省き、要る物は「スマホの録音アプリ」「会社のGoogleの仕組み」のように中身の言葉に言い換える。
- 「〜した。」「〜になった。」の普通の文。1〜3文。元が短い物は短く。箇条の記号は付けない。
- 「社長」はそのまま。人の名前は元のまま。
- 返事は JSON だけ：{"番号": "直した文", ...}。全部の番号に答える。

"""


MATOME = """あなたは、ソフト開発の1日の進みを、社員向けに短くまとめる係です。
下は、あるソフト「{namae}」の、ある1日の進みの記録（細かい走り書き）です。
これを、ソフト開発を知らない社員が10秒で読んで「今日は何が進んだか」が分かるようにまとめてください。

決まり：
- "midashi"：その日のいちばん大きな出来事を、20字以内の見出し1つ（例「写真をみんなに見せられるようになった」）。
- "ten"：大事な事だけを2〜3個。1個は30字以内の短い文。使う人から見て「何が出来るようになったか・何が良くなったか」だけを書く。
- 書かない物：中の作り・道具やサービスの名前（使う人が画面で選ぶ物は除く）・鍵や設定や試験や測る話・まだの事や予定や持ち越し・やり直しの話・人の名前や役職（「社長」は除く）。
- 事実は変えない・足さない・盛らない。「社長」はそのまま。
- 返事は JSON だけ：{{"midashi": "...", "ten": ["...", "..."]}}

記録：
"""


def find_claude() -> str | None:
    root = Path(os.environ.get("LOCALAPPDATA", r"C:\Users\hiroy\AppData\Local")) / "Claude-Data"
    best, key = None, None
    for p in glob.glob(str(root / "*" / "claude-code" / "*" / "*" / "claude.exe")):
        ver = Path(p).parent.parent.name
        k = tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", ver))
        if key is None or k > key:
            best, key = p, k
    return best


NAISHO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\cl\kai_shain_private")


def kiku(exe: str | None, prompt: str, shurui: str, naiyou: str) -> str:
    """AI に1回頼む。L9 の頭えらび（atama_tsunagi.py・入/切つき）が無ければ今までどおり opus medium。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent)) if str(Path(__file__).resolve().parent) not in sys.path else None  # 罠：-I と埋め込み python では自分の場所が sys.path に無い
        import atama_tsunagi
        return atama_tsunagi.kiku(NAISHO, exe, prompt, shurui, naiyou)
    except ImportError:
        r = subprocess.run([exe, "-p", "--model", "opus", "--effort", "medium", "--tools", "",
                            "--output-format", "text", "--no-session-persistence"],
                           input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=900, creationflags=NO_WINDOW, cwd=os.environ.get("TEMP", "."))
        return r.stdout or ""


def yubi(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def tanomu(exe: str, bun: dict[str, str]) -> dict[str, str]:
    prompt = TANOMI + json.dumps(bun, ensure_ascii=False, indent=0)
    for _ in range(3):
        try:
            o = kiku(exe, prompt, "karui", "言い直し")  # L9：短い言い換え＝軽い頭
            i = o.find("{")  # 罠：{.*} で取ると塊が2つの時に読めない→最初の塊だけ読む
            if i >= 0:
                d, _ = json.JSONDecoder().raw_decode(o[i:])
                return {k: re.sub(r"ハイロ(様|さん|さま)?", "社長", str(v).strip()) for k, v in d.items() if k in bun and str(v).strip()}
        except Exception as e:  # noqa: BLE001
            print("やり直し:", e, file=sys.stderr)
    return {}


def matome_tanomu(exe: str, namae: str, bun: list[str]) -> dict | None:
    prompt = MATOME.format(namae=namae) + "\n".join("・" + b for b in bun)
    for _ in range(3):
        try:
            o = kiku(exe, prompt, "futsuu", "1日のまとめ")  # L9：まとめ＝ふつうの頭
            i = o.find("{")  # 罠：{.*} で取ると塊が2つの時に読めない→最初の塊だけ読む
            if i >= 0:
                d, _ = json.JSONDecoder().raw_decode(o[i:])
                fix = lambda v: re.sub(r"ハイロ(様|さん|さま)?", "社長", str(v).strip())
                ten = [fix(t) for t in d.get("ten", []) if str(t).strip()][:3]
                if d.get("midashi") and ten:
                    return {"midashi": fix(d["midashi"]), "ten": ten}
        except Exception as e:  # noqa: BLE001
            print("やり直し:", e, file=sys.stderr)
    return None


def matome(exe: str | None, datas: list, cache: dict, cache_p: Path) -> None:
    """進みを日ごとに束ね、見出し1つ＋要点2〜4個にまとめて h["susumi_matome"] に入れる（2026-11-25 社長「意味わからん・簡潔に」）。"""
    mada = {}
    kumi_all = []
    for d in datas:
        for h in d["soft"]:
            hibi: dict[str, list] = {}
            for x in h.get("susumi", []):
                hibi.setdefault((x.get("hi") or "")[:10], []).append(x)
            kumi = []
            for hi in sorted(hibi, reverse=True):
                bun = [(x.get("yasashi") or {}).get("text") or x.get("text") or "" for x in reversed(hibi[hi])]
                bun = [b for b in bun if b]
                key = "m2:" + yubi(  # 頼み文を変えたら番号を上げる＝全部頼み直す
                    h["namae"] + "\n" + "\n".join(bun))
                kumi.append((hi, key, len(bun)))
                if key not in cache:
                    mada[key] = (h["namae"], bun)
            kumi_all.append((h, kumi))
    print(f"まとめる日 {len(mada)} 件")
    if mada and exe:
        with ThreadPoolExecutor(DOUJI) as ex:
            for key, got in zip(mada, ex.map(lambda k: matome_tanomu(exe, *mada[k]), list(mada))):
                if got:
                    cache[key] = json.dumps(got, ensure_ascii=False)
                    cache_p.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    for h, kumi in kumi_all:
        h["susumi_matome"] = [dict(json.loads(cache[k]), hi=hi, kazu=n) for hi, k, n in kumi if k in cache]


def main() -> int:
    naisho = Path(sys.argv[1])
    files = [Path(a) for a in sys.argv[2:]]
    cache_p = naisho / "yaku_cache.json"
    cache: dict[str, str] = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}
    datas = [json.loads(f.read_text(encoding="utf-8")) for f in files]

    def koumoku(d):
        for h in d["soft"]:
            for k, rans in RAN.items():
                for x in h.get(k, []):
                    yield x, rans
        for x in d.get("lab_dameshi", []):
            yield x, RAN["dameshi"]

    mada: dict[str, str] = {}
    for d in datas:
        for x, rans in koumoku(d):
            for r in rans:
                s = x.get(r) or ""
                if len(s) >= 4 and yubi(s) not in cache:
                    mada[yubi(s)] = s
    exe = find_claude()
    print(f"直す文 {len(mada)} 件（覚えている物 {len(cache)} 件）")
    if mada and exe:
        keys = list(mada)
        kumi = [keys[i:i + KUGIRI] for i in range(0, len(keys), KUGIRI)]

        def ikkai(ks):
            ban = {str(n + 1): mada[k] for n, k in enumerate(ks)}
            got = tanomu(exe, ban)
            return {ks[int(n) - 1]: v for n, v in got.items() if n.isdigit() and 0 < int(n) <= len(ks)}

        with ThreadPoolExecutor(DOUJI) as ex:
            for n, got in enumerate(ex.map(ikkai, kumi)):
                cache.update(got)
                cache_p.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
                print(f"  {n + 1}/{len(kumi)} 組 済み（{len(got)} 件）", flush=True)
    for d in datas:
        for x, rans in koumoku(d):
            y = {r: cache[yubi(x[r])] for r in rans if x.get(r) and yubi(x[r]) in cache}
            if y:
                x["yasashi"] = y
    matome(exe, datas, cache, cache_p)
    for f, d in zip(files, datas):
        for x, rans in koumoku(d):
            y = {r: cache[yubi(x[r])] for r in rans if x.get(r) and yubi(x[r]) in cache}
            if y:
                x["yasashi"] = y
            else:
                x.pop("yasashi", None)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    nokori = sum(1 for d in datas for x, rans in koumoku(d) for r in rans if x.get(r) and len(x[r]) >= 4 and yubi(x[r]) not in cache)
    print(f"まだ直せていない文 {nokori} 件")
    try:
        import atama_tsunagi
        print(f"ゲージを送った行 {atama_tsunagi.gauge_okuru(NAISHO)} 件")
    except Exception as e:  # noqa: BLE001
        print("ゲージを送れず:", type(e).__name__, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
