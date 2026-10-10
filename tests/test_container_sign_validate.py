import hashlib
import json
import os
import subprocess
import zipfile

import pytest

from openpicture import cli, container, ed25519, runs, sign, validate


def _manifest(media_dir, name="clip.mov", body=b"not really a movie"):
    (media_dir / name).write_bytes(body)
    return {
        "opi": 0,
        "profile": "core",
        "media_binding": {"timecode": {"start": "00:00:00:00", "rate": {"num": 24, "den": 1}, "drop_frame": False}, 
            "files": [{"role": "original", "name": name, "size": len(body),
                       "sha256": hashlib.sha256(body).hexdigest()}],
        },
        "machine_intelligence": [
            {"run_id": runs.run_id("test:shots", "1", hashlib.sha256(body).hexdigest()),
             "producer": "test:shots", "model_version": "1",
             "facets": {"shots": [{"idx": 0, "confidence": 0.5, "span": {"frame_in": 0, "frame_out": 48}}]}}
        ],
        "editorial_annotations": {"notes": "hero take"},
    }


# ── detection ──────────────────────────────────────────────────────────


def test_detect_core_full_and_neither(tmp_path):
    assert container.detect(b'{"opi":0}') == "json"
    assert container.detect("﻿  \n{".encode("utf-8")) == "json"
    assert container.detect(b"PK\x03\x04rest") == "zip"
    assert container.profile_of_members(["manifest.json"]) == "core"
    assert container.profile_of_members(["manifest.json", "keyframes/"]) == "core"
    assert container.profile_of_members(["manifest.json", "embeddings.bin"]) == "full"
    assert container.detect(b"PK\x05\x06") is None  # empty zip
    assert container.detect(b"[1,2]") is None
    assert container.detect(b"garbage PK\x03\x04") is None


# ── core round trip ────────────────────────────────────────────────────


def test_core_write_read_and_validate_unsigned(tmp_path):
    m = _manifest(tmp_path)
    path = container.write_core(m, tmp_path / "clip.opi")
    back, profile = container.read_manifest(path)
    assert profile == "core" and back == m
    assert path.read_bytes().startswith(b"PK\x03\x04")  # B14: a .opi is always a ZIP
    with zipfile.ZipFile(path) as zf:
        assert zf.namelist() == ["manifest.json"]
        assert zf.read("manifest.json").startswith(b"{\n  \"opi\": 0")
    report = validate.validate(path)
    assert report.ok, report.as_dict()
    assert report.status == "valid-unsigned"
    assert not list(tmp_path.glob(".*.tmp.*"))  # atomic write cleaned up


def test_bare_json_internal_form_reads_as_core_and_is_flagged_not_failed(tmp_path):
    m = _manifest(tmp_path)
    path = container.write_json(m, tmp_path / "clip.mov.opi")
    assert container.detect(path) == "json"
    back, profile = container.read_manifest(path)
    assert profile == "core" and back == m
    report = validate.validate(path)
    assert report.ok and report.status == "valid-unsigned"
    canon = next(c for c in report.checks if c.name == "canonical form")
    assert canon.ok and "internal form" in canon.detail
    # sign converts it to the canonical ZIP form
    assert cli.main(["sign", str(path), "--key", _key(tmp_path), "--signer", "urn:t"]) == 0
    assert container.detect(path) == "zip"


def _key(tmp_path):
    k = tmp_path / "k.hex"
    if not k.exists():
        k.write_text(ed25519.generate_secret().hex())
    return str(k)


def test_media_sha_mismatch_fails_but_missing_media_is_allowed(tmp_path):
    m = _manifest(tmp_path)
    path = container.write_core(m, tmp_path / "clip.opi")
    (tmp_path / "clip.mov").write_bytes(b"changed")
    r = validate.validate(path)
    assert not r.ok and any(c.name == "media sha256" and not c.ok for c in r.checks)
    (tmp_path / "clip.mov").unlink()
    assert validate.validate(path).ok


# ── signing ────────────────────────────────────────────────────────────


def test_sign_verify_and_human_layer_mutation(tmp_path):
    m = _manifest(tmp_path)
    sk = ed25519.generate_secret()
    entry = sign.sign_run(m, 0, sk, signer="urn:test:producer")
    assert m["machine_intelligence"][0]["signature"] is entry
    vr = sign.verify_manifest(m)
    assert vr.status == "signed" and vr.runs[0].status == "valid"

    # An editor changes the human block: still signed.
    m["editorial_annotations"]["notes"] = "actually the B take"
    m["editorial_annotations"]["rating"] = 5
    assert sign.verify_manifest(m).status == "signed"

    # Anyone touches the run's facets: invalid, and the report says which run.
    m["machine_intelligence"][0]["facets"]["shots"][0]["confidence"] = 0.99
    vr = sign.verify_manifest(m)
    assert vr.status == "invalid" and vr.runs[0].reason == "signature does not verify"


