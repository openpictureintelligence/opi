"""Keyframe stills as members — `keyframes/<id>_<frame:07d>.webp`.

A still is the picture a judgment was made on. It travels in the Full
profile so a reviewer can see *why* a shot was called a close-up without
opening the master. A8 §4: WebP lossy q≈80, 512 px long edge, sRGB,
metadata stripped; JPEG only when a consumer profile asks for it; PNG
accepted on read. No decoding happens here — only enough header parsing to
confirm the magic and read the dimensions, so the manifest can carry
`width`/`height`/`media_type` and a validator can check them.
"""

from __future__ import annotations

import hashlib
import struct

__all__ = ["describe", "member_name", "attachment_entry", "EXTENSIONS", "STILL_TYPES",
           "MAX_LONG_EDGE", "MAX_LONG_EDGE_HARD", "metadata_chunks", "problems"]

EXTENSIONS = {"image/webp": ".webp", "image/jpeg": ".jpg", "image/png": ".png"}
STILL_TYPES = ("image/webp", "image/jpeg")   # §7b.4: what a .opi may carry
MAX_LONG_EDGE = 512        # SHOULD
MAX_LONG_EDGE_HARD = 2048  # MUST


def member_name(prefix: str, frame: int, media_type: str = "image/webp") -> str:
    """`keyframes/<prefix>_<frame:07d>.<ext>` — zero-padded so a directory
    listing sorts in frame order."""
    if media_type not in EXTENSIONS:
        raise ValueError(f"unsupported still type {media_type!r}")
    safe = prefix.strip().replace("/", "_").replace("\\", "_")
    if not safe or frame < 0:
        raise ValueError("member_name needs a non-empty prefix and a frame >= 0")
    return f"keyframes/{safe}_{frame:07d}{EXTENSIONS[media_type]}"


def describe(data: bytes | bytearray | memoryview) -> dict:
    """`{"media_type", "width", "height"}` from the header bytes.

    Raises `ValueError` when the bytes are not a WebP, JPEG or PNG we can
    read. Truncated files raise too — a still whose size cannot be read is
    not one worth declaring.
    """
    b = bytes(memoryview(data)[:64])
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return _webp(bytes(data))
    if b[:2] == b"\xff\xd8":
        return _jpeg(bytes(data))
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return _png(b)
    raise ValueError("not a WebP, JPEG or PNG")


def _webp(d: bytes) -> dict:
    if len(d) < 30:
        raise ValueError("webp: truncated")
    chunk = d[12:16]
    if chunk == b"VP8 ":
        # Lossy: 10-byte frame header after the chunk header; 3-byte start
        # code 9d 01 2a then 14-bit width and height (top 2 bits are scale).
        if d[23:26] != b"\x9d\x01\x2a":
            raise ValueError("webp: VP8 start code missing")
        w, h = struct.unpack("<HH", d[26:30])
        return {"media_type": "image/webp", "width": w & 0x3FFF, "height": h & 0x3FFF}
    if chunk == b"VP8L":
        if d[20] != 0x2F:
            raise ValueError("webp: VP8L signature missing")
        bits = int.from_bytes(d[21:25], "little")
        return {"media_type": "image/webp", "width": (bits & 0x3FFF) + 1,
                "height": ((bits >> 14) & 0x3FFF) + 1}
    if chunk == b"VP8X":
        w = int.from_bytes(d[24:27], "little") + 1
        h = int.from_bytes(d[27:30], "little") + 1
        return {"media_type": "image/webp", "width": w, "height": h}
    raise ValueError(f"webp: unknown first chunk {chunk!r}")


_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _jpeg(d: bytes) -> dict:
    i = 2
    n = len(d)
    while i + 4 <= n:
        if d[i] != 0xFF:
            raise ValueError("jpeg: marker expected")
        marker = d[i + 1]
        if marker == 0xFF:  # fill byte
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:  # standalone
            i += 2
            continue
        if marker == 0xD9 or marker == 0xDA:
            break  # EOI / SOS before any SOF
        (seglen,) = struct.unpack(">H", d[i + 2:i + 4])
        if marker in _SOF:
            if i + 9 > n:
                raise ValueError("jpeg: truncated SOF")
            h, w = struct.unpack(">HH", d[i + 5:i + 9])
            return {"media_type": "image/jpeg", "width": w, "height": h}
        i += 2 + seglen
    raise ValueError("jpeg: no SOF marker found")


