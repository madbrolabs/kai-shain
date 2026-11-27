"""社員ページのデータを、社長の PC と借りたサーバーの間で送る係（画面にもログにも中身を出さない）。

  pythonw -I -X utf8 hikkoshi/noboru.py nobori    PC が書く物（noboru_mono.txt と主任名簿の写し）を PC → サーバー（日に何度でも）
  pythonw -I -X utf8 hikkoshi/noboru.py kudari    サーバーが書く物（kudari_mono.txt）を サーバー → PC（控え・戻す時の備え）
  pythonw -I -X utf8 hikkoshi/noboru.py hikkoshi  引っ越しの日：鍵（kagi_mono.txt）＋サーバーが書く物＋PC が書く物を PC → サーバー
  付け足し：--server root@kai-server（既定）／--local <場所>＝サーバーの代わりにこの PC の <場所> へ（試し）
            --zenbu＝nobori でも全部送り直す（ふだんは前に送ってから変わった物だけ＝内緒の場所/noboru_kiroku.json）
  消した物は向こうでは消えない（足す・替えるだけ）。消したい時は手でサーバーの物も消す。

運び方：Python の tarfile で包み、ssh（Windows の OpenSSH）でサーバーの tar へ流す。PC に rsync が無くても動く。
ログ＝内緒の場所/noboru.log（送った物の名前の数と大きさだけ）。
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAISHO = Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))
S_NAISHO = "/srv/kai_shain_private"
SSH = os.environ.get("KAI_SSH", r"C:\Windows\System32\OpenSSH\ssh.exe")
TAR = os.environ.get("KAI_TAR", r"C:\Program Files\Git\usr\bin\tar.exe")  # --local の試しで、サーバーの tar の代わり
MEIBO = {  # PC の名簿 → サーバーの写しの名前（英字＝字化けしない）
    Path(r"C:\Users\hiroy\Claude\主任名簿.json"): "meibo/shunin.json",
    Path(r"C:\Users\hiroy\Claude\亀部屋名簿.json"): "meibo/kamebeya.json",
    Path(r"C:\Users\hiroy\Claude\岩田部屋名簿.json"): "meibo/iwabeya.json",
    Path(r"C:\Users\hiroy\Claude\勝山部屋名簿.json"): "meibo/katsubeya.json",
}
NOZOKU = {"_bak", "_kettei.json", "__pycache__"}  # todoita/_kettei.json はサーバーが書く（社長の決め）
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def log(s: str) -> None:
    with open(NAISHO / "noboru.log", "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {s}\n")


def hyou(na: str) -> list[str]:
    return [l.strip() for l in (HERE / na).read_text(encoding="utf-8").splitlines() if l.strip()]


def tsutsumu(moto: Path, names: list[str], meibo: bool, mae: dict | None = None) -> tuple[bytes, int, dict]:
    """moto の下の names（と名簿）を tar に包む。無い物は飛ばす（入/切の札など）。
    mae（前に送った物の 名前→[時刻,大きさ]）を渡すと、変わった物だけを包む。戻り＝(包み, 件数, 今の 名前→[時刻,大きさ])。"""
    buf, n, ima = io.BytesIO(), 0, {}
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as t:
        def ireru1(p: Path, na: str) -> None:
            nonlocal n
            st = p.stat()
            ima[na] = [int(st.st_mtime), st.st_size]
            if mae is None or mae.get(na) != ima[na]:
                t.add(p, arcname=na, recursive=False)
                n += 1

        def ireru(p: Path, na: str) -> None:
            if p.name in NOZOKU:
                return
            if p.is_dir():
                for c in sorted(p.iterdir()):
                    ireru(c, f"{na}/{c.name}")
            elif p.is_file():
                ireru1(p, na)
        for na in names:
            ireru(moto / na, na)
        if meibo:
            for p, na in MEIBO.items():
                if p.is_file():
                    ireru1(p, na)
    return buf.getvalue(), n, ima


def okuru(data: bytes, server: str, local: str) -> None:
    if local:
        Path(local).mkdir(parents=True, exist_ok=True)
        cmd = [TAR, "-C", local.replace("\\", "/"), "-xf", "-", "--no-same-owner"]
    else:
        cmd = [SSH, "-o", "BatchMode=yes", server,
               f"tar -C {S_NAISHO} -xf - --no-same-owner && chown -R kai:kai {S_NAISHO} && chmod -R go-rwx {S_NAISHO}"]
    r = subprocess.run(cmd, input=data, capture_output=True, creationflags=NO_WINDOW, timeout=1800)
    if r.returncode:
        raise RuntimeError(f"送れませんでした（{r.returncode}）{r.stderr.decode('utf-8', 'replace')[-300:]}")


def toru(names: list[str], server: str, local: str) -> int:
    """サーバー（または --local の場所）から names を受け取り、PC の内緒の場所へ。無い物は飛ばす。"""
    ari = " ".join(f"$( [ -e {n} ] && echo {n} )" for n in names)
    if local:
        moto = Path(local)
        data, _, _ = tsutsumu(moto, [n for n in names if (moto / n).exists()], False)
    else:
        r = subprocess.run([SSH, "-o", "BatchMode=yes", server, f"cd {S_NAISHO} && tar -cf - {ari}"],
                           capture_output=True, creationflags=NO_WINDOW, timeout=1800)
        if r.returncode:
            raise RuntimeError(f"受け取れませんでした（{r.returncode}）{r.stderr.decode('utf-8', 'replace')[-300:]}")
        data = r.stdout
    n = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r") as t:
        for m in t.getmembers():
            if m.isfile():
                t.extract(m, NAISHO, filter="data")  # 外へはみ出す名前・リンクは断る
                n += 1
    return n


def main() -> None:
    a = sys.argv[1:]
    shu = a[0] if a else ""
    server = a[a.index("--server") + 1] if "--server" in a else "root@kai-server"
    local = a[a.index("--local") + 1] if "--local" in a else ""
    try:
        kiroku = Path(local) / "_noboru_kiroku.json" if local else NAISHO / "noboru_kiroku.json"  # 前に送った物（変わった物だけ送るため）
        if shu == "nobori":
            mae = json.loads(kiroku.read_text(encoding="utf-8")) if kiroku.exists() and "--zenbu" not in a else {}
            data, n, ima = tsutsumu(NAISHO, hyou("noboru_mono.txt"), True, mae)
            if n:
                okuru(data, server, local)
            kiroku.write_text(json.dumps(ima, ensure_ascii=False), encoding="utf-8")  # 送れた後だけ書く（つまずけば次にまた送る）
        elif shu == "hikkoshi":
            data, n, ima = tsutsumu(NAISHO, hyou("kagi_mono.txt") + hyou("kudari_mono.txt") + hyou("noboru_mono.txt"), True)
            okuru(data, server, local)
            kiroku.write_text(json.dumps({k: v for k, v in ima.items() if not k.startswith(("secret/",) + tuple(hyou("kudari_mono.txt")))},
                                         ensure_ascii=False), encoding="utf-8")
        elif shu == "kudari":
            n, data = toru(hyou("kudari_mono.txt"), server, local), b""
        else:
            sys.exit(__doc__)
        log(f"{shu} 済み {n}件 {len(data) // 1024}KB" + ("（試し）" if local else ""))
        print(f"{shu} 済み {n}件")
    except Exception as e:
        log(f"{shu} つまずき {e!r}"[:400])
        print(f"{shu} つまずき {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
