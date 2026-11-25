"""営業用資料の棚の係：成果物台帳の busho「営業用資料」の行から、写し（PDF・HTML・動画・絵）と表紙の小さな絵を作って棚に並べる。

使い方: python -I -X utf8 eigyou.py <内緒の場所> [--push]   （定時の仕事 KAISHAIN_eigyou が30分おきに --push で呼ぶ）
- 台帳の行に moto（元ファイル＝PC の中の PDF か HTML）が要る。moto_karui（軽い版の PDF）があれば棚はそれを先に開く。
- 元ファイルが変わったら（指紋が変わったら）写しと絵を作り直す＝作った主任は台帳に足すか、元ファイルを直すだけ。
- 公式ページへ出す前に検める：全案件の scrub_words.txt の言葉と鍵の形。1つでも当たれば公式には出さず、
  写しは 内緒の場所/eigyou/kakushi/<id>/ に置く（社員ページ・社長・お客のページから門番 mon/eigyou.py 経由で開く）。
- 出す物：docs/eigyou/<id>/（写し・e.jpg）と docs/eigyou/tana.json（公開の一覧）／内緒の場所/eigyou/tana.json（全部の一覧）と moji/<id>.txt（お客のページで隠す言葉を調べるための本文）。
罠メモ：当たった言葉そのものは一覧にもログにも書かない（数だけ）。--push は docs/eigyou だけをコミットする（git commit -- docs/eigyou）。
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import html as _html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KOKO = Path(__file__).resolve().parent
REPO = KOKO.parent
sys.path.insert(0, str(REPO / "mon"))
import seika  # noqa: E402

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
GIT = shutil.which("git") or "git"
PUB = REPO / "docs" / "eigyou"
URL = "https://madbrolabs.github.io/kai-shain/eigyou/"
SCRUB_GLOB = os.environ.get("KAI_SCRUB_GLOB", r"C:\cl\*_private\scrub_words.txt")
KAGI = re.compile(
    r"(ghp_|github_pat_|gho_|sk-[A-Za-z0-9]{8}|AIza[0-9A-Za-z]|xox[bp]-|-----BEGIN|"
    r"(password|passwd|token|secret)\s*[:=]\s*\S|"
    r"(合言葉|パスワード|鍵|暗証)\s*[:：=＝は]\s*[`「\"']?[A-Za-z0-9_\-]{6,}|"
    r"ts\.net|/kamei/[A-Za-z0-9_-]{20,}|/kyaku/[A-Za-z0-9_-]{20,})",
    re.I,
)
E_HABA = 480
DOUGA = {".mp4", ".webm"}  # 動画・絵は写しをそのまま開く（本文は題と一言だけで検める）
ZOU = {".png", ".jpg", ".jpeg"}


def log(naisho: Path, msg: str) -> None:
    t = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(naisho / "eigyou" / "eigyou.log", "a", encoding="utf-8") as f:
        f.write(f"{t} {msg}\n")


def scrub_kotoba() -> list[str]:
    out = []
    for p in glob.glob(SCRUB_GLOB):
        try:
            for l in Path(p).read_text(encoding="utf-8-sig").splitlines():
                l = l.strip()
                if l and not l.startswith("#") and len(l) >= 2:
                    out.append(l)
        except Exception:
            pass
    return list(dict.fromkeys(out))


def html_moji(t: str) -> str:
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", _html.unescape(t))


def pdf_moji(p: Path) -> str:
    import pymupdf
    with pymupdf.open(p) as d:
        return " ".join(pg.get_text() for pg in d)


def moji(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        return pdf_moji(p)
    return html_moji(p.read_text(encoding="utf-8", errors="replace"))


def fuzoku(p: Path) -> list[str]:
    """HTML が相対の道で読む絵など（同じフォルダより下にある物だけ）。"""
    t = p.read_text(encoding="utf-8", errors="replace")
    cand = re.findall(r'''(?:src|href)\s*=\s*["']([^"'#?]+)''', t) + re.findall(r'''url\(\s*["']?([^"')#?]+)''', t)
    out = []
    base = p.parent.resolve()
    for c in cand:
        c = c.strip()
        if not c or re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|/)", c, re.I):
            continue
        q = (base / c).resolve()
        if q.is_file() and base in q.parents and c not in out:
            out.append(c)
    return out


def shimon(files: list[Path]) -> str:
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def e_jpg(src_png: Path, out: Path) -> bool:
    from PIL import Image
    with Image.open(src_png) as im:
        im = im.convert("RGB")
        im = im.resize((E_HABA, round(im.height * E_HABA / im.width)))
        im.save(out, quality=82)
    return out.is_file()


def e_pdf(p: Path, out: Path) -> bool:
    import pymupdf
    with pymupdf.open(p) as d:
        pg = d[0]
        z = E_HABA * 2 / pg.rect.width
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(z, z))
        tmp = out.with_suffix(".png")
        pix.save(tmp)
    try:
        return e_jpg(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)


def e_douga(p: Path, out: Path) -> bool:
    """動画の3分の1あたりの1こまを表紙にする。"""
    import cv2
    v = cv2.VideoCapture(str(p))
    try:
        n = int(v.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        v.set(cv2.CAP_PROP_POS_FRAMES, max(0, n // 3))
        ok, f = v.read()
    finally:
        v.release()
    if not ok:
        return False
    tmp = out.with_suffix(".png")
    cv2.imencode(".png", f)[1].tofile(str(tmp))
    try:
        return e_jpg(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)


def e_html(p: Path, out: Path) -> bool:
    exe = next((c for c in seika.CHROME if Path(c).is_file()), None)
    if not exe:
        return False
    prof = tempfile.mkdtemp(prefix="eigyou_e_")
    tmp = Path(prof) / "e.png"
    try:
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--mute-audio", "--hide-scrollbars", "--no-first-run",
                        "--no-default-browser-check", "--disable-extensions", f"--user-data-dir={prof}",
                        "--window-size=1200,750", "--virtual-time-budget=6000", f"--screenshot={tmp}", p.resolve().as_uri()],
                       capture_output=True, timeout=90, creationflags=NO_WINDOW)
        return tmp.is_file() and tmp.stat().st_size > 2000 and e_jpg(tmp, out)
    except Exception:
        return False
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def kirei_na(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s).strip("_")[:60] or "shiryou"


def ookisa(n: int) -> str:
    return f"{n / 1024 / 1024:.1f}MB" if n >= 1024 * 1024 else f"{max(1, round(n / 1024))}KB"


def soto_dake(naisho: Path, x: dict, ng: list[str], m: dict | None) -> tuple[dict | None, bool]:
    """元ファイルが無く、もう誰でも開ける所（https・claude.ai 以外）にある資料＝札はそこを開く。写しは作らない。"""
    link = x["link"]
    if "claude.ai" in link.lower() or not link.startswith("https://"):
        log(naisho, f'{x["id"]} 元ファイル（moto）が無く、リンクも誰でも開ける所ではないので飛ばした')
        return None, False
    fid = x["id"]
    kensa_moji = " ".join([str(x.get("dai", "")), str(x.get("hitokoto", ""))])
    kouhou = not (any(w in kensa_moji for w in ng) or KAGI.search(kensa_moji) or x.get("shain_dake"))
    dst = (PUB if kouhou else naisho / "eigyou" / "kakushi") / fid
    kawatta = False
    if not (dst / "e.jpg").is_file():
        dst.mkdir(parents=True, exist_ok=True)
        e = str(x.get("e", "") or "").strip()
        src = Path(e) if e and Path(e).is_file() else None
        if not src:
            got = seika.e_tsukuru(link)
            src = Path(got) if got else None
        if src:
            try:
                e_jpg(src, dst / "e.jpg")
            except Exception:
                pass
        kawatta = True
    (naisho / "eigyou" / "moji" / f"{fid}.txt").write_text(kensa_moji, encoding="utf-8")
    return {"id": fid, "dai": x["dai"], "hitokoto": x.get("hitokoto", ""), "dekita": str(x.get("dekita", ""))[:10],
            "naoshita": x.get("naoshita", ""), "at": x.get("at", ""), "heya": x.get("heya", ""), "shurui": "ページ",
            "soto": link, "hiraku": "", "zentai": "", "ookisa": "", "ookisa_zentai": "", "dl_na": "", "dl_na_zentai": "",
            "e": (dst / "e.jpg").is_file(), "kouhou": kouhou, "atari": 0 if kouhou else 1, "shimon": "", "link": link}, kawatta


def tsukuru(naisho: Path) -> tuple[list[dict], bool]:
    priv = naisho / "eigyou"
    (priv / "moji").mkdir(parents=True, exist_ok=True)
    (priv / "kakushi").mkdir(parents=True, exist_ok=True)
    PUB.mkdir(parents=True, exist_ok=True)
    try:
        mae = {x["id"]: x for x in json.loads((priv / "tana.json").read_text(encoding="utf-8")).get("tana", [])}
    except Exception:
        mae = {}
    ng = scrub_kotoba()
    rows = [x for x in seika.matomeru() if str(x.get("busho", "")).strip() == seika.EIGYOU]
    tana, mita_shimon, kawatta = [], set(), False
    for x in rows:
        fid = x["id"]
        if not str(x.get("moto", "")).strip():
            t, k = soto_dake(naisho, x, ng, mae.get(fid))
            if t:
                tana.append(t)
                kawatta |= k
            continue
        moto = Path(str(x["moto"]).strip())
        karui = Path(str(x.get("moto_karui") or "").strip()) if str(x.get("moto_karui") or "").strip() else None
        if not moto.is_file() or (karui and not karui.is_file()):
            log(naisho, f"{fid} 元ファイルが見つからないので飛ばした")
            continue
        suf = moto.suffix.lower()
        pdf = suf == ".pdf"
        douga, zou = suf in DOUGA, suf in ZOU
        media = douga or zou
        fz = [] if (pdf or media) else fuzoku(moto)
        files = [moto] + ([karui] if karui else []) + [moto.parent / f for f in fz]
        sm = shimon(files)
        if sm in mita_shimon:
            log(naisho, f"{fid} 中身が他の資料と同じなので1枚にまとめた")
            continue
        mita_shimon.add(sm)
        try:
            honbun = "" if media else moji(moto)
        except Exception as e:
            log(naisho, f"{fid} 本文を読めませんでした {type(e).__name__}")
            continue
        kensa_moji = " ".join([str(x.get("dai", "")), str(x.get("hitokoto", "")), honbun])
        atari = sum(1 for w in ng if w in kensa_moji) + len(KAGI.findall(kensa_moji))
        kouhou = atari == 0 and not x.get("shain_dake")  # shain_dake＝作った部屋が「公式には出さない」と決めた物
        dst = (PUB if kouhou else priv / "kakushi") / fid
        hon = "shiryou.pdf" if pdf else ("douga" + suf if douga else ("zou" + suf if zou else "index.html"))
        hiraku = "karui.pdf" if karui else hon
        zentai = hon if karui else ""
        m = mae.get(fid)
        if not (m and m.get("shimon") == sm and m.get("kouhou") == kouhou and (dst / hiraku).is_file() and (dst / "e.jpg").is_file()):
            shutil.rmtree(dst, ignore_errors=True)
            dst.mkdir(parents=True)
            shutil.copy2(moto, dst / hon)
            if karui:
                shutil.copy2(karui, dst / "karui.pdf")
            for f in fz:
                (dst / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(moto.parent / f, dst / f)
            try:
                ok = (e_pdf(karui or moto, dst / "e.jpg") if (pdf or karui) else e_douga(moto, dst / "e.jpg") if douga
                      else e_jpg(moto, dst / "e.jpg") if zou else e_html(moto, dst / "e.jpg"))
            except Exception:
                ok = False
            if not ok:
                log(naisho, f"{fid} 表紙の絵を作れませんでした（絵なしの札）")
            kawatta = True
            log(naisho, f"{fid} 写しを作り直した（{'公式にも出す' if kouhou else (f'検めに{atari}か所当たったので社員だけ' if atari else '台帳で社員だけと決まっている')}）")
        (priv / "moji" / f"{fid}.txt").write_text(kensa_moji, encoding="utf-8")
        mono = "PDF" if pdf else ("動画" if douga else ("絵" if zou else "ページ"))
        tana.append({
            "id": fid, "dai": x["dai"], "hitokoto": x.get("hitokoto", ""), "dekita": str(x.get("dekita", ""))[:10],
            "naoshita": x.get("naoshita", ""), "at": x.get("at", ""), "heya": x.get("heya", ""),
            "shurui": mono, "hiraku": hiraku, "zentai": zentai,
            "ookisa": ookisa((dst / hiraku).stat().st_size), "ookisa_zentai": ookisa((dst / zentai).stat().st_size) if zentai else "",
            "dl_na": kirei_na(x["dai"]) + (".pdf" if (pdf or karui) else (suf if media else ".html")),
            "dl_na_zentai": kirei_na(x["dai"]) + ".pdf" if zentai else "",
            "e": (dst / "e.jpg").is_file(), "kouhou": kouhou, "atari": atari, "shimon": sm, "link": x["link"],
        })
    # 台帳から消えた物・公式から外れた物の写しを片付ける
    ids_pub = {t["id"] for t in tana if t["kouhou"]}
    ids_kak = {t["id"] for t in tana if not t["kouhou"]}
    for d, ids in ((PUB, ids_pub), (priv / "kakushi", ids_kak)):
        for c in d.iterdir():
            if c.is_dir() and c.name not in ids:
                shutil.rmtree(c, ignore_errors=True)
                kawatta = True
    for f in (priv / "moji").glob("*.txt"):
        if f.stem not in ids_pub | ids_kak:
            f.unlink(missing_ok=True)
    ima = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    kouhou_tana = [{k: v for k, v in t.items() if k not in ("kouhou", "atari", "shimon", "link", "heya")} for t in tana if t["kouhou"]]
    p = PUB / "tana.json"
    mae_pub = p.read_text(encoding="utf-8") if p.is_file() else ""
    atarashii = json.dumps({"tana": kouhou_tana}, ensure_ascii=False, indent=1)
    if mae_pub != atarashii:
        p.write_text(atarashii, encoding="utf-8")
        kawatta = True
    tmp = priv / "tana.tmp"
    tmp.write_text(json.dumps({"tsukutta": ima, "tana": tana}, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, priv / "tana.json")
    return tana, kawatta


def hashiru(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=600, creationflags=NO_WINDOW)


def push(naisho: Path) -> None:
    if not hashiru([GIT, "status", "--porcelain", "--", "docs/eigyou"]).stdout.strip():
        return
    hashiru([GIT, "add", "--", "docs/eigyou"])
    r = hashiru([GIT, "commit", "-q", "-m", "営業用資料の棚：台帳と元ファイルから写しを新しくしました（自動）\n\n"
                 "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>", "--", "docs/eigyou"])
    if r.returncode:
        log(naisho, "コミットなし: " + (r.stdout + r.stderr)[-300:])
        return
    r = hashiru([GIT, "push", "-q", "origin", "HEAD:main"])
    log(naisho, "push した" if r.returncode == 0 else "push 失敗: " + r.stderr[-300:])


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    naisho = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else seika.naisho()
    os.environ["KAI_NAISHO"] = str(naisho)
    (naisho / "eigyou").mkdir(parents=True, exist_ok=True)
    tana, kawatta = tsukuru(naisho)
    for t in tana:
        print(f'{"公式" if t["kouhou"] else "社員だけ"}  {t["dai"]}  {t["hiraku"] or "外のページ"} {t["ookisa"]}  絵{"あり" if t["e"] else "なし"}')
    print(f"全{len(tana)}件・変わった={kawatta}")
    if "--push" in sys.argv:
        push(naisho)
    return 0


if __name__ == "__main__":
    sys.exit(main())
