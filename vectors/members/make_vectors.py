"""Build the §4 / §7b member vectors — a minimal valid Full file plus the
named failure cases, each a small `.opi` produced by breaking one rule.

    python vectors/members/make_vectors.py          # (re)write the files
    python vectors/members/make_vectors.py --check  # exit 1 if stale

Deterministic: fixed key, fixed timestamps, fixed bytes. `expected.json`
records the data offsets of the valid file and, per failure case, the
check name that must fail. `tests/test_members.py` consumes both.
"""

from __future__ import annotations

import hashlib
import io
import json
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from openpicture import MANIFEST_MEMBER, container, ed25519, embeddings, keyframes, runs as opi_runs, sign  # noqa: E402

HERE = Path(__file__).resolve().parent
SECRET = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")  # RFC 8032 test 1

# A real 1x1 lossy WebP (VP8), metadata-free, 36 bytes of payload.
WEBP_1X1 = bytes.fromhex(
    "52494646" "24000000" "57454250"                    # RIFF size WEBP
    "56503820" "18000000"                               # 'VP8 ' 24
    "3001009d012a0100010002003425a40003700000feFB9400"      # frame header + minimal data (24 bytes)
)


def _vectors_member() -> bytes:
    rows = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]
    return embeddings.pack_vectors(rows, 4, model="unit-test", model_version="1", dtype="F16",
                                   normalized="l2", scope="shot",
                                   spans_ms=[(0, 1000), (1000, 2000), (2000, 3000)])


def _manifest(members: dict[str, bytes], *, extra_run_owner: bool = False) -> dict:
    producer = "vectors:members"
    model_version = "1"
    media_sha256 = hashlib.sha256(b"abc").hexdigest()
    m = {
        "opi": 0, "profile": "full",
        "media_binding": {
            "timecode": {"start": "00:00:00:00", "rate": {"num": 24000, "den": 1001}, "drop_frame": False},
            "files": [{"role": "original", "name": "clip.mov", "size": 3,
                       "sha256": media_sha256}],
        },
        "machine_intelligence": [{
            "run_id": opi_runs.run_id(producer, model_version, media_sha256),
            "producer": producer, "model_version": model_version,
            "facets": {"shots": [
                {"idx": 0, "confidence": None, "span": {"frame_in": 0, "frame_out": 1}},
                {"idx": 1, "confidence": None, "span": {"frame_in": 1, "frame_out": 2}},
                {"idx": 2, "confidence": None, "span": {"frame_in": 2, "frame_out": 3}},
            ]},
            "attachments": {},
        }],
        "editorial_annotations": {},
    }
    att = m["machine_intelligence"][0]["attachments"]
    for name, data in members.items():
        if name.startswith("embeddings/"):
            att[name] = embeddings.attachment_entry(data, rows="shots")
        elif name.startswith("keyframes/"):
            att[name] = keyframes.attachment_entry(data, frame=24, t_s=1.001, shot_id="s0")
        else:
            att[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                         "media_type": "application/octet-stream"}
    if extra_run_owner:
        duplicate_producer = "vectors:duplicate"
        m["machine_intelligence"].append({
            "run_id": opi_runs.run_id(duplicate_producer, model_version, media_sha256),
            "producer": duplicate_producer, "model_version": model_version,
            "facets": {}, "attachments": dict(att),
        })
    for i in range(len(m["machine_intelligence"])):
        sign.sign_run(m, i, SECRET, signer="urn:opi:vectors", signed_at="2026-01-01T00:00:00+00:00")
    return m


def _write(name: str, manifest: dict, members: dict[str, bytes], **kw) -> Path:
    path = HERE / name
    container.write_full(manifest, path, members, **kw)
    return path