def _png(b: bytes) -> dict:
    if len(b) < 24 or b[12:16] != b"IHDR":
        raise ValueError("png: IHDR missing")
    w, h = struct.unpack(">II", b[16:24])
    return {"media_type": "image/png", "width": w, "height": h}


def attachment_entry(data: bytes, *, frame: int | None = None, t_s: float | None = None,
                     shot_id: str | None = None) -> dict:
    """The value for a run's `attachments[<member>]`: hash, size, type,
    dimensions, and where in the media the still came from."""
    entry = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), **describe(data)}
    if frame is not None:
        entry["frame"] = int(frame)
    if t_s is not None:
        entry["t_s"] = float(t_s)
    if shot_id is not None:
        entry["shot_id"] = str(shot_id)
    return entry


# ── §7b.4 conformance ────────────────────────────────────────────────────

_WEBP_FORBIDDEN = {b"EXIF": "EXIF", b"XMP ": "XMP", b"ICCP": "ICC profile", b"ANIM": "animation", b"ANMF": "animation"}
_JPEG_FORBIDDEN = {0xE1: "APP1 (Exif/XMP)", 0xED: "APP13 (IPTC)", 0xE2: "APP2 (ICC)"}


def metadata_chunks(data: bytes) -> list[str]:
    """Names of forbidden metadata/animation payloads present in a still:
    WebP RIFF chunks `EXIF`/`XMP `/`ICCP`/`ANIM`/`ANMF`, JPEG APP1/APP13/APP2.
    Empty means the still is stripped as §7b.4 requires."""
    d = bytes(data)
    found: list[str] = []
    if d[:4] == b"RIFF" and d[8:12] == b"WEBP":
        i = 12
        while i + 8 <= len(d):
            fourcc = d[i:i + 4]
            (size,) = struct.unpack("<I", d[i + 4:i + 8])
            if fourcc in _WEBP_FORBIDDEN:
                found.append(_WEBP_FORBIDDEN[fourcc])
            i += 8 + size + (size & 1)
    elif d[:2] == b"\xff\xd8":
        i = 2
        while i + 4 <= len(d) and d[i] == 0xFF:
            marker = d[i + 1]
            if marker == 0xDA or marker == 0xD9:
                break
            if marker == 0xFF:
                i += 1
                continue
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            (seglen,) = struct.unpack(">H", d[i + 2:i + 4])
            if marker in _JPEG_FORBIDDEN:
                found.append(_JPEG_FORBIDDEN[marker])
            i += 2 + seglen
    return found


def problems(name: str, data: bytes, declared: dict | None = None) -> list[str]:
    """Every way a still fails §7b.4; empty means conformant."""
    out: list[str] = []
    try:
        info = describe(data)
    except ValueError as exc:
        return [f"still: {exc}"]
    if info["media_type"] not in STILL_TYPES:
        out.append(f"{info['media_type']} is not permitted in keyframes/ (webp or jpeg)")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    want = EXTENSIONS.get(info["media_type"], "").lstrip(".")
    if ext not in (want, "jpeg" if want == "jpg" else want):
        out.append(f"extension .{ext} does not match {info['media_type']}")
    if max(info["width"], info["height"]) > MAX_LONG_EDGE_HARD:
        out.append(f"long edge {max(info['width'], info['height'])} exceeds {MAX_LONG_EDGE_HARD}")
    for chunk in metadata_chunks(data):
        out.append(f"contains {chunk}; stills must be stripped")
    base = name.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0]
    frame_txt = stem.rsplit("_", 1)[-1] if "_" in stem else ""
    frame_in_name = int(frame_txt) if frame_txt.isdigit() and len(frame_txt) == 7 else None
    if frame_in_name is None:
        out.append("name must end in _<frame:07d>")
    if declared:
        for k in ("width", "height"):
            if declared.get(k) != info[k]:
                out.append(f"attachment {k}={declared.get(k)!r} disagrees with image ({info[k]})")
        if declared.get("media_type") not in (None, info["media_type"]):
            out.append(f"attachment media_type {declared.get('media_type')!r} disagrees with image ({info['media_type']})")
        if "frame" in declared and frame_in_name is not None and declared["frame"] != frame_in_name:
            out.append(f"attachment frame={declared['frame']} disagrees with name ({frame_in_name})")
    return out
