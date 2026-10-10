"""The `.opi` container — one extension, two profiles.

**Core** is a UTF-8 JSON document. **Full** is a ZIP whose `manifest.json`
member is byte-for-byte the Core document, plus optional members:
`embeddings.bin`-style binaries stored *uncompressed and 64-byte aligned*
so a reader can `mmap` the archive and hand the slice to a tensor library
without copying, `keyframes/*` stills, and `extensions/<reverse.dns>/*`.

Readers never trust the extension. `detect()` looks at the first bytes:
`{` (after an optional BOM and whitespace) is Core, `PK\\x03\\x04` is Full.

Every write is atomic — temp file beside the target, fsync, rename — because
a half-written sidecar next to a client's master is worse than none.
"""

from __future__ import annotations

import io
import json
import os
import struct
import zipfile
from pathlib import Path
from typing import Iterable, Mapping

from . import MANIFEST_MEMBER

__all__ = [
    "ALIGNMENT",
    "ALIGNED_SUFFIXES",
    "MAX_MANIFEST_BYTES",
    "ManifestTooLarge",
    "PADDING_EXTRA_ID",
    "detect",
    "profile_of_members",
    "read_manifest",
    "member_data_offset",
    "write_core",
    "write_json",
    "write_full",
    "manifest_bytes",
    "atomic_write",
    "rewrite",
]

ALIGNMENT = 64
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
# Members with these suffixes are STORED and 64-byte aligned by default: raw
# binaries and safetensors, the two things a reader wants to mmap.
ALIGNED_SUFFIXES = (".bin", ".safetensors")
# ZIP "extra field" header id used for alignment padding. Private range;
# readers that don't know it skip it, which is what the ZIP spec promises.
PADDING_EXTRA_ID = 0x4F50  # 'OP'
_LOCAL_HEADER = struct.Struct("<4sHHHHHIIIHH")  # 30 bytes
_BOM = "﻿".encode("utf-8")


class ManifestTooLarge(ValueError):
    """Raised before parsing a manifest that exceeds the format size cap."""


# ── detection ──────────────────────────────────────────────────────────


def detect(source: str | os.PathLike | bytes) -> str | None:
    """`"core"`, `"full"`, or `None` when the bytes are neither.

    Only the head of the file is read. A ZIP is recognised by its local
    file header signature at offset 0 — an archive with prepended data or
    an empty archive (`PK\\x05\\x06`) is not a `.opi` and returns None.
    """
    if isinstance(source, (bytes, bytearray)):
        head = bytes(source[:64])
    else:
        with open(source, "rb") as fh:
            head = fh.read(64)
    if head.startswith(b"PK\x03\x04"):
        return "zip"
    if head.startswith(_BOM):
        head = head[len(_BOM):]
    if head.lstrip(b" \t\r\n").startswith(b"{"):
        return "json"
    return None


def profile_of_members(names: Iterable[str]) -> str:
    """`"core"` when the only file member is the manifest, else `"full"`.

    Directory entries do not count. This is the *content* profile; the
    manifest's declared `profile` must agree with it.
    """
    files = {n for n in names if not n.endswith("/")}
    return "core" if files <= {MANIFEST_MEMBER} else "full"


# ── reading ────────────────────────────────────────────────────────────


def read_manifest(path: str | os.PathLike) -> tuple[dict, str]:
    """The manifest dict and the *content* profile (`"core"` / `"full"`).

    A bare JSON file is read as Core (internal form). Raises `ValueError`
    for anything that is not a `.opi`, including a ZIP without
    `manifest.json` — that is the one required member.
    """
    form = detect(path)
    if form == "json":
        size = os.path.getsize(path)
        if size > MAX_MANIFEST_BYTES:
            raise ManifestTooLarge(
                f"manifest size {size} bytes exceeds {MAX_MANIFEST_BYTES} byte limit"
            )
        with open(path, "rb") as fh:
            raw = fh.read()
        return _parse(raw), "core"
    if form == "zip":
        with zipfile.ZipFile(path) as zf:
            try:
                info = zf.getinfo(MANIFEST_MEMBER)
            except KeyError:
                raise ValueError(f"{path}: ZIP without {MANIFEST_MEMBER}") from None
            if info.file_size > MAX_MANIFEST_BYTES:
                raise ManifestTooLarge(
                    f"manifest size {info.file_size} bytes exceeds {MAX_MANIFEST_BYTES} byte limit"
                )
            raw = zf.read(info)
            return _parse(raw), profile_of_members(zf.namelist())
    raise ValueError(f"{path}: not a .opi (neither ZIP nor JSON object)")


