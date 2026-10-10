import hashlib
import json
import struct

import pytest

from openpicture import container, embeddings, sign, validate, ed25519, runs


def _vec(n, d, seed=1):
    return [((i * 7919 + seed) % 1000) / 1000.0 - 0.5 for i in range(n * d)]


def test_pack_layout_is_valid_safetensors_and_64_aligned():
    vals = _vec(3, 4)
    data = embeddings.pack(
        {"m/frames": ((3, 4), "F32", vals), "m/frame_index": ((3,), "I64", [0, 24, 48])},
        {"model": "m", "dim": "4", "normalized": "l2"},
    )
    (n,) = struct.unpack("<Q", data[:8])
    assert (8 + n) % 64 == 0                      # buffer starts 64-aligned
    header = json.loads(data[8:8 + n])
    assert header["__metadata__"] == {"model": "m", "dim": "4", "normalized": "l2"}
    assert header["m/frames"] == {"dtype": "F32", "shape": [3, 4], "data_offsets": [0, 48]}
    assert header["m/frame_index"]["data_offsets"] == [48, 72]
    assert data[8 + n - 1:8 + n] in (b" ", b"}")  # space padding only
    assert len(data) == 8 + n + 72


def test_unpack_round_trip_zero_copy():
    vals = _vec(2, 8)
    data = embeddings.pack({"m/frames": ((2, 8), "F16", vals), "m/idx": ((2,), "I64", [3, 5])})
    meta, tensors = embeddings.unpack(data)
    assert meta == {}
    dtype, shape, view = tensors["m/frames"]
    assert (dtype, shape) == ("F16", [2, 8])
    back = struct.unpack("<16e", view)
    assert all(abs(a - b) < 1e-3 for a, b in zip(back, vals))
    assert struct.unpack("<2q", tensors["m/idx"][2]) == (3, 5)
    assert view.obj is not None and view.nbytes == 32  # a view, not a copy


def test_raw_bytes_and_empty_tensor_accepted():
    data = embeddings.pack({"a": ((0, 4), "F32", b""), "b": ((2,), "U8", b"\x01\x02")})
    _, t = embeddings.unpack(data)
    assert t["a"][1] == [0, 4] and bytes(t["b"][2]) == b"\x01\x02"


@pytest.mark.parametrize("bad", [
    {"x": ((2, 2), "F32", [1.0, 2.0])},        # wrong element count
    {"x": ((2,), "NOPE", b"\0\0")},            # unknown dtype
    {"x": ((-1,), "U8", b"")},                 # negative dim
    {"__metadata__": ((1,), "U8", b"\0")},     # reserved name
    {"x": ((1,), "BF16", [1.0])},              # no encoder for this dtype
    {},
])
def test_pack_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        embeddings.pack(bad)


def test_pack_rejects_non_string_metadata():
    with pytest.raises(ValueError):
        embeddings.pack({"x": ((1,), "U8", b"\0")}, {"dim": 4})


def _corrupt(data: bytes, mutate):
    (n,) = struct.unpack("<Q", data[:8])
    header = json.loads(data[8:8 + n])
    header = mutate(header)
    body = json.dumps(header).encode()
    return struct.pack("<Q", len(body)) + body + data[8 + n:]


def test_unpack_rejects_malformed():
    good = embeddings.pack({"a": ((2,), "U8", b"\x01\x02"), "b": ((2,), "U8", b"\x03\x04")})
    with pytest.raises(ValueError):
        embeddings.unpack(b"\x00" * 4)
    with pytest.raises(ValueError):
        embeddings.unpack(struct.pack("<Q", 10**9) + b"{}")
    with pytest.raises(ValueError):
        embeddings.unpack(struct.pack("<Q", 2) + b"[]")
    with pytest.raises(ValueError):  # hole
        embeddings.unpack(_corrupt(good, lambda h: {**h, "b": {**h["b"], "data_offsets": [3, 4]}} | {"a": {**h["a"], "data_offsets": [0, 1]}}))
    with pytest.raises(ValueError):  # offsets past buffer
        embeddings.unpack(_corrupt(good, lambda h: {**h, "b": {**h["b"], "data_offsets": [2, 9]}}))
    with pytest.raises(ValueError):  # shape/dtype mismatch
        embeddings.unpack(_corrupt(good, lambda h: {**h, "b": {**h["b"], "shape": [3]}}))
    with pytest.raises(ValueError):  # trailing bytes
        embeddings.unpack(good + b"\x00")
    with pytest.raises(ValueError):  # non-string metadata
        embeddings.unpack(_corrupt(good, lambda h: {**h, "__metadata__": {"k": 1}}))


def test_member_name_and_attachment_entry():
    assert embeddings.member_name("clip-vit-b32") == "embeddings/clip-vit-b32.safetensors"
    assert embeddings.member_name("org/model") == "embeddings/org_model.safetensors"
    assert embeddings.member_name("emb:visual-hash-256-v1") == "embeddings/emb-visual-hash-256-v1.safetensors"
    assert embeddings.member_name("a b*c") == "embeddings/a-b-c.safetensors"
    with pytest.raises(ValueError):
        embeddings.member_name(":::")
    with pytest.raises(ValueError):
        embeddings.member_name("..")
    data = embeddings.pack({"x": ((1,), "U8", b"\0")})
    entry = embeddings.attachment_entry(data)
    assert entry == {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                     "media_type": "application/x-safetensors"}


