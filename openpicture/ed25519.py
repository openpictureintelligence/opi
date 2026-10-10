"""Ed25519 (RFC 8032), pure Python, standard library only.

This is the RFC's own reference algorithm, transcribed, so that a verifier
can be copied anywhere without a compiled dependency. It is slow — a verify
costs tens of milliseconds — which is irrelevant for a sidecar and would be
wrong for a server. If `cryptography` is importable it is used instead;
the results are identical, that is the point of a standard.

Only the raw 32-byte key and 64-byte signature encodings from RFC 8032 are
handled here. PEM, X.509 and key custody are somebody else's problem.
"""

from __future__ import annotations

import hashlib
import secrets

__all__ = ["generate_secret", "public_key", "sign", "verify", "BACKEND"]

_p = 2**255 - 19
_q = 2**252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_sqrt_m1 = pow(2, (_p - 1) // 4, _p)


def _inv(x: int) -> int:
    return pow(x, _p - 2, _p)


def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _p
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C = 2 * P[3] * Q[3] * _d % _p
    D = 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s: int, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _recover_x(y: int, sign: int):
    if y >= _p:
        return None
    x2 = (y * y - 1) * _inv(_d * y * y + 1)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p != 0:
        x = x * _sqrt_m1 % _p
    if (x * x - x2) % _p != 0:
        return None
    if (x & 1) != sign:
        x = _p - x
    return x


_gy = 4 * _inv(5) % _p
_gx = _recover_x(_gy, 0)
_G = (_gx, _gy, 1, _gx * _gy % _p)


def _compress(P) -> bytes:
    zinv = _inv(P[2])
    x = P[0] * zinv % _p
    y = P[1] * zinv % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s: bytes):
    if len(s) != 32:
        raise ValueError("Ed25519 point must be 32 bytes")
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _p)


def _sha512_modq(s: bytes) -> int:
    return int.from_bytes(hashlib.sha512(s).digest(), "little") % _q


def _expand(secret: bytes):
    if len(secret) != 32:
        raise ValueError("Ed25519 secret key must be 32 bytes")
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


# ── public API ───────────────────────────────────────────────────────────


def generate_secret() -> bytes:
    """A fresh 32-byte secret key from the OS CSPRNG."""
    return secrets.token_bytes(32)


def _py_public_key(secret: bytes) -> bytes:
    a, _ = _expand(secret)
    return _compress(_mul(a, _G))


def _py_sign(secret: bytes, msg: bytes) -> bytes:
    a, prefix = _expand(secret)
    A = _compress(_mul(a, _G))
    r = _sha512_modq(prefix + msg)
    Rs = _compress(_mul(r, _G))
    h = _sha512_modq(Rs + A + msg)
    s = (r + h * a) % _q
    return Rs + int.to_bytes(s, 32, "little")


def _py_verify(public: bytes, msg: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    A = _decompress(public)
    if A is None:
        return False
    Rs = signature[:32]
    R = _decompress(Rs)
    if R is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _q:
        return False
    h = _sha512_modq(Rs + public + msg)
    return _equal(_mul(s, _G), _add(R, _mul(h, A)))


try:  # pragma: no cover - exercised only where the dependency is present
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _c

    BACKEND = "cryptography"

    def public_key(secret: bytes) -> bytes:
        return _c.Ed25519PrivateKey.from_private_bytes(secret).public_key().public_bytes_raw()

    def sign(secret: bytes, msg: bytes) -> bytes:
        return _c.Ed25519PrivateKey.from_private_bytes(secret).sign(msg)

    def verify(public: bytes, msg: bytes, signature: bytes) -> bool:
        if len(public) != 32 or len(signature) != 64:
            return False
        try:
            _c.Ed25519PublicKey.from_public_bytes(public).verify(signature, msg)
            return True
        except Exception:
            return False

except ImportError:
    BACKEND = "pure-python"
    public_key = _py_public_key
    sign = _py_sign
    verify = _py_verify
