# 亀井ページの見張り（UserPromptSubmit・全部の部屋）2026-11-25
# 配達係（SendMessage）がまだ届けられていない書き込みが、この部屋あてに受け箱に残っていたら、
# この部屋の次の番に差し込んで「届いた」にする（部屋が眠っていて一覧に出なかった時の予備の道）。
# 登録は主任：~/.claude/settings.json の hooks.UserPromptSubmit に
#   "<uv の python> -I -X utf8 C:/cl/kai_shain/mon/kamei_mihari.py" を足す。
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        d = json.load(sys.stdin)
    except Exception:
        return
    sid = d.get("session_id") or ""
    if not sid:
        return
    try:
        import kamei as k
        if not k.iri():
            return
        out = []
        for x in k.okutta():
            if x.get("sid") != sid or x.get("joutai") != "machi":
                continue
            f = k.ukebako() / f'{x["id"]}.json'
            out.append(k.todokeru_bun(x))
            x.update(joutai="todoita", todoita_at=k.ima(), yonda_at=k.ima(), michi="hook")
            k.wj(f, x)
    except Exception:
        return
    if out:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                 "additionalContext": "\n\n".join(out)}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