def test_frame_spans_are_exact_and_preferred_over_milliseconds():
    """F1: frames round-trip exactly; a reader prefers them over the ms fallback."""
    rows = [[0.0, 1.0], [2.0, 3.0], [4.0, 5.0]]
    exact = [(0, 1), (1, 143), (143, 240)]
    data = embeddings.pack_vectors(rows, 2, model="m", model_version="1",
                                   spans_ms=[(0, 42), (42, 5964), (5964, 10008)],
                                   frame_spans=exact)
    _, tensors = embeddings.unpack(data)
    unit, pairs = embeddings.spans(tensors)
    assert unit == "frame" and pairs == exact  # frame-exact wins, no rounding
    entry = embeddings.attachment_entry(data, rows="shots")
    assert entry["spans"] == "frame"


def test_millisecond_fallback_still_reads_as_ms():
    """F1: a member written before the frame tensor is still readable."""
    data = embeddings.pack_vectors([[0.0, 1.0], [2.0, 3.0]], 2, model="m",
                                   model_version="1", spans_ms=[(0, 1000), (1000, 2000)])
    _, tensors = embeddings.unpack(data)
    assert embeddings.spans(tensors) == ("ms", [(0, 1000), (1000, 2000)])
    assert embeddings.attachment_entry(data)["spans"] == "ms"
    assert embeddings.problems(data) == []


def test_untimed_member_has_no_span_unit():
    data = embeddings.pack_vectors([[0.0, 1.0]], 2, model="m", model_version="1")
    _, tensors = embeddings.unpack(data)
    assert embeddings.spans(tensors) == (None, [])
    assert "spans" not in embeddings.attachment_entry(data)


def test_frame_spans_shape_is_checked_and_declared_keys_agree():
    good = embeddings.pack_vectors([[0.0, 1.0]], 2, model="m", model_version="1",
                                   frame_spans=[(0, 5)])
    assert embeddings.problems(good, {"spans": "frame"}) == []
    assert embeddings.problems(good, {"spans": "ms"})          # declared disagrees
    bad = embeddings.pack({"vectors": ((1, 2), "F32", [0.0, 1.0]),
                           "frame_spans": ((1, 3), "I64", [0, 1, 2])})
    probs = embeddings.problems(bad)
    assert any("frame_spans" in p for p in probs)


def test_numpy_cross_check_if_available():
    np = pytest.importorskip("numpy")
    vals = _vec(4, 3)
    data = embeddings.pack({"m/frames": ((4, 3), "F32", vals)})
    (n,) = struct.unpack("<Q", data[:8])
    h = json.loads(data[8:8 + n])["m/frames"]
    arr = np.frombuffer(data[8 + n:], dtype="<f4")[h["data_offsets"][0] // 4:h["data_offsets"][1] // 4].reshape(h["shape"])
    assert np.allclose(arr.ravel(), np.array(vals, dtype="<f4"))


def test_full_opi_with_safetensors_member_validates(tmp_path):
    vals = _vec(5, 16)
    rows = [vals[i * 16:(i + 1) * 16] for i in range(5)]
    st = embeddings.pack_vectors(rows, 16, model="clip", model_version="1",
                                 spans_ms=[(t, t + 1000) for t in range(0, 5000, 1000)])
    name = embeddings.member_name("clip")
    media = tmp_path / "clip.mov"
    media.write_bytes(b"movie")
    manifest = {
        "opi": 0, "profile": "full",
        "media_binding": {"files": [{"role": "original", "name": "clip.mov", "size": 5,
                                     "sha256": hashlib.sha256(b"movie").hexdigest()}]},
        "machine_intelligence": [{"run_id": runs.run_id("embed:clip", "1", hashlib.sha256(b"movie").hexdigest()), "producer": "embed:clip", "model_version": "1",
                                  "facets": {}, "attachments": {name: embeddings.attachment_entry(st)}}],
    }
    sign.sign_run(manifest, 0, ed25519.generate_secret(), signer="urn:test")
    path = container.write_full(manifest, tmp_path / "clip.mov.opi", {name: st}, aligned={name})

    report = validate.validate(path)
    assert report.ok, [c for c in report.checks if not c.ok]
    assert report.status == "valid-signed"
    off = container.member_data_offset(path, name)
    assert off % 64 == 0
    # The tensor buffer is 64-aligned in the *file*, not just in the member.
    (n,) = struct.unpack("<Q", st[:8])
    assert (off + 8 + n) % 64 == 0
    with open(path, "rb") as fh:
        fh.seek(off)
        meta, tensors = embeddings.unpack(fh.read(len(st)))
    assert meta["opi.model"] == "clip" and tensors["vectors"][1] == [5, 16]
