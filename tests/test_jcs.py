import json
import math

import pytest

from openpicture import jcs

# RFC 8785 Appendix B — ES6 number serialization samples (hex IEEE → text).
_RFC_NUMBERS = [
    ("0000000000000000", "0"),
    ("8000000000000000", "0"),
    ("0000000000000001", "5e-324"),
    ("8000000000000001", "-5e-324"),
    ("7fefffffffffffff", "1.7976931348623157e+308"),
    ("ffefffffffffffff", "-1.7976931348623157e+308"),
    ("4340000000000000", "9007199254740992"),
    ("c340000000000000", "-9007199254740992"),
    ("4430000000000000", "295147905179352830000"),
    ("7fffffffffffffff", None),  # NaN
    ("7ff0000000000000", None),  # Infinity
    ("44b52d02c7e14af5", "9.999999999999997e+22"),
    ("44b52d02c7e14af6", "1e+23"),
    ("44b52d02c7e14af7", "1.0000000000000001e+23"),
    ("444b1ae4d6e2ef4e", "999999999999999700000"),
    ("444b1ae4d6e2ef4f", "999999999999999900000"),
    ("444b1ae4d6e2ef50", "1e+21"),
    ("3eb0c6f7a0b5ed8c", "9.999999999999997e-7"),
    ("3eb0c6f7a0b5ed8d", "0.000001"),
    ("3eb0c6f7a0b5ed8e", "0.0000010000000000000002"),
    ("41b3de4355555553", "333333333.3333332"),
    ("41b3de4355555554", "333333333.33333325"),
    ("41b3de4355555555", "333333333.3333333"),
    ("41b3de4355555556", "333333333.3333334"),
    ("41b3de4355555557", "333333333.33333343"),
    ("becbf647612f3696", "-0.0000033333333333333333"),
    ("43143ff3c1cb0959", "1424953923781206.2"),
]


def _from_hex(h: str) -> float:
    import struct

    return struct.unpack(">d", bytes.fromhex(h))[0]


@pytest.mark.parametrize("hexval,expected", _RFC_NUMBERS)
def test_rfc8785_number_vectors(hexval, expected):
    x = _from_hex(hexval)
    if expected is None:
        with pytest.raises(ValueError):
            jcs.dumps(x)
    else:
        assert jcs.dumps(x) == expected


def test_rfc8785_appendix_a_sample():
    # RFC 8785 §3.2.3 / Appendix A: the canonical form of the spec's example.
    doc = json.loads(
        '{"numbers": [333333333.33333329, 1E30, 4.50, 2e-3, 0.000000000000000000000000001],'
        ' "string": "\\u20ac$\\u000F\\u000aA\'B\\u0022\\\\\\\\\\"\\/",'
        ' "literals": [null, true, false]}'
    )
    expected = (
        '{"literals":[null,true,false],'
        '"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
        '"string":"€$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'
    )
    assert jcs.dumps(doc) == expected


def test_key_order_is_utf16_not_codepoint():
    # U+FF5E (BMP) sorts before U+1F600 in UTF-16 (0xFF5E < 0xD83D), but after
    # it by code point. RFC 8785 §3.2.3 example ordering.
    doc = {"\U0001f600": 1, "～": 2, "a": 3, "A": 4, "": 5, "é": 6}
    out = jcs.dumps(doc)
    keys = [k for k in json.loads(out)]
    assert keys == ["", "A", "a", "é", "\U0001f600", "～"]


def test_ints_are_plain_and_rejects_non_string_keys():
    assert jcs.dumps({"n": 10**20}) == '{"n":100000000000000000000}'
    with pytest.raises(TypeError):
        jcs.dumps({1: "x"})


def test_roundtrip_is_json():
    doc = {"z": [1, 2.5, "x\ty", {"b": None, "a": True}], "a": -0.0}
    out = jcs.dumps(doc)
    back = json.loads(out)
    assert back["z"][2] == "x\ty"
    assert back["a"] == 0
    assert jcs.canonicalize(doc) == out.encode("utf-8")


def test_nan_rejected():
    with pytest.raises(ValueError):
        jcs.dumps([math.nan])
