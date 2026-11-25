"""声を字にする係（亀井ページの「マイクのボタン」アドオンの部品）。Whisper large-v3 を起こしっぱなしにして、届いた声を日本語の字にする。

使い方: pythonw -I -X utf8 koe_moji.py <内緒の場所>   （窓なし。門番 kamei.py が要る時に起こす。ログは <内緒の場所>/kamei/koe_moji.log）
口＝127.0.0.1:8849（KAI_KOE_PORT）。同じ口に2つ目は立たない（多重起動しない）。
  GET /genki → {"ok":true,"dekiru":bool,"kikai":"cuda float16"…}
  POST /moji（本文＝声そのまま。webm/opus・mp4/aac・wav など PyAV が読める物）→ {"ok":true,"text":…,"onsei_byou":…,"byou":…}
声はファイルにしない（メモリの中だけで読み、字にしたら捨てる）。
罠メモ：segs は後から計算される入れ物＝字を取り出して初めて動く。言葉は ja に決め、声の無い所は捨てる（幻の字よけ）。
罠メモ：Windows の http.server は同じ口に2つ目も立ってしまう（SO_REUSEADDR）→ allow_reuse_address=False。
"""
from __future__ import annotations

import datetime as dt
import glob
import io
import json
import os
import re
import site
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

NAISHO = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))
PORT = int(os.environ.get("KAI_KOE_PORT", "8849"))
JST = dt.timezone(dt.timedelta(hours=9))
MODEL = os.environ.get("KAI_KOE_MODEL", "large-v3")
SAIDAI_BYTE = 20 * 1024 * 1024
SAIDAI_BYOU = 300
# 声の無い所で Whisper がよく出す決まり文句（幻の字）。この字だけの塊は捨てる。
MABOROSHI = re.compile(r"^(?:ご視聴ありがとうございました|ご覧いただきありがとうございます|チャンネル登録(?:を)?お願いします|"
                       r"お疲れ様でした|ありがとうございました|字幕(?:は|by).*|提供.*|by .*|おやすみなさい)[。.!！\s]*$")


def log(s: str) -> None:
    try:
        (NAISHO / "kamei").mkdir(parents=True, exist_ok=True)
        with open(NAISHO / "kamei" / "koe_moji.log", "a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now(JST):%Y-%m-%d %H:%M:%S} {s}\n")
    except Exception:
        pass


def _dll() -> None:
    for sp in site.getsitepackages():
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")) + glob.glob(os.path.join(sp, "Lib", "site-packages", "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(d)
            except Exception:
                pass
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


M = {"m": None, "kikai": "", "err": ""}
JOU = threading.Lock()  # 1度に1本ずつ（GPU を取り合わない）


def yomikomu(cpu: bool = False) -> None:
    from faster_whisper import WhisperModel
    tame = [("cpu", "int8")] if cpu else [("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")]
    for dev, ct in tame:
        t0 = time.perf_counter()
        try:
            m = WhisperModel(MODEL, device=dev, compute_type=ct)
            import numpy as np
            "".join(s.text for s in m.transcribe(np.zeros(16000, dtype=np.float32), language="ja")[0])  # 温め
            M.update(m=m, kikai=f"{dev} {ct}", err="")
            log(f"{MODEL} を読み込みました（{dev} {ct}・{time.perf_counter() - t0:.1f}秒）")
            return
        except Exception as e:
            M["err"] = repr(e)[:200]
            log(f"{MODEL} を {dev} {ct} で読めませんでした {e!r}"[:300])
    M["m"] = None


def mojini(data: bytes) -> dict:
    from faster_whisper.audio import decode_audio
    t0 = time.perf_counter()
    try:
        a = decode_audio(io.BytesIO(data), sampling_rate=16000)
    except Exception as e:
        return {"ok": False, "riyuu": "yomenai", "err": repr(e)[:120]}
    finally:
        del data
    onsei = len(a) / 16000
    if onsei < 0.5:
        return {"ok": False, "riyuu": "mijikai", "onsei_byou": round(onsei, 2)}
    if onsei > SAIDAI_BYOU:
        return {"ok": False, "riyuu": "nagai", "onsei_byou": round(onsei, 2)}
    import numpy as np
    if float(np.sqrt(np.mean(a ** 2))) < 0.002:  # ほぼ無音（録れていない）
        return {"ok": False, "riyuu": "koe_nashi", "onsei_byou": round(onsei, 2)}

    def hashiru():
        segs, info = M["m"].transcribe(a, language="ja", beam_size=5, vad_filter=True,
                                       vad_parameters={"min_silence_duration_ms": 500},
                                       condition_on_previous_text=False, no_speech_threshold=0.6)
        out = []
        for s in segs:  # 字を取り出して初めて計算が走る
            t = s.text.strip()
            if not t or (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0) or MABOROSHI.match(t):
                continue
            out.append(t)
        return out

    with JOU:
        try:
            out = hashiru()
        except Exception as e:  # GPU のメモリを取り合って落ちた時などは CPU でやり直す
            log(f"字にする途中でつまずき（{M['kikai']}）{e!r}"[:300])
            if M["kikai"].startswith("cuda"):
                yomikomu(cpu=True)
                if not M["m"]:
                    return {"ok": False, "riyuu": "shippai"}
                out = hashiru()
            else:
                return {"ok": False, "riyuu": "shippai"}
    text = "".join(out).strip()
    byou = round(time.perf_counter() - t0, 2)
    log(f"字にした（声{onsei:.1f}秒→{len(text)}字・{byou}秒・{M['kikai']}）")  # 中身は書かない
    if not text:
        return {"ok": False, "riyuu": "kara", "onsei_byou": round(onsei, 2), "byou": byou}
    return {"ok": True, "text": text, "onsei_byou": round(onsei, 2), "byou": byou, "kikai": M["kikai"]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def kotae(self, o: dict, code: int = 200) -> None:
        b = json.dumps(o, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/genki":
            return self.kotae({"ok": True, "dekiru": M["m"] is not None, "kikai": M["kikai"], "model": MODEL, "err": M["err"]})
        self.kotae({"ok": False}, 404)

    def do_POST(self):
        if self.path != "/moji":
            return self.kotae({"ok": False}, 404)
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > SAIDAI_BYTE:
            return self.kotae({"ok": False, "riyuu": "ookisa"}, 400)
        data = self.rfile.read(n)
        if not M["m"]:
            return self.kotae({"ok": False, "riyuu": "junbichuu"}, 503)
        try:
            self.kotae(mojini(data))
        except Exception as e:
            log(f"字にできませんでした {e!r}"[:300])
            self.kotae({"ok": False, "riyuu": "shippai"})


class S(ThreadingHTTPServer):
    allow_reuse_address = False  # 2つ目を立てない
    daemon_threads = True


def main() -> None:
    try:
        srv = S(("127.0.0.1", PORT), H)
    except OSError:
        log(f"口 {PORT} はもう使われています（もう起きている）。終わります")
        return
    _dll()
    threading.Thread(target=yomikomu, daemon=True).start()
    log(f"声を字にする係を起こした（{PORT}・{MODEL}）")
    srv.serve_forever()


if __name__ == "__main__":
    main()