def _parse(raw: bytes) -> dict:
    text = raw.decode("utf-8")
    if text.startswith("﻿"):
        text = text[1:]
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise ValueError("manifest must be a JSON object")
    return doc


def member_data_offset(path: str | os.PathLike, name: str) -> int:
    """Byte offset of `name`'s data inside the archive, from the local header.

    Read from the *local* header, not the central directory: the two may
    carry different extra fields and the local one decides where the bytes
    are. This is what a zero-copy reader `mmap`s from.
    """
    with zipfile.ZipFile(path) as zf, open(path, "rb") as fh:
        info = zf.getinfo(name)
        fh.seek(info.header_offset)
        fields = _LOCAL_HEADER.unpack(fh.read(_LOCAL_HEADER.size))
        name_len, extra_len = fields[9], fields[10]
        return info.header_offset + _LOCAL_HEADER.size + name_len + extra_len


# ── writing ────────────────────────────────────────────────────────────


def manifest_bytes(manifest: Mapping) -> bytes:
    """The manifest serialization: readable JSON, key order preserved,
    trailing newline. These are the bytes of `manifest.json` in every
    `.opi`, Core or Full, and of the bare internal form."""
    text = json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def atomic_write(path: str | os.PathLike, data: bytes) -> Path:
    path = Path(path)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return path


def write_json(manifest: Mapping, path: str | os.PathLike) -> Path:
    """The bare-JSON internal form. Not a canonical `.opi`; see `write_core`."""
    return atomic_write(path, manifest_bytes(manifest))


def write_core(manifest: Mapping, path: str | os.PathLike) -> Path:
    """A Core-profile `.opi`: a ZIP whose only member is `manifest.json`."""
    return write_full(manifest, path, {})


def write_full(
    manifest: Mapping,
    path: str | os.PathLike,
    members: Mapping[str, bytes] | None = None,
    *,
    aligned: Iterable[str] | None = None,
) -> Path:
    """A `.opi` container: `manifest.json` first, then `members` in order.

    With no members this *is* the Core profile — `write_core` calls here.

    Members named in `aligned` (default: every `*.bin` / `*.safetensors`) are STORED with
    their data start padded to a 64-byte boundary. Everything else is
    STORED too except the manifest, which is DEFLATED — a long transcript
    compresses well and `unzip -p` does not care.
    """
    members = dict(members or {})
    if MANIFEST_MEMBER in members:
        raise ValueError(f"{MANIFEST_MEMBER} is written from `manifest`, not `members`")
    align = set(aligned) if aligned is not None else {n for n in members if n.endswith(ALIGNED_SUFFIXES)}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(_info(MANIFEST_MEMBER, zipfile.ZIP_DEFLATED), manifest_bytes(manifest))
        for name, data in members.items():
            info = _info(name, zipfile.ZIP_STORED)
            if name in align:
                info.extra = _padding(buf.tell(), name)
            zf.writestr(info, data)
    return atomic_write(path, buf.getvalue())


def _info(name: str, compression: int) -> zipfile.ZipInfo:
    # A fixed timestamp keeps the container reproducible: same manifest and
    # members, same bytes. ZIP's DOS epoch is 1980, so that is the floor.
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = compression
    info.create_system = 3  # unix
    info.external_attr = 0o644 << 16
    return info


def _padding(header_offset: int, name: str) -> bytes:
    """An extra field that lands the member's data on the next boundary."""
    base = header_offset + _LOCAL_HEADER.size + len(name.encode("utf-8"))
    pad = (-base) % ALIGNMENT
    if pad < 4:  # an extra field needs its 4-byte header
        pad += ALIGNMENT
    return struct.pack("<HH", PADDING_EXTRA_ID, pad - 4) + b"\0" * (pad - 4)


def rewrite(path: str | os.PathLike, manifest: Mapping) -> Path:
    """Replace the manifest of an existing `.opi`, keeping every member byte for byte.

    Core files stay Core; Full files are rebuilt with the same members and
    alignment recomputed. This is what `sign` and `annotate` use, so a Full
    file never has to be unpacked to be edited.
    """
    members: dict[str, bytes] = {}
    if detect(path) == "zip":
        with zipfile.ZipFile(path) as zf:
            members = {n: zf.read(n) for n in zf.namelist() if n != MANIFEST_MEMBER and not n.endswith("/")}
    if members:
        return write_full(manifest, path, members)
    return write_core(manifest, path)
