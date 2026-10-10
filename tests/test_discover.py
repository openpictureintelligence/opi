import hashlib

from openpicture import container, discover, ed25519, sign


def _manifest(media_path, sha=None, body=None, opi=0):
    if body is not None:
        media_path.write_bytes(body)
    sha = sha or hashlib.sha256(media_path.read_bytes()).hexdigest()
    return {
        "opi": opi, "profile": "core",
        "media_binding": {"timecode": {"start": "00:00:00:00", "rate": {"num": 24, "den": 1}, "drop_frame": False}, "files": [{"role": "original", "name": media_path.name,
                                     "size": media_path.stat().st_size, "sha256": sha}]},
        "machine_intelligence": [{"run_id": "r1", "producer": "test:p", "model_version": "1", "facets": {}}],
        "editorial_annotations": {},
    }


def _tree(tmp_path):
    root = tmp_path / "archive"
    (root / "DAY_01").mkdir(parents=True)
    (root / "DAY_02").mkdir()
    a = root / "DAY_01" / "A001_C001.mov"
    a.write_bytes(b"alpha")
    container.write_core(_manifest(a), a.with_name("A001_C001.mov.opi"))
    b = root / "DAY_01" / "A001_C001.wav"          # shares a stem with the .mov
    b.write_bytes(b"lav")
    container.write_core(_manifest(b), b.with_name("A001_C001.wav.opi"))
    c = root / "DAY_01" / "A001_C002.mov"           # missing sidecar
    c.write_bytes(b"gamma")
    d = root / "DAY_02" / "B001_C001.MOV"           # stem-form sidecar, uppercase ext
    d.write_bytes(b"delta")
    container.write_core(_manifest(d), d.with_name("B001_C001.opi"))
    e = root / "DAY_02" / "B001_C002.mov"           # mismatch
    e.write_bytes(b"epsilon")
    container.write_core(_manifest(e, sha="0" * 64), e.with_name("B001_C002.mov.opi"))
    orphan = root / "DAY_02" / "lost.mov.opi"       # orphan whose sha matches c
    container.write_core(_manifest(c), orphan)
    (root / "DAY_02" / "junk.opi").write_text("not json at all")
    return root, dict(a=a, b=b, c=c, d=d, e=e, orphan=orphan)


def test_scan_states_without_hashing(tmp_path):
    root, f = _tree(tmp_path)
    by_media = {str(p.media.name) if p.media else str(p.sidecar.name): p for p in discover.scan(root)}
    assert by_media["A001_C001.mov"].state == "paired-unverified"
    assert by_media["A001_C001.wav"].state == "paired-unverified"
    assert by_media["A001_C001.wav"].sidecar.name == "A001_C001.wav.opi"  # not the .mov's
    assert by_media["A001_C002.mov"].state == "missing"
    assert by_media["B001_C001.MOV"].state == "paired-unverified"
    assert by_media["B001_C001.MOV"].sidecar.name == "B001_C001.opi"      # stem fallback
    assert by_media["B001_C002.mov"].state == "paired-unverified"          # mismatch needs hashing
    assert by_media["lost.mov.opi"].state == "orphan"
    assert by_media["junk.opi"].state == "unreadable"
    counts = discover.summarize(discover.scan(root))
    assert counts == {"missing": 1, "orphan": 1, "paired-unverified": 4, "unreadable": 1}


def test_scan_verifies_media_when_asked(tmp_path):
    root, f = _tree(tmp_path)
    states = {p.media.name: p for p in discover.scan(root, verify_media=True) if p.media}
    assert states["A001_C001.mov"].state == "paired"
    assert states["B001_C002.mov"].state == "mismatch"
    assert "manifest 000000000000" in states["B001_C002.mov"].detail


def test_duplicate_tampered_and_newer_schema(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    m = root / "x.mov"
    m.write_bytes(b"x")
    manifest = _manifest(m)
    container.write_core(manifest, root / "x.mov.opi")
    container.write_core(manifest, root / "x.opi")            # stem form as well -> duplicate
    (p,) = [p for p in discover.scan(root) if p.media]
    assert p.state == "duplicate" and p.sidecar.name == "x.mov.opi" and [e.name for e in p.extras] == ["x.opi"]

    (root / "x.opi").unlink()
    sign.sign_run(manifest, 0, ed25519.generate_secret(), signer="urn:a")
    manifest["machine_intelligence"][0]["facets"] = {"shots": [1]}  # tamper after signing
    container.write_core(manifest, root / "x.mov.opi")
    (p,) = [p for p in discover.scan(root) if p.media]
    assert p.state == "tampered" and "urn:a" in p.detail

    container.write_core(_manifest(m, opi=99), root / "x.mov.opi")
    (p,) = [p for p in discover.scan(root) if p.media]
    assert p.state == "newer-schema"


def test_repair_proposes_then_applies(tmp_path):
    root, f = _tree(tmp_path)
    pairings = discover.scan(root)
    proposals = discover.repair(root, pairings)
    assert [(r.sidecar.name, r.target.name) for r in proposals] == [("lost.mov.opi", "A001_C002.mov.opi")]
    assert f["orphan"].exists() and not proposals[0].applied

    applied = discover.repair(root, pairings, apply=True)
    assert applied[0].applied and not f["orphan"].exists()
    assert (root / "DAY_01" / "A001_C002.mov.opi").exists()
    after = discover.summarize(discover.scan(root))
    assert "orphan" not in after and "missing" not in after


def test_repair_never_overwrites(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    m = root / "a.mov"
    m.write_bytes(b"a")
    container.write_core(_manifest(m), root / "a.mov.opi")
    container.write_core(_manifest(m), root / "stray.opi")  # same sha, but a.mov is already paired
    pairings = discover.scan(root)
    assert discover.repair(root, pairings) == []


def test_hidden_files_and_dirs_are_skipped(tmp_path):
    root = tmp_path / "r"
    (root / ".opi").mkdir(parents=True)
    (root / ".opi" / "cache.mov").write_bytes(b"x")
    (root / "._a.mov").write_bytes(b"x")
    assert discover.scan(root) == []


def test_examples_scan_as_orphans_not_errors():
    from pathlib import Path
    ex = Path(__file__).resolve().parent.parent / "examples"
    states = {p.sidecar.name: p.state for p in discover.scan(ex)}
    assert states["A001_C001.mov.opi"] == "orphan"
    assert states["A001_C001.mov.full.opi"] == "orphan"
