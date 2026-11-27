"""社員ページの新しい住所（https://shain.kailab.co.jp）から、このPCの門番（127.0.0.1:8802）へ通すトンネル係。窓を出さない。

  pythonw -I -X utf8 mon/tonneru.py [内緒の場所＝C:\\cl\\kai_shain_private]
  起こし方：タスク KAISHAIN_tonneru（ログオンの時・止まったら1分ごとに起こし直す）。KAISHAIN_mon と同じ形。

中身：Cloudflare のトンネル（cloudflared）を、窓を出さずに動かし続ける。落ちたら少し待って起こし直す。
  道具＝C:\\Users\\hiroy\\tools\\cloudflared\\cloudflared.exe（KAI_CLOUDFLARED で替えられる）
  設定＝内緒の場所/cloudflared/config.yml（トンネルの名前・鍵の置き場・道）。鍵（<トンネルの番号>.json）も同じ所。倉庫には入れない。
  ログ＝内緒の場所/cloudflared/tonneru.log（5MB を超えたら前の分を .1 へ回す）。cloudflared は来た人の道を書かない（loglevel info）。
守り（通達 T1795712323）：管理画面（127.0.0.1:8807）は外へ出さない。設定の道に 8807 が入っていたら起こさない。
  道は shain.kailab.co.jp → http://127.0.0.1:8802 の1本だけ。残りは 404（設定の最後の http_status:404）。
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
import time
from pathlib import Path

NAISHO = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\cl\kai_shain_private")
D = NAISHO / "cloudflared"
CFG = D / "config.yml"
LOG = D / "tonneru.log"
EXE = os.environ.get("KAI_CLOUDFLARED", r"C:\Users\hiroy\tools\cloudflared\cloudflared.exe")
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def log(s: str) -> None:
    D.mkdir(parents=True, exist_ok=True)
    try:
        if LOG.exists() and LOG.stat().st_size > 5 * 1024 * 1024:
            LOG.replace(LOG.with_suffix(".log.1"))
    except OSError:
        pass
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {s}\n")


def mamori_ok(t: str) -> str:
    """設定を起こす前に見る。だめなら理由、よければ空。"""
    ikisaki = re.findall(r"^\s*(?:-\s*)?service:\s*(\S+)", t, re.M)
    if not ikisaki or ikisaki[-1] != "http_status:404":
        return "設定の最後が http_status:404 ではない（ほかの名前が門番へ流れる）"
    for s in ikisaki[:-1]:
        if s != "http://127.0.0.1:8802":
            return f"門番（127.0.0.1:8802）以外への道がある：{s[:60]}"
    if re.search(r":8807\b", t):
        return "設定に 8807（管理画面）が入っている"
    return ""


def main() -> None:
    try:  # 2つ目は起こさない（タスクと手で起こした分が重ならないように）
        import msvcrt
        D.mkdir(parents=True, exist_ok=True)
        lk = open(D / "tonneru.lock", "w")
        msvcrt.locking(lk.fileno(), msvcrt.LK_NBLCK, 1)
    except (ImportError, OSError):
        if sys.platform == "win32":
            return
    if not CFG.exists():
        log("設定（config.yml）が無いので起こしません")
        return
    dame = mamori_ok(CFG.read_text(encoding="utf-8"))
    if dame:
        log("起こしません：" + dame)
        return
    matsu = 5
    while True:
        t0 = time.time()
        log("cloudflared を起こします")
        with open(LOG, "a", encoding="utf-8") as out:
            p = subprocess.Popen([EXE, "--no-autoupdate", "tunnel", "--loglevel", "info", "--config", str(CFG), "run"],
                                 stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
            rc = p.wait()
        log(f"cloudflared が止まりました（{rc}）")
        matsu = 5 if time.time() - t0 > 300 else min(matsu * 2, 300)  # すぐ落ちる時は待ちを延ばす
        time.sleep(matsu)


if __name__ == "__main__":
    main()
