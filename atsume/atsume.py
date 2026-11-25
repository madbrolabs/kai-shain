"""KAI社員ページ 集める係（コア）。

指示書・報告書・コミットの日誌・ダメ出しのメモから、ソフトごとの「開発部屋」の材料を機械で集め、
1つの data.json にする。新しく書く手間はかけない（今ある物を読むだけ）。
使い方: python -I -X utf8 atsume.py <設定.json> <出す場所/data.json>
罠メモ: 設定（集める元の場所）は内緒の場所に置く。鍵らしい行は丸ごと捨てる（暗号にする前の守り）。
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

JST = dt.timezone(dt.timedelta(hours=9))
NO_WINDOW = 0x08000000

# 鍵・合言葉らしい物が混じる行は捨てる
KAGI = re.compile(
    r"(ghp_|github_pat_|gho_|sk-[A-Za-z0-9]|AIza[0-9A-Za-z]|xox[bp]-|-----BEGIN|"
    r"(password|passwd|token|secret)\s*[:=]\s*\S|"
    r"(合言葉|パスワード|鍵|暗証)\s*[:：=＝は]\s*[`「\"']?[A-Za-z0-9_\-]{6,}|"
    r"[A-Za-z0-9_\-+/]{36,})",
    re.I,
)
HIZUKE = re.compile(r"(20\d\d)-(\d\d)-(\d\d)(?:[ T]?(\d\d):(\d\d))?")
HIZUKE_FILE = re.compile(r"_(20\d\d)(\d\d)(\d\d)(?:_(\d\d)(\d\d))?")
# 開発でない私事の見出しは読まない
SHIJI_NOZOKU = re.compile(r"様子|体調|健康|耳|お金の練習")
KOBANASHI = re.compile(r"いきさつ|事件|落とし穴|失敗|ハマ|踏んだ|反省|止まった|固まっ|壊れ|しくじ|叱|ダメ出し|だめ出し")


# パソコンの中の場所（C:\… や ~/…）は読む人に要らないので名前だけ残す
BASHO = re.compile(r"(?:[A-Za-z]:[\\/]|~/)[^\s　、。（）()「」]*?([^\\/\s　、。（）()「」]+)(?=[\s　、。（）()「」]|$)")


# 家での呼び名は会社のページでは「社長」（2026-11-25 社長の指示）
YOBINA = re.compile(r"ハイロ(様|さん|さま)?")

# 社員（社長以外）の版に出さない内輪の話（2026-11-25 社長「変なことまで共有しなくていい」）
NAIWA = re.compile(r"オフレコ|真実|不正|権限の段|グランドマスター|叱|ダメ出し|だめ出し|反省|scold|めんどく|お伺い|係長|主任|社長「|社長（|経由|給料|お金|体調|小話|いきさつ|事件")


def kirei(s: str, n: int = 420) -> str:
    s = re.sub(r"\*\*|`|~~", "", s).strip()
    s = YOBINA.sub("社長", s)
    s = BASHO.sub(r"\1", s)
    s = re.sub(r"^[-*・]\s*", "", s)
    s = re.sub(r"\s+", " ", s)
    return s if len(s) <= n else s[: n - 1] + "…"


def hizuke(s: str) -> str:
    m = HIZUKE.search(s)
    if not m:
        return ""
    y, mo, d, h, mi = m.groups()
    return f"{y}-{mo}-{d}" + (f" {h}:{mi}" if h else "")


def anzen(s: str, scrub: list[str]) -> bool:
    return not KAGI.search(s)


def yomu(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def shijisho_kara(path: Path, scrub: list[str]) -> dict:
    """指示書を見出しごとに分け、思い・決まった事・採らなかった案・進み・小話を拾う。"""
    out = {k: [] for k in ("omoi", "kimatta", "fusaiyou", "susumi", "kobanashi")}
    midashi = ""
    midashi_hi = ""
    saigo_hi = ""
    for raw in yomu(path).splitlines():
        line = raw.rstrip()
        if line.startswith("#"):
            midashi = line.lstrip("#").strip()
            midashi_hi = hizuke(midashi)
            saigo_hi = ""
            continue
        if not line.strip() or SHIJI_NOZOKU.search(midashi):
            continue
        if not anzen(line, scrub):
            continue
        t = kirei(line)
        if len(t) < 6:
            continue
        hi = hizuke(line) or saigo_hi or midashi_hi
        saigo_hi = hi
        item = {"hi": hi, "text": t, "moto": path.stem, "midashi": kirei(midashi, 80)}
        if "思い" in midashi:
            out["omoi"].append(item)
        elif "【決" in line or (("決まった" in midashi or "決" in midashi[:3]) and raw.lstrip().startswith("-")):
            out["kimatta"].append(item)
        elif "採らなかった" in midashi or "不採用" in line:
            out["fusaiyou"].append(item)
        elif "進み" in midashi or re.match(r"\s*-\s*(進み|20\d\d-)", raw):
            out["susumi"].append(item)
        if KOBANASHI.search(line) and raw.lstrip().startswith("-"):
            out["kobanashi"].append(item)
    return out


def houkoku_kara(d: Path, scrub: list[str]) -> list[dict]:
    res = []
    if not d.is_dir():
        return res
    for p in sorted(d.glob("*.md")):
        if "報告" not in p.name and "公開" not in p.name:
            continue
        txt = yomu(p)
        lines = txt.splitlines()
        daimei = kirei(lines[0].lstrip("#"), 120) if lines else p.stem
        naiyou, tore = [], False
        for ln in lines[1:]:
            if ln.startswith("## "):
                tore = "出来た" in ln or "済んだ" in ln
                continue
            if tore and ln.strip() and anzen(ln, scrub):
                naiyou.append(ln.strip())
        m = HIZUKE_FILE.search(p.stem)
        hi = f"{m[1]}-{m[2]}-{m[3]}" + (f" {m[4]}:{m[5]}" if m and m[4] else "") if m else ""
        res.append({"hi": hi, "daimei": daimei, "naiyou": kirei(" ".join(naiyou), 600), "moto": p.name})
    return res


def git_kara(repo: Path, scrub: list[str]) -> list[dict]:
    if not (repo / ".git").exists():
        return []
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "log", "-n", "80", "--date=format:%Y-%m-%d %H:%M", "--pretty=%ad\t%s"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            creationflags=NO_WINDOW if sys.platform == "win32" else 0,
        )
    except Exception:
        return []
    res = []
    for ln in r.stdout.splitlines():
        if "\t" not in ln:
            continue
        hi, s = ln.split("\t", 1)
        if anzen(s, scrub):
            res.append({"hi": hi, "text": kirei(s, 200), "repo": repo.name})
    return res


def memo_kara(d: Path, nozoku: list[str]) -> list[dict]:
    res = []
    # 見出しは MEMORY.md の日本語の題を使う（description は英語が多い）
    dai = dict((m[2], m[1]) for m in re.finditer(r"^- \[(.+?)\]\((.+?)\)", yomu(d / "MEMORY.md"), re.M))
    for p in sorted(d.glob("*.md")):
        if p.name == "MEMORY.md" or any(n in p.name for n in nozoku):
            continue
        txt = yomu(p)
        if "type: feedback" not in txt:
            continue
        m = re.search(r"^description:\s*(.+)$", txt, re.M)
        setsumei = m[1].strip().strip('"') if m else ""
        body = txt.split("---", 2)[-1].strip()
        why = re.search(r"\*\*Why:?\*\*:?\s*(.+)", body)
        honbun = [ln for ln in body.splitlines() if ln.strip() and not ln.startswith("**") and anzen(ln, [])]
        res.append({
            "namae": p.stem,
            "setsumei": kirei(dai.get(p.name, setsumei), 240),
            "honbun": kirei(" ".join(honbun), 500),
            "naze": kirei(why[1], 300) if why else "",
            "hi": hizuke(body) or hizuke(setsumei),
            "_zen": setsumei + "\n" + body,
        })
    return res


# 書類の中で、埋まった住所・番号などは社員ページへ出さない（空欄の【社長記入】は残す）
FUSE = [re.compile(r"〒?\d{3}-\d{4}"), re.compile(r"\d{2,4}-\d{2,4}-\d{3,4}"), re.compile(r"\d{7,}")]


def fuseji(t: str, kakusu: list[str]) -> str:
    out = []
    for ln in t.splitlines():
        if KAGI.search(ln):
            continue
        ln = YOBINA.sub("社長", ln)
        for w in kakusu:
            if w:
                ln = ln.replace(w, "【社長記入】")
        for r in FUSE:
            ln = r.sub("【社長記入】", ln)
        out.append(ln)
    return "\n".join(out)


# 見出しだけで中身の無い行／アドレス・番号・鍵らしき文字列の行／同じ中身の繰り返しは見せない（2026-11-25 社長）
MIENAI = re.compile(r"[:：]\s*$|https?:|https?[A-Za-z0-9]{6,}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|/h/|(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Z])[A-Za-z0-9_-]{16,}")
ATAMA = re.compile(r"^\s*(20\d\d-\d\d-\d\d(\s+\d\d:\d\d)?\s*)?")


def seiri(xs: list[dict]) -> list[dict]:
    mita, out = set(), []
    for x in xs:
        t = x.get("text") or x.get("daimei") or x.get("setsumei") or ""
        if t and MIENAI.search(t):
            continue
        if MIENAI.search(" ".join(str(v) for v in x.values() if isinstance(v, str)).replace("：", "").replace(":", "")):
            continue
        kagi = ATAMA.sub("", t + "|" + (x.get("naiyou") or "")).strip()
        if kagi in mita:
            continue
        mita.add(kagi)
        out.append(x)
    return out


def hoka_no_mono(settei: dict) -> dict:
    """門番の行き先・開発の表・会社設立の書類・手引き・AIの包み（社長と社員の両方の箱へ）。鍵は箱ごとに別で入れる。"""
    o: dict = {"kaihatsu": [], "shorui": [], "tebiki": [], "tsutsumi": None}
    for s in settei["soft"]:
        if s.get("kaihatsu"):
            o["kaihatsu"].append(dict(s["kaihatsu"], id=s["id"], namae=s["namae"]))
    o["kaihatsu"] += settei.get("kaihatsu_hoka", [])
    st = settei.get("setsuritsu")
    if st:
        for f in st["files"]:
            fp = Path(st["dir"]) / f
            if fp.exists():
                o["shorui"].append({"daimei": re.sub(r"^\d+_|\.md$", "", f).replace("_", "・"),
                                    "hi": dt.datetime.fromtimestamp(fp.stat().st_mtime, JST).strftime("%Y-%m-%d %H:%M"),
                                    "md": fuseji(fp.read_text(encoding="utf-8"), st.get("kakusu", []))})
        o["shorui_midashi"] = st.get("midashi", "会社設立へ向けて")
    tb = settei.get("tebiki_dir")
    if tb:
        for fp in sorted(Path(tb).glob("*.md")):
            o["tebiki"].append({"id": fp.stem, "md": fuseji(fp.read_text(encoding="utf-8"), [])})
    at = settei.get("ai_tsutsumi")
    if at:
        try:
            ban = json.loads((Path(at["dir"]) / at["ban"]).read_text(encoding="utf-8"))
            fp = Path(at["dir"]) / at["file"]
            o["tsutsumi"] = {"namae": fp.name, "ban": ban.get("ban"), "koushin": ban.get("koushin"),
                             "md": fuseji(fp.read_text(encoding="utf-8"), [])}
        except Exception:
            pass
    mon = settei.get("mon")
    if mon:
        k = json.loads(Path(mon["kagi"]).read_text(encoding="utf-8"))
        o["mon"] = {"url": mon["url"], "_shain": k["shain"], "_shachou": k["shachou"]}
    return o


def shain_ban(data: dict, p: Path) -> None:
    """社員の版：エピソード（小話・ダメ出しと学び・ラボの心得）と、思い・決まった事・採らなかった案は社長だけ（「〜_小話.md」の思い・小話は社員にも出す）。
    進み・出来た事・工事日誌だけを、内輪の言葉が混じる行を落として出す。"""
    def ok(x: dict) -> bool:
        # 罠：出どころ（moto＝帳面の名前「〜主任」）まで網にかけると、主任の指示書の行が全部落ちる
        return not NAIWA.search(json.dumps({k: v for k, v in x.items() if k != "moto"}, ensure_ascii=False))

    def kokai(x: dict) -> bool:  # 社長が「社員にも」と言った話は「〜_小話.md」に書く＝社員の版にも出す
        return str(x.get("moto", "")).endswith("_小話")  # 帳面ごと社員向けに書く物なので内輪の言葉の網はかけない
    soft = []
    for h in data["soft"]:
        soft.append({"id": h["id"], "namae": h["namae"], "hitokoto": h["hitokoto"],
                     "omoi": [x for x in h["omoi"] if kokai(x)], "kimatta": [], "fusaiyou": [],
                     "kobanashi": [x for x in h["kobanashi"] if kokai(x)], "dameshi": [],
                     "susumi": [x for x in h["susumi"] if ok(x)],
                     "houkoku": [x for x in h["houkoku"] if ok(x)],
                     "commit": [x for x in h["commit"] if ok(x)]})
    hoka = {k: v for k, v in data.get("hoka", {}).items()}
    if "mon" in hoka:
        hoka["mon"] = {"url": hoka["mon"]["url"], "kagi": hoka["mon"]["_shain"], "dare": "shain"}
    p.write_text(json.dumps({"tsukutta": data["tsukutta"], "soft": soft, "lab_dameshi": [], "hoka": hoka},
                            ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    settei = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_path = Path(sys.argv[2])
    scrub: list[str] = []
    sdir = Path(settei["shijisho_dir"])
    memos = memo_kara(Path(settei["memory_dir"]), settei.get("memory_nozoku", []))
    tsukatta = set()
    soft_out = []
    for s in settei["soft"]:
        heya = {"id": s["id"], "namae": s["namae"], "hitokoto": s["hitokoto"],
                "omoi": [], "kimatta": [], "fusaiyou": [], "susumi": [], "kobanashi": [],
                "houkoku": [], "commit": [], "dameshi": []}
        for f in s["shijisho"]:
            got = shijisho_kara(sdir / f, scrub)
            for k, v in got.items():
                heya[k].extend(v)
        for d in s["houkoku"]:
            heya["houkoku"].extend(houkoku_kara(Path(d), scrub))
        for g in s["git"]:
            heya["commit"].extend(git_kara(Path(g), scrub))
        for mm in memos:
            if any(k.lower() in mm["_zen"].lower() for k in s["kotoba"]):
                heya["dameshi"].append({k: v for k, v in mm.items() if k != "_zen"})
                tsukatta.add(mm["namae"])
        for k in ("susumi", "houkoku", "commit", "kobanashi", "kimatta"):
            heya[k].sort(key=lambda x: x.get("hi", ""), reverse=True)
        for k in heya:
            if isinstance(heya[k], list):
                heya[k] = seiri(heya[k])
        heya["susumi"] = heya["susumi"][:60]
        heya["kobanashi"] = heya["kobanashi"][:40]
        heya["kimatta"] = heya["kimatta"][:80]
        soft_out.append(heya)
    lab = [{k: v for k, v in mm.items() if k != "_zen"} for mm in memos if mm["namae"] not in tsukatta]
    data = {
        "tsukutta": dt.datetime.now(JST).isoformat(timespec="minutes"),
        "soft": soft_out,
        "lab_dameshi": lab,
        "hoka": hoka_no_mono(settei),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shachou = dict(data, hoka=dict(data["hoka"]))
    if "mon" in shachou["hoka"]:
        m = shachou["hoka"]["mon"]
        shachou["hoka"]["mon"] = {"url": m["url"], "kagi": m["_shachou"], "dare": "shachou"}
    out_path.write_text(json.dumps(shachou, ensure_ascii=False, indent=1), encoding="utf-8")
    shain_ban(data, out_path.with_name(out_path.stem + "_shain.json"))
    kazu = {h["namae"]: {k: len(h[k]) for k in ("omoi", "kimatta", "fusaiyou", "susumi", "kobanashi", "houkoku", "commit", "dameshi")} for h in soft_out}
    print(json.dumps({"lab_dameshi": len(lab), **kazu}, ensure_ascii=False))


if __name__ == "__main__":
    main()
