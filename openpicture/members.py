"""Member conformance — spec §4 (container) and §7b (attachments).

`checks(path, manifest)` walks the archive at the byte level — local file
headers, extra-field records, timestamps, the end-of-central-directory
record — and the manifest's attachment declarations, and returns one
`(name, ok, detail)` per rule so a producer can see exactly which line of
the specification a file broke. `validate.validate` runs it for Full files;
it is also the reference behaviour for the copyable validator.

Everything here is standard library. `zipfile` is used only to enumerate
entries and read member bytes; every structural fact is re-read from the
raw headers, because that is where the rules live.
"""

from __future__ import annotations

import hashlib
import os
import re
import struct
import zipfile
from typing import Iterable, Mapping

from . import MANIFEST_MEMBER, container, embeddings, keyframes

__all__ = ["checks", "RESERVED_DIRS", "name_problems", "Check"]

Check = tuple[str, bool, str]

RESERVED_DIRS = ("embeddings", "keyframes", "extensions")
_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
_MAX_NAME = 255
_MAX_SEGMENT = 128
_ZIP64_LIMIT = 2**31 - 1
_DOS_EPOCH = (0x0021, 0x0000)  # 1980-01-01, 00:00:00
_LOCAL = struct.Struct("<4sHHHHHIIIHH")
_EOCD_SIG = b"PK\x05\x06"
_EOCD64_SIG = b"PK\x06\x06"
_EOCD64_LOC = b"PK\x06\x07"
_AES_EXTRA = 0x9901
_ZIP64_EXTRA = 0x0001


# ── names ──────────────────────────────────────────────────────────────


def name_problems(name: str) -> list[str]:
    """Every way a member name breaks §4.2 / §4.3 (top level)."""
    out: list[str] = []
    if len(name.encode("utf-8")) > _MAX_NAME:
        out.append(f"longer than {_MAX_NAME} bytes")
    if name.startswith("/"):
        out.append("leading /")
    if name.endswith("/"):
        out.append("directory entry")
    segments = name.split("/")
    for seg in segments:
        if seg == "":
            out.append("empty segment")
        elif seg in (".", ".."):
            out.append(f"segment {seg!r}")
        elif not _SEGMENT.match(seg):
            out.append(f"segment {seg!r} has characters outside [A-Za-z0-9._-]")
        elif len(seg.encode("utf-8")) > _MAX_SEGMENT:
            out.append(f"segment {seg!r} longer than {_MAX_SEGMENT} bytes")
    if name != MANIFEST_MEMBER:
        top = segments[0]
        if len(segments) == 1:
            out.append("top-level member; only manifest.json and reserved directories may appear there")
        elif top not in RESERVED_DIRS:
            out.append(f"top-level directory {top!r} is not reserved (use extensions/<reverse.dns>/)")
        elif top == "extensions" and (len(segments) < 3 or "." not in segments[1] or segments[1] != segments[1].lower()):
            out.append("extensions/ members need a lower-case reverse-DNS directory then a file")
    return out


# ── raw header walk ────────────────────────────────────────────────────


def _local_headers(raw: bytes, infos) -> dict[str, dict]:
    """Per member: the fields of its local header, decoded, plus extra records."""
    out: dict[str, dict] = {}
    for info in infos:
        h = info.header_offset
        if raw[h:h + 4] != b"PK\x03\x04" or h + 30 > len(raw):
            out[info.filename] = {"error": "local header signature missing"}
            continue
        (_, version, flags, method, dtime, ddate, crc, csize, usize, nlen, elen) = _LOCAL.unpack(raw[h:h + 30])
        extra = raw[h + 30 + nlen:h + 30 + nlen + elen]
        records = []
        i = 0
        while i + 4 <= len(extra):
            rid, rsize = struct.unpack("<HH", extra[i:i + 4])
            records.append((rid, rsize))
            i += 4 + rsize
        out[info.filename] = {
            "offset": h, "flags": flags, "method": method, "time": dtime, "date": ddate,
            "csize": csize, "usize": usize, "name_len": nlen, "extra_len": elen,
            "extra": records, "data_offset": h + 30 + nlen + elen, "central_extra": info.extra,
        }
    return out


