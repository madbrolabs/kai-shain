"""スマホ・パソコンへの知らせ（Web Push）を送る部品。協力者の広場（kyouryoku.py）が使う。

決まり事（RFC 8291 中身の暗号＝aes128gcm・RFC 8292 送り主の印＝VAPID）をそのまま書いた。
暗号の部品 cryptography は 内緒の場所/pylib に入れてある（門番の Python には無いので、そこを読みに行く）。
送り主の鍵（VAPID）＝内緒の場所/secret/kyouryoku_vapid.json（無ければ初めて使う時に作る）。表には出さない。
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit


def _naisho() -> Path:
    return Path(os.environ.get("KAI_NAISHO", r"C:\cl\kai_shain_private"))


def _pylib() -> None:
    p = str(_naisho() / "pylib")
    if p not in sys.path and Path(p).is_dir():
        sys.path.append(p)


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64d(s: str) -> bytes:
    s = str(s or "")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def tsukaeru() -> bool:
    """暗号の部品が読めるか。"""
    _pylib()
    try:
        import cryptography  # noqa: F401
        return True
    except Exception:
        return False


_KAGI = None


def kagi():
    """送り主の鍵（秘密の鍵の物・表に出す鍵の文字）。無ければ作って内緒の場所へ置く。"""
    global _KAGI
    if _KAGI is not None:
        return _KAGI
    _pylib()
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    p = _naisho() / "secret" / "kyouryoku_vapid.json"
    d = None
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        prv = ec.derive_private_key(int.from_bytes(b64d(d["d"]), "big"), ec.SECP256R1())
    except Exception:
        prv = ec.generate_private_key(ec.SECP256R1())
        n = prv.private_numbers().private_value.to_bytes(32, "big")
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"d": b64e(n), "memo": "協力者の広場の知らせ（Web Push）の送り主の鍵。表に出さない・コミットしない"}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
    pub = prv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    _KAGI = (prv, b64e(pub))
    return _KAGI


def koukai_kagi() -> str:
    return kagi()[1]


def _jwt(aud: str, sub: str) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    prv, _ = kagi()
    h = b64e(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    c = b64e(json.dumps({"aud": aud, "exp": int(time.time()) + 12 * 3600, "sub": sub}, separators=(",", ":")).encode())
    der = prv.sign(f"{h}.{c}".encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return f"{h}.{c}.{b64e(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def angou(nakami: bytes, p256dh: str, auth: str) -> bytes:
    """RFC 8291（aes128gcm）で中身を包む。受け取る端末だけが開けられる。"""
    _pylib()
    import hashlib
    import hmac as _h
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    def hm(k, m):
        return _h.new(k, m, hashlib.sha256).digest()

    ua_pub = b64d(p256dh)
    auth_s = b64d(auth)
    if len(ua_pub) != 65 or len(auth_s) < 16:
        raise ValueError("受け取る端末の鍵の形が違います")
    ua = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub)
    me = ec.generate_private_key(ec.SECP256R1())
    as_pub = me.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    ecdh = me.exchange(ec.ECDH(), ua)
    prk_key = hm(auth_s, ecdh)
    ikm = hm(prk_key, b"WebPush: info\x00" + ua_pub + as_pub + b"\x01")[:32]
    salt = os.urandom(16)
    prk = hm(salt, ikm)
    cek = hm(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = hm(prk, b"Content-Encoding: nonce\x00\x01")[:12]
    ct = AESGCM(cek).encrypt(nonce, nakami + b"\x02", None)
    return salt + (4096).to_bytes(4, "big") + bytes([len(as_pub)]) + as_pub + ct


async def okuru(session, kounyuu: dict, nakami: dict, sub: str, ttl: int = 86400) -> int:
    """1台へ送る。返り値＝届け先の答えの番号（201＝受け取った・404/410＝その端末はもう居ない）。"""
    ep = str(kounyuu.get("endpoint", ""))
    u = urlsplit(ep)
    if u.scheme != "https" or not u.hostname:
        return 400
    keys = kounyuu.get("keys") or {}
    body = angou(json.dumps(nakami, ensure_ascii=False).encode(), keys.get("p256dh", ""), keys.get("auth", ""))
    aud = f"{u.scheme}://{u.netloc}"
    hed = {
        "Authorization": f"vapid t={_jwt(aud, sub)}, k={koukai_kagi()}",
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Urgency": "normal",
    }
    async with session.post(ep, data=body, headers=hed) as r:
        await r.read()
        return r.status
