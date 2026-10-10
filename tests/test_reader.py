import hashlib
from pathlib import Path

import pytest

from openpicture import container, ed25519, reader, sign

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_load_core_example():
    sc = reader.load(EXAMPLES / "A001_C001.mov.opi")
    assert sc.profile == "core" and sc.version == 0
    assert sc.original["name"] == "A001_C001.mov" and len(sc.sha256) == 64
    assert sc.signature_status == "signed"
    assert [r.producer for r in sc.runs] == ["shots:scenedetect"]
    assert sc.runs[0].verified and sc.runs[0].signer.startswith("urn:openpicture:example")
    shots = sc.trusted_facets("shots")
    assert shots and shots[0][0]["span"]["frame_in"] == 0
    assert sc.annotations["labels"][0]["value"] == "hero"
    assert sc.members() == [] and not list(sc.facets("nope"))


def test_load_full_example_members_and_mmap():
    sc = reader.load(EXAMPLES / "A001_C001.mov.full.opi")
    assert sc.profile == "full"
    members = sc.members()
    kf_name = next(m for m in members if m.startswith("keyframes/"))
    emb_name = next(m for m in members if m.startswith("embeddings/"))
    kf = sc.read_member(kf_name)
    assert kf[:4] == b"RIFF"
    view = sc.map_member(emb_name)
    declared = next(r.attachments[emb_name] for r in sc.runs if emb_name in r.attachments)
    assert len(view) == declared["size"]
    assert hashlib.sha256(bytes(view)).hexdigest() == declared["sha256"]
    view.release()
    with pytest.raises(KeyError):
        reader.load(EXAMPLES / "A001_C001.mov.opi").read_member("x")


def test_tampered_run_is_untrusted(tmp_path):
    m = {"opi": 0, "profile": "core",
         "media_binding": {"files": [{"role": "original", "name": "c.mov", "sha256": "0" * 64}]},
         "machine_intelligence": [{"run_id": "a", "producer": "p", "facets": {"shots": [1]}},
                                  {"run_id": "b", "producer": "q", "facets": {"shots": [2]}}]}
    sign.sign_run(m, 0, ed25519.generate_secret(), signer="urn:a")
    m["machine_intelligence"][0]["facets"]["shots"] = [99]  # tamper after signing
    p = container.write_core(m, tmp_path / "c.mov.opi")
    sc = reader.load(p)
    assert sc.signature_status == "invalid"
    assert [r.status for r in sc.runs] == ["invalid", "unsigned"]
    assert sc.trusted_facets("shots") == []
    assert [v for _, v in sc.facets("shots")] == [[99], [2]]


def test_refuses_newer_major_and_non_opi(tmp_path):
    p = container.write_core({"opi": 99, "profile": "core", "media_binding": {"files": []}}, tmp_path / "n.opi")
    with pytest.raises(reader.UnsupportedVersion):
        reader.load(p)
    assert reader.load(p, max_version=99).version == 99
    (tmp_path / "x.opi").write_bytes(b"nope")
    with pytest.raises(ValueError):
        reader.load(tmp_path / "x.opi")
