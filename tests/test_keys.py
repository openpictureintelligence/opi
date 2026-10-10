import json

import pytest

from openpicture import ed25519, keys, sign


def _manifest():
    return {
        "opi": 0, "profile": "core",
        "media_binding": {"timecode": {"start": "00:00:00:00", "rate": {"num": 24, "den": 1}, "drop_frame": False}, "files": [{"role": "original", "name": "c.mov", "size": 1, "sha256": "a" * 64}]},
        "machine_intelligence": [
            {"run_id": "r1", "producer": "test:p", "model_version": "1", "facets": {}},
            {"run_id": "r2", "producer": "test:q", "model_version": "2", "facets": {}},
        ],
        "editorial_annotations": {},
    }


def test_add_load_lookup_append_only(tmp_path):
    log = tmp_path / "keys.jsonl"
    sk = ed25519.generate_secret()
    pk = ed25519.public_key(sk).hex()
    e1 = keys.add(log, sk.hex(), "urn:a", from_secret=True, note="laptop")
    assert e1.public_key == pk
    e2 = keys.add(log, pk, "urn:a", note="rotated out 2027-01-01; still valid for old files")
    entries = keys.load(log)
    assert [e.note for e in entries] == ["laptop", e2.note]
    assert len(keys.lookup(entries, pk.upper())) == 2
    assert log.read_text().count("\n") == 2  # one line per append, nothing rewritten
    assert sk.hex() not in log.read_text()   # the secret never lands in the log


def test_load_missing_is_empty_and_malformed_raises(tmp_path):
    assert keys.load(tmp_path / "nope") == []
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"public_key": "x"}\n')
    with pytest.raises(ValueError):
        keys.load(bad)
    with pytest.raises(ValueError):
        keys.add(tmp_path / "k", "abcd", "urn:x")


def test_trust_report_layers_over_verification(tmp_path):
    log = tmp_path / "keys.jsonl"
    m = _manifest()
    sk_a, sk_b = ed25519.generate_secret(), ed25519.generate_secret()
    sign.sign_run(m, 0, sk_a, signer="urn:a")
    sign.sign_run(m, 1, sk_b, signer="urn:b")
    keys.add(log, sk_a, "urn:a", from_secret=True)
    entries = keys.load(log)

    report = keys.trust_report(m, entries)
    assert [(t.status, t.trust) for t in report] == [("valid", "trusted"), ("valid", "unknown-signer")]

    # log says this key belongs to someone else than the file claims
    keys.add(log, sk_b, "urn:not-b", from_secret=True)
    report = keys.trust_report(m, keys.load(log))
    assert report[1].trust == "signer-mismatch" and "urn:not-b" in report[1].note

    # an unsigned or invalid run is not a trust question
    del m["machine_intelligence"][1]["signature"]
    m["machine_intelligence"][0]["facets"] = {"x": 1}
    report = keys.trust_report(m, keys.load(log))
    assert [(t.status, t.trust) for t in report] == [("invalid", "n/a"), ("unsigned", "n/a")]
