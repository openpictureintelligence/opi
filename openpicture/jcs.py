"""RFC 8785 — JSON Canonicalization Scheme, standard library only.

Signing JSON requires that two parties serialize the same data to the same
bytes. `json.dumps(sort_keys=True)` is close but not RFC 8785: Python sorts
keys by code point where JCS sorts by UTF-16 code unit, and Python formats
floats (`1e+16`, `1e-05`) where ECMAScript would write `10000000000000000`
and `0.00001`. This module does exactly what the RFC says and nothing else.

Constraints the RFC imposes on the *data*, enforced here by raising:
`NaN` and infinities are not JSON; keys must be strings; the top-level
value may be anything JSON allows.
"""

from __future__ import annotations

import decimal
import math
from typing import Any

__all__ = ["canonicalize", "dumps"]

_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def canonicalize(value: Any) -> bytes:
    """The RFC 8785 canonical UTF-8 encoding of `value`."""
    return dumps(value).encode("utf-8")


def dumps(value: Any) -> str:
    out: list[str] = []
    _emit(value, out)
    return "".join(out)


def _emit(value: Any, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, int):
        out.append(str(value))
    elif isinstance(value, float):
        out.append(_number(value))
    elif isinstance(value, str):
        out.append(_string(value))
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for i, item in enumerate(value):
            if i:
                out.append(",")
            _emit(item, out)
        out.append("]")
    elif isinstance(value, dict):
        out.append("{")
        for i, key in enumerate(sorted(value, key=_utf16_key)):
            if not isinstance(key, str):
                raise TypeError(f"JSON object keys must be str, got {type(key).__name__}")
            if i:
                out.append(",")
            out.append(_string(key))
            out.append(":")
            _emit(value[key], out)
        out.append("}")
    else:
        raise TypeError(f"{type(value).__name__} is not JSON-serializable")


def _utf16_key(key: object) -> bytes:
    # RFC 8785 §3.2.3: sort by UTF-16 code units. Big-endian UTF-16 bytes
    # compare in exactly that order.
    if not isinstance(key, str):
        raise TypeError(f"JSON object keys must be str, got {type(key).__name__}")
    return key.encode("utf-16-be")


def _string(s: str) -> str:
    out = ['"']
    for ch in s:
        esc = _ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
        elif ch < " ":
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _number(x: float) -> str:
    """ECMAScript `Number::toString`, which RFC 8785 §3.2.2.3 adopts."""
    if math.isnan(x) or math.isinf(x):
        raise ValueError("NaN and Infinity are not JSON values")
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    # repr() is the shortest round-tripping decimal, which is the digit
    # string ECMAScript specifies; only the layout of those digits differs.
    digits_tuple, exp = _shortest_digits(abs(x))
    digits = "".join(map(str, digits_tuple))
    k = len(digits)
    n = exp + k  # value = 0.digits × 10^n
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        esign = "+" if e >= 0 else "-"
        mant = digits if k == 1 else digits[0] + "." + digits[1:]
        body = f"{mant}e{esign}{abs(e)}"
    return sign + body


def _shortest_digits(x: float) -> tuple[tuple[int, ...], int]:
    d = decimal.Decimal(repr(x))
    _, digits, exp = d.as_tuple()
    digits = list(digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exp += 1
    return tuple(digits), exp