def _eocd(raw: bytes) -> tuple[int, int] | None:
    """(offset of EOCD, comment length) or None."""
    idx = raw.rfind(_EOCD_SIG)
    if idx < 0 or idx + 22 > len(raw):
        return None
    (comment_len,) = struct.unpack("<H", raw[idx + 20:idx + 22])
    return idx, comment_len


# ── the checks ─────────────────────────────────────────────────────────


def checks(path: str | os.PathLike, manifest: Mapping) -> list[Check]:
    """Spec §4 and §7b, as `(name, ok, detail)` rows. Never raises for a bad
    archive; a file that is not a ZIP yields a single failing row."""
    with open(path, "rb") as fh:
        raw = fh.read()
    out: list[Check] = []
    add = lambda n, ok, d="": out.append((n, bool(ok), d))  # noqa: E731

    add("container.signature", raw[:4] == b"PK\x03\x04", "" if raw[:4] == b"PK\x03\x04" else "file does not start with PK\\x03\\x04")
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        add("container.readable", False, str(exc))
        return out
    with zf:
        infos = zf.infolist()
        heads = _local_headers(raw, infos)
        names = [i.filename for i in infos]

        # §4.1 profile
        bad_method = [n for n, h in heads.items() if h.get("method") not in (0, 8)]
        add("container.methods", not bad_method, "" if not bad_method else f"non STORE/DEFLATE: {bad_method}")
        encrypted = [n for n, h in heads.items() if h.get("flags", 0) & 0x0001 or any(r[0] == _AES_EXTRA for r in h.get("extra", []))]
        add("container.no-encryption", not encrypted, "" if not encrypted else f"encrypted: {encrypted}")
        patched = [n for n, h in heads.items() if h.get("flags", 0) & 0x0020]
        add("container.no-patched-data", not patched)
        descriptors = [n for n, h in heads.items() if h.get("flags", 0) & 0x0008]
        add("container.no-data-descriptors", not descriptors, "" if not descriptors else f"bit 3 set (SHOULD NOT): {descriptors}")
        eocd = _eocd(raw)
        add("container.no-comment", eocd is not None and eocd[1] == 0, "" if eocd and eocd[1] == 0 else "archive comment present or EOCD missing")

        # §4.6 no ZIP64
        z64 = []
        if _EOCD64_SIG in raw or _EOCD64_LOC in raw:
            z64.append("zip64 end-of-central-directory record")
        for n, h in heads.items():
            if any(r[0] == _ZIP64_EXTRA for r in h.get("extra", [])):
                z64.append(f"{n}: 0x0001 extra in local header")
            if h.get("csize") == 0xFFFFFFFF or h.get("usize") == 0xFFFFFFFF:
                z64.append(f"{n}: size sentinel")
            if h.get("usize", 0) > _ZIP64_LIMIT or h.get("csize", 0) > _ZIP64_LIMIT:
                z64.append(f"{n}: over 2 GiB")
        for info in infos:
            if _zip64_in(info.extra):
                z64.append(f"{info.filename}: 0x0001 extra in central directory")
        add("container.no-zip64", not z64, "; ".join(z64))
        add("container.entry-count", len(infos) < 65535, "" if len(infos) < 65535 else f"{len(infos)} entries")

        # §4.2 names, §4.3 top level
        dir_entries = [n for n in names if n.endswith("/")]
        add("names.no-directory-entries", not dir_entries, "" if not dir_entries else f"{dir_entries}")
        name_bad = {n: name_problems(n) for n in names if not n.endswith("/")}
        name_bad = {n: p for n, p in name_bad.items() if p}
        add("names.valid", not name_bad, "; ".join(f"{n}: {', '.join(p)}" for n, p in name_bad.items()))
        folded: dict[str, list[str]] = {}
        for n in names:
            folded.setdefault(n.lower(), []).append(n)
        dupes = [v for v in folded.values() if len(v) > 1]
        add("names.case-unique", not dupes, "" if not dupes else f"case collisions: {dupes}")

        # §4.3 manifest first
        add("manifest.present", MANIFEST_MEMBER in heads)
        if MANIFEST_MEMBER in heads:
            first = min(heads.items(), key=lambda kv: kv[1].get("offset", 1 << 62))[0]
            add("manifest.first", first == MANIFEST_MEMBER, "" if first == MANIFEST_MEMBER else f"first local header is {first!r}")

        # §4.5 timestamps
        stamped = [n for n, h in heads.items() if (h.get("date"), h.get("time")) != _DOS_EPOCH]
        stamped += [i.filename for i in infos if i.date_time != (1980, 1, 1, 0, 0, 0) and i.filename not in stamped]
        add("container.timestamps", not stamped, "" if not stamped else f"not 1980-01-01 00:00:00: {sorted(set(stamped))}")

        # §4.4 alignment
        misaligned = []
        for n, h in heads.items():
            if n.endswith(container.ALIGNED_SUFFIXES):
                if h.get("method") != 0:
                    misaligned.append(f"{n}: not STORED")
                elif h.get("data_offset", 1) % container.ALIGNMENT:
                    misaligned.append(f"{n}: data at {h['data_offset']}")
        add("members.aligned", not misaligned, "; ".join(misaligned))

        # §4.7 / §7b.2 declarations
        declared, owners = _declarations(manifest)
        multi = {n: o for n, o in owners.items() if len(o) > 1}
        add("attachments.single-owner", not multi, "" if not multi else f"declared by several runs: {multi}")
        members = [n for n in names if n != MANIFEST_MEMBER and not n.endswith("/")]
        undeclared = sorted(n for n in members if n not in declared)
        add("attachments.all-declared", not undeclared, "" if not undeclared else f"undeclared: {undeclared}")
        absent = sorted(n for n in declared if n not in members)
        add("attachments.all-present", not absent, "" if not absent else f"declared but absent: {absent}")
        for n in sorted(set(members) & set(declared)):
            meta = declared[n]
            data = zf.read(n)
            probs = []
            if not isinstance(meta, dict):
                probs.append("declaration is not an object")
            else:
                for key in ("sha256", "size", "media_type"):
                    if key not in meta:
                        probs.append(f"missing {key}")
                if isinstance(meta.get("sha256"), str) and meta["sha256"].lower() != hashlib.sha256(data).hexdigest():
                    probs.append("sha256 mismatch")
                if "size" in meta and meta["size"] != len(data):
                    probs.append(f"size {meta['size']} != {len(data)}")
                if isinstance(meta.get("media_type"), str) and "/" not in meta["media_type"]:
                    probs.append(f"media_type {meta['media_type']!r} is not a type/subtype")
            add(f"attachment.{n}", not probs, "; ".join(probs))
            if probs:
                continue
            # §7b.3 / §7b.4 kind-specific
            if n.startswith("embeddings/") or n.endswith(".safetensors"):
                if not n.endswith(".safetensors"):
                    add(f"embeddings.{n}", False, "embeddings/ members must be .safetensors")
                else:
                    if meta.get("media_type") != embeddings.MEDIA_TYPE:
                        add(f"embeddings.{n}.media_type", False, f"expected {embeddings.MEDIA_TYPE}")
                    ep = embeddings.problems(data, meta)
                    add(f"embeddings.{n}", not ep, "; ".join(ep))
            elif n.startswith("keyframes/"):
                kp = keyframes.problems(n, data, meta)
                add(f"still.{n}", not kp, "; ".join(kp))
    return out


def _zip64_in(extra: bytes) -> bool:
    i = 0
    while i + 4 <= len(extra):
        rid, rsize = struct.unpack("<HH", extra[i:i + 4])
        if rid == _ZIP64_EXTRA:
            return True
        i += 4 + rsize
    return False


def _declarations(manifest: Mapping) -> tuple[dict[str, object], dict[str, list[int]]]:
    """member -> declaration (first wins), member -> [run indexes that declare it]."""
    declared: dict[str, object] = {}
    owners: dict[str, list[int]] = {}
    runs = manifest.get("machine_intelligence")
    if isinstance(runs, list):
        for i, run in enumerate(runs):
            att = run.get("attachments") if isinstance(run, dict) else None
            if not isinstance(att, dict):
                continue
            for name, meta in att.items():
                owners.setdefault(name, []).append(i)
                declared.setdefault(name, meta)
    return declared, owners


def summary(rows: Iterable[Check]) -> str:
    rows = list(rows)
    bad = [r for r in rows if not r[1]]
    return f"{len(rows) - len(bad)} ok, {len(bad)} failing" + ("" if not bad else ": " + "; ".join(f"{n} ({d})" for n, _, d in bad))