def test_run_signature_binds_the_media(tmp_path):
    m = _manifest(tmp_path)
    sign.sign_run(m, 0, ed25519.generate_secret(), signer="urn:a")
    m["media_binding"]["files"][0]["sha256"] = "0" * 64
    assert sign.verify_manifest(m).status == "invalid"


def test_second_producer_appends_without_voiding_the_first(tmp_path):
    m = _manifest(tmp_path)
    sign.sign_run(m, 0, ed25519.generate_secret(), signer="urn:a")
    m["machine_intelligence"].append({"run_id": "r2", "producer": "b:pass", "model_version": "1", "facets": {}})
    assert sign.verify_manifest(m).status == "partial"
    sign.sign_run(m, 1, ed25519.generate_secret(), signer="urn:b")
    vr = sign.verify_manifest(m)
    assert vr.status == "signed"
    assert [(r.status, r.signer) for r in vr.runs] == [("valid", "urn:a"), ("valid", "urn:b")]


def test_unsigned_is_not_invalid_and_bad_entries_are_reported(tmp_path):
    m = _manifest(tmp_path)
    assert sign.verify_manifest(m).status == "unsigned"
    m["machine_intelligence"][0]["signature"] = {"algorithm": "RSA", "public_key": "", "signature": ""}
    assert "unsupported algorithm" in sign.verify_manifest(m).runs[0].reason
    m["machine_intelligence"][0]["signature"] = {"algorithm": "Ed25519", "public_key": "zz", "signature": "!"}
    assert "malformed" in sign.verify_manifest(m).runs[0].reason
    del m["machine_intelligence"]
    assert sign.verify_manifest(m).status == "unsigned"
    with pytest.raises(IndexError):
        sign.sign_run(_manifest(tmp_path), 3, ed25519.generate_secret(), signer="x")


# ── full container ─────────────────────────────────────────────────────


def test_full_container_alignment_and_validation(tmp_path):
    m = _manifest(tmp_path)
    emb = bytes(range(256)) * 10
    kf = b"RIFFfakewebp"
    m["profile"] = "full"
    m["machine_intelligence"][0]["attachments"] = {
        "extensions/com.example/test.bin": {"sha256": hashlib.sha256(emb).hexdigest(), "size": len(emb), "media_type": "application/octet-stream"},
        "extensions/com.example/still.bin": {"sha256": hashlib.sha256(kf).hexdigest(), "size": len(kf), "media_type": "application/octet-stream"},
    }
    sign.sign_run(m, 0, ed25519.generate_secret(), signer="urn:test")
    path = container.write_full(m, tmp_path / "clip.opi", {"extensions/com.example/test.bin": emb, "extensions/com.example/still.bin": kf})

    assert container.detect(path) == "zip"
    off = container.member_data_offset(path, "extensions/com.example/test.bin")
    assert off % 64 == 0
    with open(path, "rb") as fh:
        fh.seek(off)
        assert fh.read(len(emb)) == emb  # zero-copy slice is the real bytes
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
        assert zf.read("manifest.json") == container.manifest_bytes(m)
        assert zf.getinfo("extensions/com.example/test.bin").compress_type == zipfile.ZIP_STORED

    report = validate.validate(path)
    assert report.ok, [c for c in report.checks if not c.ok]
    assert report.status == "valid-signed"
    # tampering with a member is caught through the signed attachments block
    with zipfile.ZipFile(path, "a") as zf:
        zf.writestr("extensions/com.example/x.json", "{}")
    r = validate.validate(path)
    assert not r.ok and any("undeclared" in c.detail for c in r.checks if not c.ok)


def test_alignment_holds_for_many_name_lengths(tmp_path):
    for n in range(1, 70):
        name = "extensions/com.example/" + "a" * n + ".bin"
        path = container.write_full({"opi": 0, "profile": "full", "media_binding": {"timecode": {"start": "00:00:00:00", "rate": {"num": 24, "den": 1}, "drop_frame": False}, "files": []}},
                                    tmp_path / f"t{n}.opi", {name: b"\x01" * 7})
        assert container.member_data_offset(path, name) % 64 == 0, n


def test_unzip_p_works_when_available(tmp_path):
    import shutil
    if shutil.which("unzip") is None:
        pytest.skip("no unzip")
    m = _manifest(tmp_path)
    m["profile"] = "full"
    path = container.write_full(m, tmp_path / "clip.opi")
    out = subprocess.run(["unzip", "-p", str(path), "manifest.json"], capture_output=True)
    assert out.returncode == 0 and json.loads(out.stdout)["opi"] == 0


