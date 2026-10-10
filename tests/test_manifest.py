"""SPEC §5, §6, §8 — the manifest key by key, via vectors/manifest/.

Every vector is pushed through the schema (the stdlib mini-checker in
test_schema.py) and, when written as a real file, through the reference
validator. `expect.validator == null` marks a rule the schema enforces but
the validator has no row for yet — those assert schema only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from openpicture import container, validate

from tests.test_schema import check as schema_check

ROOT = Path(__file__).resolve().parents[1]
VEC = ROOT / "vectors" / "manifest"
NAMES = sorted(p.name for p in VEC.glob("*.json") if p.name != "invalid-oversize.json")


def _load(name):
    return json.loads((VEC / name).read_text())


def test_vectors_are_current():
    r = subprocess.run([sys.executable, str(VEC / "make_vectors.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("name", NAMES)
def test_schema_verdict(name):
    v = _load(name)
    errs = schema_check(v["manifest"])
    if v["expect"]["schema"] == "valid":
        assert errs == [], errs
    else:
        assert errs, f"{name}: schema accepted an invalid manifest"


@pytest.mark.parametrize("name", NAMES)
def test_validator_verdict(name, tmp_path):
    v = _load(name)
    expect = v["expect"]["validator"]
    if expect is None:
        pytest.skip("schema-only rule; no validator row yet")
    path = container.write_core(v["manifest"], tmp_path / "clip.mov.opi")
    report = validate.validate(path)
    failing = [(c.name, c.detail) for c in report.checks if not c.ok]
    if expect == "valid":
        assert report.ok, failing
        return
    assert not report.ok, f"{name}: validator accepted an invalid file"
    # and for the stated reason — a vector that starts failing a different
    # check has stopped testing what it was written to test
    want = v["expect"]["check"]
    assert want, f"{name}: a must-fail vector must name the check it fails"
    assert any(want in n for n, _ in failing), f"{name}: expected {want!r}, got {failing}"


def test_minimal_and_maximal_roundtrip_bytes(tmp_path):
    """§5.5: a Core file's manifest re-serializes to the same bytes."""
    for name in ("valid-minimal.json", "valid-maximal.json"):
        m = _load(name)["manifest"]
        path = container.write_core(m, tmp_path / name.replace(".json", ".opi"))
        back, profile = container.read_manifest(path)
        assert profile == "core"
        assert container.manifest_bytes(back) == container.manifest_bytes(m)
        assert list(back)[0] == "opi"


def test_exactly_one_original_default_role():
    """§6.3: an entry without `role` counts as the original."""
    m = _load("valid-minimal.json")["manifest"]
    assert "role" not in m["media_binding"]["files"][0]
    assert schema_check(m) == []
    two = json.loads(json.dumps(m))
    two["media_binding"]["files"].append({"name": "b.mov", "sha256": "0" * 64})
    assert schema_check(two)  # two implicit originals


def test_oversize_rule_is_stated_and_measurable():
    """§5.6: the cap is 16 MiB of serialized manifest; padding past it must be detectable."""
    v = _load("invalid-oversize.json")
    assert v["limit_bytes"] == 16 * 1024 * 1024
    m = _load("valid-maximal.json")["manifest"]
    small = len(container.manifest_bytes(m))
    assert small < v["limit_bytes"]
    # Replacing the existing note also removes its old serialized bytes; pad
    # with a small margin so the assertion measures the cap, not that detail.
    m["editorial_annotations"]["notes"] = "x" * (v["limit_bytes"] - small + 256)
    assert len(container.manifest_bytes(m)) > v["limit_bytes"]


def test_oversize_manifest_is_rejected_before_parse(tmp_path):
    """The reader must enforce the manifest cap before loading JSON."""
    m = _load("valid-maximal.json")["manifest"]
    small = len(container.manifest_bytes(m))
    m["editorial_annotations"]["notes"] = "x" * (container.MAX_MANIFEST_BYTES - small + 256)
    path = container.write_core(m, tmp_path / "oversize.mov.opi")
    with pytest.raises(container.ManifestTooLarge):
        container.read_manifest(path)


def test_unknown_keys_survive_write_and_read(tmp_path):
    """§5.3: unknown keys at every level are carried, not dropped."""
    m = _load("valid-maximal.json")["manifest"]
    m["x-future"] = {"a": [1]}
    m["media_binding"]["x-vendor"] = True
    m["media_binding"]["files"][0]["x-note"] = "kept"
    m["editorial_annotations"]["labels"][0]["x-colour"] = "red"
    path = container.write_core(m, tmp_path / "u.mov.opi")
    back, _ = container.read_manifest(path)
    assert back["x-future"] == {"a": [1]}
    assert back["media_binding"]["files"][0]["x-note"] == "kept"
    assert back["editorial_annotations"]["labels"][0]["x-colour"] == "red"
    assert schema_check(back) == []
