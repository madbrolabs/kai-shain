"""KAI社員ページ 毎日の更新係：集める → 中身が変わっていれば錠をかけ直す → コミットして push。
使い方: pythonw -I -X utf8 koushin.py <内緒の場所>   （窓を出さない。ログは <内緒の場所>/koushin.log）
内緒の場所に置く物: settei.json（集める元）・secret/aikotoba.json（合言葉）・out/（集めた平文）。
罠メモ: 錠は毎回まぜ方が変わるので、比べるのは平文（集めた時刻を除く）の指紋。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
KOKO = Path(__file__).resolve().parent
REPO = KOKO.parent
NODE = os.environ.get("KAISHAIN_NODE") or shutil.which("node") or r"C:\Users\hiroy\tools\node-v26.13.1-win-x64\node.exe"
GIT = shutil.which("git") or "git"


def log(naishō: Path, msg: str) -> None:
    t = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(naishō / "koushin.log", "a", encoding="utf-8") as f:
        f.write(f"{t} {msg}\n")


def hashiru(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600, creationflags=NO_WINDOW)


def shimon(p: Path) -> str:
    d = json.loads(p.read_text(encoding="utf-8"))
    d.pop("tsukutta", None)
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main() -> int:
    naishō = Path(sys.argv[1])
    out = naishō / "out" / "data.json"
    mae = shimon(out) if out.exists() else ""
    r = hashiru([sys.executable.replace("pythonw", "python"), "-I", "-X", "utf8", str(KOKO / "atsume.py"),
                 str(naishō / "settei.json"), str(out)])
    if r.returncode:
        log(naishō, "集める係が失敗: " + r.stderr[-500:])
        return 1
    ato = shimon(out)
    if ato == mae and "--itsumo" not in sys.argv:
        log(naishō, "中身に変わりなし。今回は出さない")
        return 0
    enc = REPO / "docs" / "shain" / "data.enc.json"
    r = hashiru([NODE, str(KOKO / "fuu.mjs"), str(out), str(naishō / "secret" / "aikotoba.json"), str(enc)])
    if r.returncode:
        log(naishō, "錠の係が失敗: " + r.stderr[-500:])
        return 1
    hashiru([GIT, "add", "docs/shain/data.enc.json"])
    r = hashiru([GIT, "commit", "-q", "-m", "社員ページの中身を毎日の記録から更新\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"])
    if r.returncode:
        log(naishō, "コミットなし: " + (r.stdout + r.stderr)[-300:])
        return 0
    r = hashiru([GIT, "push", "-q", "origin", "main"])
    log(naishō, "更新して push した" if r.returncode == 0 else "push 失敗: " + r.stderr[-500:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