def test_full_without_manifest_is_rejected(tmp_path):
    p = tmp_path / "bad.opi"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("x.txt", "hi")
    assert not validate.validate(p).ok


# ── cli ────────────────────────────────────────────────────────────────


def test_cli_end_to_end(tmp_path, capsys):
    m = _manifest(tmp_path)
    core = tmp_path / "clip.opi"
    container.write_core(m, core)
    key = tmp_path / "k.hex"
    assert cli.main(["keygen", str(key)]) == 0
    assert oct(os.stat(key).st_mode & 0o777) == "0o600"
    assert cli.main(["sign", str(core), "--key", str(key), "--signer", "urn:test"]) == 0
    assert cli.main(["validate", str(core)]) == 0
    out = capsys.readouterr().out
    assert "valid-signed" in out

    emb = tmp_path / "e.bin"
    emb.write_bytes(b"\x00" * 100)
    # attaching members to an already-signed run is refused
    assert cli.main(["pack", str(core), str(tmp_path / "full.opi"), "--member", f"extensions/com.example/e.bin={emb}"]) == 2
    # attach first, then the packed manifest validates (unsigned)
    container.write_core(_manifest(tmp_path), core)
    assert cli.main(["pack", str(core), str(tmp_path / "full.opi"), "--member", f"extensions/com.example/e.bin={emb}"]) == 0
    assert cli.main(["validate", "--json", str(tmp_path / "full.opi")]) == 0
    rep = json.loads(capsys.readouterr().out.split("\n", 1)[1])
    assert rep["status"] == "valid-unsigned" and rep["profile"] == "full"
    assert cli.main(["inspect", str(tmp_path / "full.opi")]) == 0
    assert cli.main(["unpack", str(tmp_path / "full.opi"), str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "manifest.json").exists()


def test_pack_without_members_is_core(tmp_path, capsys):
    m = _manifest(tmp_path)
    src = tmp_path / "manifest.json"
    src.write_text(json.dumps(m))
    assert cli.main(["pack", str(src), str(tmp_path / "c.mov.opi")]) == 0
    rep = validate.validate(tmp_path / "c.mov.opi")
    assert rep.ok and rep.profile == "core", [c for c in rep.checks if not c.ok]


def test_sign_full_file_in_place(tmp_path, capsys):
    m = _manifest(tmp_path)
    emb = b"\x01" * 100
    m["profile"] = "full"
    m["machine_intelligence"][0]["attachments"] = {"extensions/com.example/e.bin": {"sha256": hashlib.sha256(emb).hexdigest(), "size": len(emb), "media_type": "application/octet-stream"}}
    path = container.write_full(m, tmp_path / "c.mov.opi", {"extensions/com.example/e.bin": emb})
    key = tmp_path / "k.hex"
    cli.main(["keygen", str(key)])
    assert cli.main(["sign", str(path), "--key", str(key), "--signer", "urn:t"]) == 0
    rep = validate.validate(path)
    assert rep.status == "valid-signed", [c for c in rep.checks if not c.ok]
    with zipfile.ZipFile(path) as zf:
        assert zf.read("extensions/com.example/e.bin") == emb
    assert container.member_data_offset(path, "extensions/com.example/e.bin") % 64 == 0


def test_host_and_models_fall_under_the_run_signature(tmp_path):
    """SPEC §7.2 claims these are attested. §9.2's payload is every run key
    except `signature`, so the claim is only true if tampering breaks it."""
    m = _manifest(tmp_path)
    m["machine_intelligence"][0]["host"] = {"os": "linux", "arch": "x86_64"}
    m["machine_intelligence"][0]["models"] = [{"name": "w.pt", "sha256": "ab" * 32}]
    sk = ed25519.generate_secret()
    sign.sign_all(m, sk, signer="urn:p")
    assert sign.verify_manifest(m).status == "signed"

    m["machine_intelligence"][0]["host"]["arch"] = "arm64"
    assert sign.verify_manifest(m).status != "signed"


def test_the_human_layer_stays_outside_the_signature(tmp_path):
    """§8/§9.2: `by` is a claim precisely because no signature covers it."""
    m = _manifest(tmp_path)
    sk = ed25519.generate_secret()
    sign.sign_all(m, sk, signer="urn:p")
    m["editorial_annotations"]["labels"] = [
        {"name": "select", "value": True, "created_by": "opi:latent", "by": "u-417"}
    ]
    assert sign.verify_manifest(m).status == "signed"
