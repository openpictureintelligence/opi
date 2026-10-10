"""Spec §4 (container) and §7b (attachments and members) — the byte-level
rules, the declaration rules, and the embeddings / stills member formats,
proven against the committed vectors in vectors/members/."""

import json
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from openpicture import container, embeddings, keyframes, members

ROOT = Path(__file__).resolve().parent.parent
VEC = ROOT / "vectors" / "members"
sys.path.insert(0, str(VEC))
import make_vectors  # noqa: E402

EXPECTED = json.loads((VEC / "expected.json").read_text())


def _failing(rows):
    return {n: d for n, ok, d in rows if not ok}


# ── vectors ────────────────────────────────────────────────────────────


def test_vectors_are_current():
    r = subprocess.run([sys.executable, str(VEC / "make_vectors.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_valid_vector_passes_every_check():
    path = VEC / EXPECTED["valid"]["file"]
    manifest, profile = container.read_manifest(path)
    assert profile == "full"
    rows = members.checks(path, manifest)
    assert not _failing(rows), _failing(rows)
    for name, off in EXPECTED["valid"]["data_offsets"].items():
        assert container.member_data_offset(path, name) == off
        if name.endswith(".safetensors"):
            assert off % 64 == 0
    # buffer of the safetensors member is 64-aligned in the *file*
    with zipfile.ZipFile(path) as zf:
        data = zf.read("embeddings/unit-test.safetensors")
    (n,) = struct.unpack("<Q", data[:8])
    assert (EXPECTED["valid"]["data_offsets"]["embeddings/unit-test.safetensors"] + 8 + n) % 64 == 0


@pytest.mark.parametrize("fname", sorted(EXPECTED["cases"]))
def test_each_failure_case_trips_its_named_check(fname):
    case = EXPECTED["cases"][fname]
    path = VEC / fname
    manifest, _ = container.read_manifest(path)
    bad = _failing(members.checks(path, manifest))
    assert case["must_fail"] in bad, (case, bad)


def test_unzip_p_works_on_the_valid_vector():
    import shutil
    if shutil.which("unzip") is None:
        pytest.skip("no unzip")
    out = subprocess.run(["unzip", "-p", str(VEC / EXPECTED["valid"]["file"]), "manifest.json"], capture_output=True)
    assert out.returncode == 0 and json.loads(out.stdout)["opi"] == 0


# ── names ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", [
    "manifest.json", "embeddings/clip-vit-b32.safetensors", "keyframes/s0_0000024.webp",
    "extensions/org.example.tool/notes.txt", "extensions/com.example/deep/er/x.bin",
])
def test_good_names(name):
    assert members.name_problems(name) == []


@pytest.mark.parametrize("name,fragment", [
    ("/embeddings/x.safetensors", "leading /"),
    ("embeddings//x.safetensors", "empty segment"),
    ("embeddings/../x.safetensors", "'..'"),
    ("embeddings/x y.safetensors", "outside"),
    ("thumbnails/x.webp", "not reserved"),
    ("stray.txt", "top-level member"),
    ("extensions/notes.txt", "reverse-DNS"),
    ("extensions/Org.Example/notes.txt", "reverse-DNS"),
    ("keyframes/" + "a" * 130 + ".webp", "longer than 128"),
    ("embeddings/x.safetensors/", "directory entry"),
])
def test_bad_names(name, fragment):
    probs = members.name_problems(name)
    assert any(fragment in p for p in probs), probs


# ── embeddings member (§7b.3) ──────────────────────────────────────────


def test_pack_vectors_layout_and_metadata():
    rows = [[0.6, 0.8, 0.0], [0.0, 0.0, 1.0]]
    data = embeddings.pack_vectors(rows, 3, model="m", model_version="v", spans_ms=[(0, 10), (10, 20)])
    meta, tensors = embeddings.unpack(data)
    assert set(embeddings.REQUIRED_METADATA) <= set(meta)
    assert meta["opi.dim"] == "3" and meta["opi.dtype"] == "F16" and meta["opi.normalized"] == "l2"
    assert tensors["vectors"][0] == "F16" and tensors["vectors"][1] == [2, 3]
    assert tensors["spans"][0] == "I64" and tensors["spans"][1] == [2, 2]
    (n,) = struct.unpack("<Q", data[:8])
    assert (8 + n) % 64 == 0
    # vectors is first in the buffer
    header = json.loads(data[8:8 + n].decode())
    assert header["vectors"]["data_offsets"][0] == 0
    assert embeddings.problems(data) == []
    entry = embeddings.attachment_entry(data, rows="shots")
    assert entry["dim"] == 3 and entry["count"] == 2 and entry["dtype"] == "F16"
    assert entry["model"] == "m" and entry["rows"] == "shots" and entry["media_type"] == embeddings.MEDIA_TYPE
    assert embeddings.problems(data, entry) == []
    assert "disagrees" in embeddings.problems(data, {**entry, "dim": 7})[0]


def test_pack_vectors_quantized_requires_scale_and_zero_point():
    with pytest.raises(ValueError):
        embeddings.pack_vectors([[1, 2], [3, 4]], 2, model="m", model_version="v", dtype="I8")
    data = embeddings.pack_vectors([[1, 2], [3, 4]], 2, model="m", model_version="v", dtype="I8",
                                   normalized="none", scale=[0.1], zero_point=[0.0])
    assert embeddings.problems(data) == []
    with pytest.raises(ValueError):
        embeddings.pack_vectors([[1, 2, 3]], 2, model="m", model_version="v")
    with pytest.raises(ValueError):
        embeddings.pack_vectors([[1.0]], 1, model="m", model_version="v", dtype="F64")


def test_problems_names_every_missing_rule():
    legacy = embeddings.pack({"embeddings": ([1, 2], "F16", [1.0, 0.0])}, {"producer": "x"})
    probs = embeddings.problems(legacy)
    assert any("'vectors' missing" in p for p in probs)
    bad_meta = embeddings.pack({"vectors": ([1, 2], "F16", [1.0, 0.0])}, {"opi.dim": "9"})
    probs = embeddings.problems(bad_meta)
    assert any("opi.dim '9' != vectors dim 2" in p for p in probs)
    assert sum("missing" in p for p in probs) == len(embeddings.REQUIRED_METADATA) - 1
    not_first = embeddings.pack({"spans": ([1, 2], "I64", [0, 1]), "vectors": ([1, 2], "F16", [1.0, 0.0])})
    assert any("not the first" in p for p in embeddings.problems(not_first))
    assert embeddings.problems(b"\0" * 3)[0].startswith("safetensors")


# ── stills (§7b.4) ─────────────────────────────────────────────────────


def test_still_metadata_detection_and_problems():
    good = make_vectors.WEBP_1X1
    assert keyframes.metadata_chunks(good) == []
    assert keyframes.problems("keyframes/s0_0000024.webp", good) == []
    exif = make_vectors._webp_with_chunk(good, b"EXIF", b"\0" * 8)
    assert keyframes.metadata_chunks(exif) == ["EXIF"]
    assert any("stripped" in p for p in keyframes.problems("keyframes/s0_0000024.webp", exif))
    anim = make_vectors._webp_with_chunk(good, b"ANIM", b"\0" * 6)
    assert "animation" in keyframes.metadata_chunks(anim)
    # extension must match type; frame must be in the name; dims must agree
    assert any("extension" in p for p in keyframes.problems("keyframes/s0_0000024.jpg", good))
    assert any("_<frame:07d>" in p for p in keyframes.problems("keyframes/s0.webp", good))
    assert any("width" in p for p in keyframes.problems("keyframes/s0_0000024.webp", good, {"width": 9, "height": 1}))
    assert any("frame=" in p for p in keyframes.problems("keyframes/s0_0000024.webp", good, {"width": 1, "height": 1, "frame": 3}))
    entry = keyframes.attachment_entry(good, frame=24, t_s=1.001, shot_id="s0")
    assert entry["shot_id"] == "s0" and entry["width"] == 1 and entry["media_type"] == "image/webp"


def test_jpeg_app1_is_detected():
    # SOI, APP1 (Exif) segment, SOF0 1x1, EOI
    app1 = b"\xff\xe1" + struct.pack(">H", 8) + b"Exif\0\0"
    sof = b"\xff\xc0" + struct.pack(">H", 11) + b"\x08" + struct.pack(">HH", 1, 1) + b"\x01\x01\x11\x00"
    jpg = b"\xff\xd8" + app1 + sof + b"\xff\xd9"
    assert keyframes.metadata_chunks(jpg) == ["APP1 (Exif/XMP)"]
    assert keyframes.describe(jpg) == {"media_type": "image/jpeg", "width": 1, "height": 1}
    assert any("stripped" in p for p in keyframes.problems("keyframes/s0_0000001.jpg", jpg))


# ── checks on a hand-made file ─────────────────────────────────────────


def test_checks_on_a_non_zip_reports_not_raises(tmp_path):
    p = tmp_path / "x.opi"
    p.write_bytes(b"not a zip at all")
    rows = members.checks(p, {})
    assert rows[0][0] == "container.signature" and not rows[0][1]
    assert any(n == "container.readable" and not ok for n, ok, _ in rows)


def test_summary_line():
    assert members.summary([("a", True, ""), ("b", False, "why")]) == "1 ok, 1 failing: b (why)"
