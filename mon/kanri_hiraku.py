"""デスクトップの近道「KAI 管理画面」から pythonw で呼ぶ（窓を出さない）。
門番の管理画面の口（127.0.0.1:8807）が起きているか確かめ、眠っていれば門番の予定の仕事（KAISHAIN_mon）を起こして待ち、
管理画面だけをアプリの窓で開く。門番は止めない（通達 T1795712323）。
"""
from __future__ import annotations

import os
import subprocess
import time
import urllib.request
import webbrowser
from pathlib import Path

PORT = int(os.environ.get("KAI_KANRI_PORT", "8807"))
URL = f"http://127.0.0.1:{PORT}/"
NO_WINDOW = 0x08000000
LOG = Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private")) / "kanri_hiraku.log"  # mon.log の隣


def kaku(s: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")
    except Exception:
        pass


def okite() -> bool:
    try:
        with urllib.request.urlopen(URL + "genki", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> None:
    if not okite():
        kaku("管理画面の口が眠っていたので、門番の予定の仕事を起こします")
        subprocess.run(["schtasks", "/run", "/tn", "KAISHAIN_mon"], creationflags=NO_WINDOW,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            time.sleep(0.5)
            if okite():
                break
        else:
            kaku("30秒待っても管理画面の口が起きませんでした（開く画面に知らせが出ます）")
    for c in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if Path(c).exists():
            subprocess.Popen([c, f"--app={URL}", "--window-size=1100,900"], creationflags=NO_WINDOW,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            kaku(f"開きました（{Path(c).name}）")
            return
    webbrowser.open(URL)
    kaku("開きました（いつものブラウザ）")


if __name__ == "__main__":
    main()
