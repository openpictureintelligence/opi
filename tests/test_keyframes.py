import hashlib
import struct
import zipfile
import zlib
from pathlib import Path

import pytest

from openpicture import container, keyframes, sign, validate, ed25519, runs

EXAMPLE_FULL = Path(__file__).resolve().parent.parent / "examples" / "A001_C001.mov.full.opi"


@pytest.fixture(scope="module")
def real_webp() -> bytes:
    with zipfile.ZipFile(EXAMPLE_FULL) as zf:
        name = next(n for n in zf.namelist() if n.startswith("keyframes/"))
        return zf.read(name)


def _png(w, h):
    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _jpeg(w, h):
    # SOI, an APP0 segment to skip over, then SOF0 with height/width, then EOI.
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


def test_real_webp_from_example(real_webp):
    d = keyframes.describe(real_webp)
    assert d == {"media_type": "image/webp", "width": 512, "height": 288}


def test_vp8l_and_vp8x_headers():
    # VP8L: signature 0x2F then 14-bit width-1, 14-bit height-1 packed LE.
    bits = (511) | ((287) << 14)
    vp8l = b"RIFF" + struct.pack("<I", 30) + b"WEBP" + b"VP8L" + struct.pack("<I", 10) + b"\x2f" + bits.to_bytes(4, "little") + b"\0" * 5
    assert keyframes.describe(vp8l) == {"media_type": "image/webp", "width": 512, "height": 288}
    vp8x = b"RIFF" + struct.pack("<I", 30) + b"WEBP" + b"VP8X" + struct.pack("<I", 10) + b"\0" * 4 + (639).to_bytes(3, "little") + (359).to_bytes(3, "little") + b"\0" * 4
    assert keyframes.describe(vp8x) == {"media_type": "image/webp", "width": 640, "height": 360}


def test_png_and_jpeg():
    assert keyframes.describe(_png(7, 3)) == {"media_type": "image/png", "width": 7, "height": 3}
    assert keyframes.describe(_jpeg(512, 288)) == {"media_type": "image/jpeg", "width": 512, "height": 288}


@pytest.mark.parametrize("bad", [
    b"", b"GIF89a" + b"\0" * 20, b"RIFF\0\0\0\0WEBPXXXX" + b"\0" * 20,
    b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 5, b"\xff\xd8\xff\xd9", b"\x89PNG\r\n\x1a\n" + b"\0" * 4,
    b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 7 + b"\x00\x01\x2a" + b"\0" * 4,  # bad start code
])
def test_describe_rejects(bad):
    with pytest.raises(ValueError):
        keyframes.describe(bad)


def test_member_name():
    assert keyframes.member_name("shot_0001", 24) == "keyframes/shot_0001_0000024.webp"
    assert keyframes.member_name("r1/a", 0, "image/jpeg") == "keyframes/r1_a_0000000.jpg"
    with pytest.raises(ValueError):
        keyframes.member_name("x", -1)
    with pytest.raises(ValueError):
        keyframes.member_name("x", 1, "image/gif")


def test_attachment_entry(real_webp):
    e = keyframes.attachment_entry(real_webp, frame=24, t_s=1.001)
    assert e["sha256"] == hashlib.sha256(real_webp).hexdigest()
    assert e["size"] == len(real_webp) and e["media_type"] == "image/webp"
    assert e["width"] == 512 and e["height"] == 288 and e["frame"] == 24 and e["t_s"] == 1.001
    assert "frame" not in keyframes.attachment_entry(real_webp)


def test_full_opi_with_keyframe_validates(tmp_path, real_webp):
    name = keyframes.member_name("shot_0000", 24)
    manifest = {
        "opi": 0, "profile": "full",
        "media_binding": {"files": [{"role": "original", "name": "c.mov", "size": 1, "sha256": "0" * 64}]},
        "machine_intelligence": [{"run_id": runs.run_id("test:shots", "1", "0" * 64), "producer": "test:shots", "model_version": "1", "facets": {},
                                  "attachments": {name: keyframes.attachment_entry(real_webp, frame=24)}}],
    }
    sign.sign_run(manifest, 0, ed25519.generate_secret(), signer="urn:test")
    path = container.write_full(manifest, tmp_path / "c.mov.opi", {name: real_webp})
    report = validate.validate(path)
    assert report.ok, [c for c in report.checks if not c.ok]
    with zipfile.ZipFile(path) as zf:
        assert zf.getinfo(name).compress_type == zipfile.ZIP_STORED