def _raw_zip(name: str, entries: list[tuple[zipfile.ZipInfo, bytes]], comment: bytes = b"") -> Path:
    """Hand-built archive for cases the reference writer refuses to produce."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for info, data in entries:
            zf.writestr(info, data)
        if comment:
            zf.comment = comment
    path = HERE / name
    path.write_bytes(buf.getvalue())
    return path


def build() -> dict:
    vec = _vectors_member()
    still_name = keyframes.member_name("s0", 24)
    good_members = {"embeddings/unit-test.safetensors": vec, still_name: WEBP_1X1,
                    "extensions/org.example.tool/notes.txt": b"hello\n"}
    expected: dict = {"valid": {}, "cases": {}}

    good = _write("valid-full.opi", _manifest(good_members), good_members)
    expected["valid"]["file"] = good.name
    expected["valid"]["data_offsets"] = {n: container.member_data_offset(good, n) for n in good_members}
    expected["valid"]["sha256"] = hashlib.sha256(good.read_bytes()).hexdigest()

    def case(fname: str, must_fail: str, why: str):
        expected["cases"][fname] = {"must_fail": must_fail, "why": why}

    # 1. undeclared member
    m = _manifest({"embeddings/unit-test.safetensors": vec})
    _write("case-undeclared.opi", m, {"embeddings/unit-test.safetensors": vec, "extensions/org.example.tool/x.bin": b"\0" * 64})
    case("case-undeclared.opi", "attachments.all-declared", "member present in the archive, absent from every run's attachments (§4.7)")

    # 2. bad name: top-level stray file
    m = _manifest({"stray.txt": b"x"})
    _write("case-bad-name.opi", m, {"stray.txt": b"x"})
    case("case-bad-name.opi", "names.valid", "top-level member other than manifest.json (§4.3)")

    # 3. misaligned safetensors (written with alignment disabled)
    m = _manifest({"embeddings/unit-test.safetensors": vec})
    _write("case-misaligned.opi", m, {"embeddings/unit-test.safetensors": vec}, aligned=set())
    case("case-misaligned.opi", "members.aligned", "safetensors member STORED but data offset not ≡ 0 mod 64 (§4.4)")

    # 4. EXIF chunk in a WebP still
    exif_webp = _webp_with_chunk(WEBP_1X1, b"EXIF", b"\0" * 8)
    members = {still_name: exif_webp}
    m = _manifest(members)
    _write("case-exif-still.opi", m, members)
    case("case-exif-still.opi", f"still.{still_name}", "WebP carries an EXIF chunk; stills must be stripped (§7b.4)")

    # 5. ZIP64 record present (hand-built with force_zip64)
    zi = zipfile.ZipInfo(MANIFEST_MEMBER, (1980, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
    m = _manifest({})
    manifest_bytes = container.manifest_bytes(m)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(zi, manifest_bytes)
        z = zipfile.ZipInfo("extensions/org.example.tool/big.txt", (1980, 1, 1, 0, 0, 0)); z.compress_type = zipfile.ZIP_STORED
        with zf.open(z, "w", force_zip64=True) as fh:
            fh.write(b"tiny")
    (HERE / "case-zip64.opi").write_bytes(buf.getvalue())
    case("case-zip64.opi", "container.no-zip64", "a ZIP64 extra record (0x0001) in a header (§4.6)")

    # 6. archive comment + wrong timestamps
    zi = zipfile.ZipInfo(MANIFEST_MEMBER, (2024, 5, 6, 7, 8, 9)); zi.compress_type = zipfile.ZIP_STORED
    _raw_zip("case-comment-timestamps.opi", [(zi, manifest_bytes)], comment=b"made by hand")
    case("case-comment-timestamps.opi", "container.no-comment", "archive comment present (§4.1); timestamps also fail §4.5")

    # 7. manifest not first
    m = _manifest({"extensions/org.example.tool/notes.txt": b"hello\n"})
    a = zipfile.ZipInfo("extensions/org.example.tool/notes.txt", (1980, 1, 1, 0, 0, 0)); a.compress_type = zipfile.ZIP_STORED
    b = zipfile.ZipInfo(MANIFEST_MEMBER, (1980, 1, 1, 0, 0, 0)); b.compress_type = zipfile.ZIP_DEFLATED
    _raw_zip("case-manifest-not-first.opi", [(a, b"hello\n"), (b, container.manifest_bytes(m))])
    case("case-manifest-not-first.opi", "manifest.first", "manifest.json is not the first local header (§4.3)")

    # 8. declared by two runs
    members = {"embeddings/unit-test.safetensors": vec}
    _write("case-two-owners.opi", _manifest(members, extra_run_owner=True), members)
    case("case-two-owners.opi", "attachments.single-owner", "the same member declared by two runs (§7b.1)")

    # 9. embeddings member missing required metadata / wrong tensor name
    legacy = embeddings.pack({"embeddings": ([3, 4], "F16", [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0])},
                             {"producer": "x"})
    members = {"embeddings/legacy.safetensors": legacy}
    _write("case-legacy-embeddings.opi", _manifest(members), members)
    case("case-legacy-embeddings.opi", "embeddings.embeddings/legacy.safetensors",
         "no 'vectors' tensor and no opi.* metadata (§7b.3)")

    # 10. case-insensitive name collision
    members = {"extensions/org.example.tool/A.txt": b"a", "extensions/org.example.tool/a.txt": b"b"}
    _write("case-case-collision.opi", _manifest(members), members)
    case("case-case-collision.opi", "names.case-unique", "two names differing only in ASCII case (§4.2)")

    (HERE / "expected.json").write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
    return expected


def _webp_with_chunk(webp: bytes, fourcc: bytes, payload: bytes) -> bytes:
    body = webp[12:] + fourcc + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) & 1 else b"")
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body


def main(argv: list[str]) -> int:
    before = {p.name: p.read_bytes() for p in HERE.glob("*.opi")}
    before_json = (HERE / "expected.json").read_text() if (HERE / "expected.json").exists() else ""
    build()
    if "--check" in argv:
        after = {p.name: p.read_bytes() for p in HERE.glob("*.opi")}
        stale = after != before or (HERE / "expected.json").read_text() != before_json
        # restore nothing: the rebuild is deterministic; a difference means the sources moved
        print("vectors stale" if stale else "vectors up to date")
        return 1 if stale else 0
    print(f"wrote {len(list(HERE.glob('*.opi')))} vector files + expected.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
