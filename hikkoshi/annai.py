"""引っ越しの後、社長の PC の門番の代わりに 127.0.0.1:8802 で聞き、前のアドレスで来た人を新しい住所へそのまま回す（308）。

わけ：今 tailscale のトンネルは 443番の /kai・/kamei・/kyaku と 8443番の / を 127.0.0.1:8802 へ流している。
門番を止めてこの係を同じ番号で起こせば、トンネルの設定を触らずに、前のアドレス（一人ずつの専用ページの鍵の道も）が
https://shain.<ドメイン> の同じ道へ行く。鍵はアドレスの道のまま渡すだけで、ここには残さない（ログにも道を書かない）。

  pythonw -I -X utf8 hikkoshi/annai.py https://shain.kailab.co.jp [番号＝8802]
止め時：みんなが新しいアドレスに替えたら（数週間）、この係を止めてトンネルの道を外す（手順.md 5）。
"""
from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

if len(sys.argv) < 2 or not urlsplit(sys.argv[1]).scheme == "https" or not urlsplit(sys.argv[1]).hostname:
    sys.exit(__doc__)
SAKI = "https://" + urlsplit(sys.argv[1]).hostname  # 道・? の後ろは来た物をそのまま付ける。名前は決めた1つだけ（よそへは飛ばさない）
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8802


class Annai(BaseHTTPRequestHandler):
    def mawasu(self) -> None:
        p = self.path if self.path.startswith("/") else "/"
        self.send_response(308)
        self.send_header("Location", SAKI + p)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        b = ('<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width">'
             f'<p>社員ページは引っ越しました。<a href="{SAKI}/kai/">{SAKI}/kai/</a> から入ってください。</p>').encode("utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b)

    do_GET = do_POST = do_HEAD = do_PUT = do_DELETE = do_OPTIONS = mawasu

    def log_message(self, *a) -> None:  # 道（鍵が入る）を書かない
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Annai).serve_forever()
