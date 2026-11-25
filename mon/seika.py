"""成果物台帳（出来上がった物を1か所に書く帳面）と、それに1件足す道具。

台帳＝内緒の場所/seikabutsu/daichou.jsonl（1行1件 JSON）。亀井ページ・社長ページ（kamei.py）はここを読むだけ。
  at（足した時刻）heya（部屋の題）busho（任意）dai（題）hitokoto（一言）link（押せば開くURL）
  e（見本の絵の URL か PC の中の絵の場所・空でよい）dekita（出来た日）kakarichou_kakunin（係長確認済みか）
  dare_demo（任意・claude.ai の物を「リンクを知っていれば誰でも」に公開した時だけ true。無ければ社長の札だけに「社長のスマホで開けます」。亀井さんには一切出さない）
  naka（任意・社長／亀井さんの専用アドレスの下の道 例 "kaisha/"。あれば札はそちらを開く。鍵は台帳に書かない）
  moto・moto_karui（任意・busho「営業用資料」の時の元ファイル＝PC の中の PDF・HTML・動画（mp4/webm）・絵（png/jpg）。棚の係 atsume/eigyou.py が写しを公式ページ・社員ページへ置く。moto_karui は軽い版の PDF。moto_sumaho はスマホ用＝縦の画面に組み直した HTML か絵）
  shain_dake（任意・営業用資料を検めに関わらず公式ページに出さず社員ページ等だけにする時 true。false の行で公式へ戻す）
同じ link の行が後から来たら同じ札の「直した日」が新しくなって上へ上がる（2枚にしない）＝ matomeru()。
使い方：python seika.py tasu --heya "【主任】超議事録" --dai "…" --hitokoto "…" --link "https://…" [--e 絵] [--kakunin]
罠メモ：読む側は壊れた行を飛ばすだけ（台帳1行の書き損じでページ全体を止めない）。足す側は形を検査して弾く。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

JST = dt.timezone(dt.timedelta(hours=9))
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
E_KAKUCHOU = (".png", ".jpg", ".jpeg", ".webp", ".gif")
MOTO_KAKUCHOU = (".pdf", ".html", ".htm", ".mp4", ".webm", ".png", ".jpg", ".jpeg")  # 動画・絵は atsume/eigyou.py がそのまま写す
EIGYOU = "営業用資料"  # この部署で足した物は、営業用資料の棚（公式ページ・社員ページ）にも出る
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]


def naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def daichou_basho() -> Path:
    return naisho() / "seikabutsu" / "daichou.jsonl"


def e_basho() -> Path:
    return naisho() / "seikabutsu" / "e"


def fuda_id(link: str) -> str:
    return hashlib.sha1(link.strip().encode("utf-8")).hexdigest()[:12]


def ima() -> dt.datetime:
    return dt.datetime.now(JST)


def _hizuke(s: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _jikoku(s: str) -> dt.datetime | None:
    try:
        t = dt.datetime.fromisoformat(str(s))
        return t if t.tzinfo else t.replace(tzinfo=JST)
    except Exception:
        return None


def url_ka(s: str) -> bool:
    try:
        u = urlparse(str(s).strip())
    except Exception:
        return False
    t = str(s).strip()
    host = u.hostname or ""
    return (u.scheme in ("http", "https") and ("." in host or host == "localhost")
            and not any(c in t for c in " \t\n<>\"'") and len(t) <= 2000)


def kensa(x: dict) -> list[str]:
    """1行の形を確かめる。だめな所をやさしい言葉で返す（空なら合格）。"""
    dame = []
    if not isinstance(x, dict):
        return ["1行が JSON の形（{…}）になっていません"]
    if not str(x.get("heya", "")).strip():
        dame.append("部屋の題（heya）が空です")
    if not str(x.get("dai", "")).strip():
        dame.append("題（dai）が空です")
    elif len(str(x["dai"])) > 80:
        dame.append("題（dai）が長すぎます（80字まで）")
    if len(str(x.get("hitokoto", ""))) > 200:
        dame.append("一言（hitokoto）が長すぎます（200字まで）")
    if not url_ka(x.get("link", "")):
        dame.append("リンク（link）が https://… の形の URL ではありません")
    if x.get("naka") and not re.fullmatch(r"[a-z0-9_-]+/", str(x["naka"])):
        dame.append("専用アドレスの下の道（naka）は kaisha/ のような英小文字と斜線の形にしてください")
    e = str(x.get("e", "") or "").strip()
    if e and not url_ka(e):
        p = Path(e)
        if p.suffix.lower() not in E_KAKUCHOU:
            dame.append("絵（e）は URL か、PC の中の絵（png・jpg・webp・gif）の場所にしてください")
        elif not p.is_file():
            dame.append(f"絵（e）の場所に絵がありません：{e}")
    for kk in ("moto", "moto_karui", "moto_sumaho"):
        m = str(x.get(kk, "") or "").strip()
        if not m:
            continue
        p = Path(m)
        if not p.is_absolute() or p.suffix.lower() not in MOTO_KAKUCHOU or (kk == "moto_karui" and p.suffix.lower() != ".pdf"):
            dame.append(f"元ファイル（{kk}）は PC の中の PDF・HTML・動画（mp4/webm）・絵（png/jpg）の場所（C:\…）にしてください（軽い版は PDF だけ）")
        elif not p.is_file():
            dame.append(f"元ファイル（{kk}）の場所にファイルがありません：{m}")
    if str(x.get("moto_karui", "") or "").strip() and not str(x.get("moto", "") or "").strip():
        dame.append("軽い版（moto_karui）だけでは足せません。ちゃんとした版（moto）も書いてください")
    if str(x.get("moto_sumaho", "") or "").strip() and not str(x.get("moto", "") or "").strip():
        dame.append("スマホ用（moto_sumaho）だけでは足せません。パソコン用（moto）も書いてください")
    now = ima()
    d = _hizuke(x.get("dekita", ""))
    if not d:
        dame.append("出来た日（dekita）が 2026-11-25 の形ではありません")
    elif d > now.date():
        dame.append("出来た日（dekita）が未来の日付です")
    t = _jikoku(x.get("at", ""))
    if not t:
        dame.append("足した時刻（at）の形が違います")
    elif t > now + dt.timedelta(minutes=5):
        dame.append("足した時刻（at）が未来です")
    if not isinstance(x.get("kakarichou_kakunin", False), bool):
        dame.append("係長確認（kakarichou_kakunin）は true か false にしてください")
    return dame


def gyou_yomu() -> list[dict]:
    """台帳の行を古い順に。壊れた行・形の違う行は飛ばす。"""
    out = []
    try:
        ls = daichou_basho().read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return out
    for i, l in enumerate(ls):
        if not l.strip():
            continue
        try:
            x = json.loads(l)
        except Exception:
            continue
        if isinstance(x, dict) and not kensa(dict(x, e="", moto="", moto_karui="", moto_sumaho="")):  # 絵の場所が後で消えても札は出す
            x["_gyou"] = i + 1
            out.append(x)
    return out


def matomeru(rows: list[dict] | None = None) -> list[dict]:
    """同じ link を1枚にまとめ、新しく足された（直された）順に並べる。中身は一番新しい行、出来た日は一番古い行。"""
    fuda: dict[str, dict] = {}
    for x in rows if rows is not None else gyou_yomu():
        k = x["link"].strip()
        mae = fuda.get(k)
        y = dict(x)
        y["id"] = fuda_id(k)
        y["link"] = k
        if mae:
            y["dekita"] = min(str(mae["dekita"])[:10], str(x["dekita"])[:10])
            y["kaisuu"] = mae["kaisuu"] + 1
            y["hajime_at"] = mae["hajime_at"]
            if not str(x.get("e", "")).strip():
                y["e"] = mae.get("e", "")
            for kk in ("busho", "hitokoto", "moto", "moto_karui", "moto_sumaho"):
                if not str(x.get(kk, "")).strip():
                    y[kk] = mae.get(kk, "")
            if "shain_dake" not in x and "shain_dake" in mae:
                y["shain_dake"] = mae["shain_dake"]
        else:
            y["kaisuu"] = 1
            y["hajime_at"] = x["at"]
        y["naoshita"] = str(x["at"])[:10] if y["kaisuu"] > 1 else ""
        fuda[k] = y
    return sorted(fuda.values(), key=lambda y: (_jikoku(y["at"]) or dt.datetime.min.replace(tzinfo=JST), y["_gyou"]), reverse=True)


def e_tsukuru(link: str) -> str:
    """見本の絵が無い時、公開ページなら頭なしの Chrome で縮小を撮る（音は出さない・窓は出さない・終わったら止める）。"""
    host = urlparse(link).netloc.lower()
    if host.endswith("claude.ai") or host.startswith(("127.", "localhost")):
        return ""  # ログインの要る所・PC の中の所は撮れない（部屋の色の札になる）
    exe = next((c for c in CHROME if Path(c).is_file()), None)
    if not exe:
        return ""
    e_basho().mkdir(parents=True, exist_ok=True)
    out = e_basho() / f"{fuda_id(link)}.png"
    prof = tempfile.mkdtemp(prefix="seika_e_")
    try:
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--mute-audio", "--hide-scrollbars", "--no-first-run",
                        "--no-default-browser-check", "--disable-extensions", f"--user-data-dir={prof}",
                        "--window-size=1200,750", "--virtual-time-budget=6000", f"--screenshot={out}", link],
                       capture_output=True, timeout=60, creationflags=NO_WINDOW)
    except Exception:
        pass
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    if not (out.is_file() and out.stat().st_size > 2000):
        return ""
    try:  # スマホで軽く見られるよう 640 幅の jpg に縮める（PIL が無ければ png のまま）
        from PIL import Image
        jpg = out.with_suffix(".jpg")
        with Image.open(out) as im:
            im.convert("RGB").resize((640, round(im.height * 640 / im.width))).save(jpg, quality=82)
        out.unlink()
        return str(jpg)
    except Exception:
        return str(out)


def tasu(heya: str, dai: str, hitokoto: str, link: str, e: str = "", busho: str = "", dekita: str = "",
         kakunin: bool = False, e_jidou: bool = True, dare_demo: bool = False, naka: str = "",
         moto: str = "", moto_karui: str = "", shain_dake: bool | None = None, moto_sumaho: str = "") -> tuple[bool, dict | list[str]]:
    link = link.strip()
    x = {"at": ima().isoformat(timespec="seconds"), "heya": heya.strip(), "busho": busho.strip(), "dai": dai.strip(),
         "hitokoto": hitokoto.strip(), "link": link, "e": e.strip(), "dekita": (dekita or ima().date().isoformat()).strip(),
         "kakarichou_kakunin": bool(kakunin)}
    if dare_demo:
        x["dare_demo"] = True  # claude.ai の物でも「リンクを知っていれば誰でも開ける」設定にしてある
    if naka.strip():
        x["naka"] = naka.strip()  # 専用アドレスの下の写し（例 kaisha/）を開く。鍵は書かない
    if moto.strip():
        x["moto"] = moto.strip()  # 営業用資料の元ファイル（棚の係が写しを作る）
    if moto_karui.strip():
        x["moto_karui"] = moto_karui.strip()
    if moto_sumaho.strip():
        x["moto_sumaho"] = moto_sumaho.strip()  # スマホ用（縦の画面に組み直した版）。棚の札は画面の幅で開き分ける
    if shain_dake is not None:
        x["shain_dake"] = bool(shain_dake)  # 営業用資料を公式ページに出さない（true）／出してよい（false）
    dame = kensa(x)
    if dame:
        return False, dame
    if busho.strip() == EIGYOU and moto.strip():
        e_jidou = False  # 表紙の絵は棚の係が元ファイルから作る
    if not x["e"] and e_jidou and not any(m["link"] == link and m.get("e") for m in matomeru()):
        x["e"] = e_tsukuru(link)
    daichou_basho().parent.mkdir(parents=True, exist_ok=True)
    with open(daichou_basho(), "a", encoding="utf-8") as f:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")
    return True, x


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="成果物台帳の道具（亀井ページ・社長ページの「新しく出来た物」に出す）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tasu", help="出来上がった物を台帳に1件足す（同じリンクなら「直した」になる）")
    t.add_argument("--heya", required=True, help="部屋の題（例「【主任】超議事録」「【係長】相談室」「【亀部屋】○○」）")
    t.add_argument("--dai", required=True, help="題")
    t.add_argument("--hitokoto", default="", help="やさしい一言（200字まで）")
    t.add_argument("--link", required=True, help="押せば開く URL（https://…）")
    t.add_argument("--e", default="", help="見本の絵の URL か PC の中の絵の場所（無ければ公開ページは自動で撮る）")
    t.add_argument("--busho", default="", help="部署（任意）")
    t.add_argument("--dekita", default="", help="出来た日 2026-11-25（無ければ今日）")
    t.add_argument("--kakunin", action="store_true", help="係長が確かめた物")
    t.add_argument("--e-nashi", action="store_true", help="絵を自動で撮らない")
    t.add_argument("--dare-demo", action="store_true", help="claude.ai の物を「リンクを知っていれば誰でも」に公開してある時")
    t.add_argument("--naka", default="", help="社長／亀井さんの専用アドレスの下で開く道（例 kaisha/）。あれば札はそちらを開く")
    t.add_argument("--moto", default="", help="営業用資料の元ファイル（PC の中の PDF・HTML・動画・絵）。--busho 営業用資料 と一緒に")
    t.add_argument("--moto-sumaho", default="", help="営業用資料のスマホ用（縦の画面に組み直した HTML か絵）。札の「開く」が画面の幅で開き分ける")
    t.add_argument("--moto-karui", default="", help="営業用資料の軽い版の PDF（あれば棚で先に開く）")
    t.add_argument("--shain-dake", action="store_const", const=True, default=None, help="営業用資料を公式ページに出さず、社員ページ・社長ページ等だけにする")
    t.add_argument("--koushiki-ok", dest="shain_dake", action="store_const", const=False, help="--shain-dake を外す（検めを通れば公式ページにも出す）")
    sub.add_parser("kensa", help="台帳の全部の行を検査する")
    sub.add_parser("ichiran", help="ページに出る順で一覧を見る")
    a = ap.parse_args()
    if a.cmd == "tasu":
        ok, v = tasu(a.heya, a.dai, a.hitokoto, a.link, a.e, a.busho, a.dekita, a.kakunin, not a.e_nashi, a.dare_demo, a.naka,
                     a.moto, a.moto_karui, a.shain_dake, a.moto_sumaho)
        if not ok:
            print("足せませんでした。直してからもう一度どうぞ：")
            for d in v:
                print("・" + d)
            sys.exit(2)
        naoshi = sum(1 for m in gyou_yomu() if m["link"] == v["link"]) > 1
        print(("同じリンクの札を「直した」にして上へ上げました：" if naoshi else "台帳に足しました：") + v["dai"])
        print(json.dumps(v, ensure_ascii=False))
    elif a.cmd == "kensa":
        bad = 0
        try:
            ls = daichou_basho().read_text(encoding="utf-8-sig").splitlines()
        except FileNotFoundError:
            ls = []
        for i, l in enumerate(ls, 1):
            if not l.strip():
                continue
            try:
                d = kensa(json.loads(l))
            except Exception:
                d = ["JSON として読めません"]
            if d:
                bad += 1
                print(f"{i}行目：" + "／".join(d))
        print(f"全{len([l for l in ls if l.strip()])}行・だめ {bad}行")
        sys.exit(1 if bad else 0)
    elif a.cmd == "ichiran":
        for m in matomeru():
            print(f'{m["at"][:16]}  {m["dai"]}（{m["heya"]}）{"・直した" if m["naoshita"] else ""}{"・係長確認済み" if m.get("kakarichou_kakunin") else ""}  {m["link"]}')


if __name__ == "__main__":
    main()
