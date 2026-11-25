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


def find_claude() -> str | None:
    root = Path(os.environ.get("LOCALAPPDATA", r"C:\Users\hiroy\AppData\Local")) / "Claude-Data"
    best, key = None, None
    for p in glob.glob(str(root / "*" / "claude-code" / "*" / "*" / "claude.exe")):
        ver = Path(p).parent.parent.name
        k = tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", ver))
        if key is None or k > key:
            best, key = p, k
    return best


def yubi(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def tanomu(exe: str, bun: dict[str, str]) -> dict[str, str]:
    prompt = TANOMI + json.dumps(bun, ensure_ascii=False, indent=0)
    for _ in range(3):
        try:
            r = subprocess.run([exe, "-p", "--model", "opus", "--effort", "medium", "--tools", "",
                                "--output-format", "text", "--no-session-persistence"],
                               input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=900, creationflags=NO_WINDOW, cwd=os.environ.get("TEMP", "."))
            m = re.search(r"\{.*\}", r.stdout, re.S)
            if m:
                d = json.loads(m.group(0))
                return {k: re.sub(r"ハイロ(様|さん|さま)?", "社長", str(v).strip()) for k, v in d.items() if k in bun and str(v).strip()}
        except Exception as e:  # noqa: BLE001
            print("やり直し:", e, file=sys.stderr)
    return {}


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
