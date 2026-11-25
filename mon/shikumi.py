"""社長ページだけの「しくみの覚え書き」（§28・2026-11-25）。

中身＝内緒の場所/shikumi/*.md（ソフトごとに1つ。名前の頭の数字が並ぶ順）。公開の倉庫には置かない。
各主任が自分の札のファイルを直せば、次に社長ページを開いた時にそのまま出る（再起動いらない）。
形：# 名前 / 係: 部屋 / ## 何をする / ## どう動く（1. 2. …）/ ## どこに置いてある / ## 止まった時に見る所
"""
from __future__ import annotations

import os
import re
from pathlib import Path

MIDASHI = {"何をする": "nani", "どう動く": "ugoki", "どこに置いてある": "basho", "止まった時に見る所": "tomatta"}


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def yomu1(p: Path) -> dict | None:
    try:
        t = p.read_text(encoding="utf-8-sig")
    except Exception:
        return None
    o = {"id": p.stem, "na": "", "kakari": "", "nani": [], "ugoki": [], "basho": [], "tomatta": []}
    cur = None
    for g in t.splitlines():
        s = g.strip()
        if not s or s.startswith("```"):
            continue
        if s.startswith("## "):
            cur = MIDASHI.get(s[3:].strip())
        elif s.startswith("# ") and not o["na"]:
            o["na"] = s[2:].strip()
        elif s.startswith("係:") or s.startswith("係："):
            o["kakari"] = s[2:].strip()
        elif cur:
            o[cur].append(re.sub(r"^(?:\d+[.．、)]|[-・*])\s*", "", s))
    return o if o["na"] else None


def ichiran() -> list[dict]:
    d = naisho() / "shikumi"
    if not d.is_dir():
        return []
    return [o for p in sorted(d.glob("*.md")) if not p.name.startswith("_") and (o := yomu1(p))]
