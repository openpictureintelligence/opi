import copy
import hashlib
import json
from pathlib import Path

import pytest

from openpicture import runs, sign

VEC = Path(__file__).resolve().parent.parent / "vectors" / "runs"
SHA = hashlib.sha256(b"abc").hexdigest()


def _vec(name):
    return json.loads((VEC / f"{name}.json").read_text())


def _failing(manifest):
    return [name for name, ok, _ in runs.checks(manifest) if not ok]


def test_run_id_vectors_and_form():
    for c in _vec("valid-run-id")["cases"]:
        assert runs.run_id(c["producer"], c["model_version"], c["sha256"]) == c["run_id"]
        assert len(c["run_id"]) == runs.RUN_ID_LENGTH
        assert hashlib.sha256(c["payload"].encode()).hexdigest()[:32] == c["run_id"]
    with pytest.raises(ValueError):
        runs.run_id("a:b", "1", "not-a-sha")


def test_valid_two_runs_all_ok_and_order_independent():
    v = _vec("valid-two-runs")
    assert _failing(v["manifest"]) == []
    assert [r["run_id"] for r in runs.current_runs(v["manifest"])] == v["expect"]["current"]
    swapped = copy.deepcopy(v["manifest"])
    swapped["machine_intelligence"].reverse()
    assert _failing(swapped) == []
    assert {r["run_id"] for r in runs.current_runs(swapped)} == set(v["expect"]["current"])


@pytest.mark.parametrize("name", [
    "invalid-duplicate-run-id", "invalid-wrong-run-id", "invalid-producer-charset", "invalid-entry-without-confidence",
])
def test_failure_vectors(name):
    v = _vec(name)
    failing = _failing(v["manifest"])
    for expected in v["expect"]["failing"]:
        assert expected in failing, (expected, failing)


def test_rerun_replaces_in_place_with_new_signature():
    v = _vec("valid-rerun-replace-in-place")
    before, after = v["before"], v["after"]
    b, a = before["machine_intelligence"][0], after["machine_intelligence"][0]
    assert b["run_id"] == a["run_id"]
    assert b["signature"]["signature"] != a["signature"]["signature"]
    assert sign.verify_manifest(before).status == "signed"
    assert sign.verify_manifest(after).status == "signed"
    # the old signature does not verify the new content
    stale = copy.deepcopy(after)
    stale["machine_intelligence"][0]["signature"] = b["signature"]
    assert sign.verify_manifest(stale).status == "invalid"
    # and re-signing with the vector's key reproduces the recorded signature exactly
    sk = bytes.fromhex(v["secret_key_hex"])
    re = copy.deepcopy(after)
    re["machine_intelligence"][0].pop("signature")
    sign.sign_run(re, 0, sk, signer="urn:example:producer", signed_at=a["signature"]["signed_at"])
    assert re["machine_intelligence"][0]["signature"]["signature"] == a["signature"]["signature"]


def test_lineage_and_current_runs():
    v = _vec("valid-lineage-supersedes")
    m = v["manifest"]
    assert _failing(m) == []
    assert [r["run_id"] for r in runs.current_runs(m)] == v["expect"]["current"]
    new_id = v["expect"]["lineage_of_new"][0]
    assert [r["run_id"] for r in runs.lineage(m, new_id)] == v["expect"]["lineage_of_new"]
    assert runs.lineage(m, "0" * 32) == []


def test_bp_scale_vector_and_confidence_rules():
    assert _failing(_vec("valid-bp-scale")["manifest"]) == []
    r = runs.new_run("a:b", "1", SHA, confidence_scale="bp", facets={"f": [{"confidence": 1.5}]})
    m = {"media_binding": {"files": [{"sha256": SHA}]}, "machine_intelligence": [r]}
    assert "run[0] facet f" in _failing(m)
    r = runs.new_run("a:b", "1", SHA, facets={"f": [{"confidence": True}]})
    m["machine_intelligence"] = [r]
    assert "run[0] facet f" in _failing(m)


def test_new_run_validates_its_inputs():
    with pytest.raises(ValueError):
        runs.new_run("NoColon", "1", SHA)
    with pytest.raises(ValueError):
        runs.new_run("a:b", "", SHA)
    with pytest.raises(ValueError):
        runs.new_run("a:b", "1", SHA, egress="cloud")
    r = runs.new_run("a:b", "1", SHA, generator="test 0", depends_on=["x" * 32])
    assert r["generated_at"].endswith("Z") and r["depends_on"] == ["x" * 32]


def test_checks_edge_cases():
    assert runs.checks({}) == [("runs", True, "no machine_intelligence")]
    assert runs.checks({"machine_intelligence": {}})[0][1] is False
    m = {"media_binding": {"files": [{"sha256": SHA}]},
         "machine_intelligence": ["nope", {"run_id": "z" * 32, "producer": "a:b", "model_version": "1",
                                           "facets": {"Bad Name": []}, "supersedes": "z" * 32,
                                           "generated_at": "yesterday", "egress": "cloud",
                                           "depends_on": ["q" * 32]}]}
    failing = _failing(m)
    for name in ("run[0]", "run[1] run_id derived", "run[1] facet Bad Name", "run[1] supersedes",
                 "run[1] generated_at", "run[1] egress"):
        assert name in failing, (name, failing)
    assert any(n.startswith("run[1] depends_on") for n in failing)


def test_attachments_declared_by_exactly_one_run():
    r1 = runs.new_run("a:b", "1", SHA, attachments={"embeddings/x.safetensors": {"sha256": "0" * 64, "size": 1}})
    r2 = runs.new_run("c:d", "1", SHA, attachments={"embeddings/x.safetensors": {"sha256": "0" * 64, "size": 1}})
    m = {"media_binding": {"files": [{"sha256": SHA}]}, "machine_intelligence": [r1, r2]}
    assert "run[1] attachment embeddings/x.safetensors" in _failing(m)


def test_current_runs_without_supersedes_uses_generated_at_then_position():
    a = runs.new_run("a:b", "1", SHA, generated_at="2026-01-01T00:00:00Z")
    b = runs.new_run("a:b", "2", SHA, generated_at="2026-02-01T00:00:00Z")
    assert runs.current_runs({"machine_intelligence": [b, a]})[0]["run_id"] == b["run_id"]
    a.pop("generated_at"); b.pop("generated_at")
    assert runs.current_runs({"machine_intelligence": [b, a]})[0]["run_id"] == a["run_id"]


def test_host_must_be_a_class_of_machine_not_an_instance():
    """§7.2: the vocabularies are closed so that a hostname cannot slip into a
    signature, where removing it would mean destroying the signature."""
    ok = runs.new_run("a:b", "1", SHA)
    ok["host"] = {"os": "linux", "arch": "x86_64", "accelerator": "cuda"}
    assert "run[0] host" not in _failing({"media_binding": {"files": [{"sha256": SHA}]},
                                          "machine_intelligence": [ok]})
    for host in ({"os": "macos", "arch": "MacBook-Pro.local"},
                 {"os": "macos", "hostname": "studio-3"},
                 {"os": "macos", "arch": "arm64", "accelerator": "npu"},
                 "macos-arm64"):
        run = runs.new_run("a:b", "1", SHA)
        run["host"] = host
        m = {"media_binding": {"files": [{"sha256": SHA}]}, "machine_intelligence": [run]}
        assert "run[0] host" in _failing(m), host


def test_models_name_a_file_and_a_digest():
    run = runs.new_run("a:b", "1", SHA)
    run["models"] = [{"name": "weights.safetensors", "sha256": "ab" * 32}]
    m = {"media_binding": {"files": [{"sha256": SHA}]}, "machine_intelligence": [run]}
    assert "run[0] models" not in _failing(m)
    for models in ([{"name": "w", "sha256": "AB" * 32}], [{"name": "w"}],
                   [{"sha256": "ab" * 32}], ["weights.safetensors"], {"a": 1}):
        run["models"] = models
        assert "run[0] models" in _failing(m), models


def test_host_and_models_do_not_touch_run_identity():
    """§7.2: neither enters the §7.1 derivation, so adding them is additive."""
    plain = runs.new_run("a:b", "1", SHA)
    decorated = runs.new_run("a:b", "1", SHA)
    decorated["host"] = {"os": "linux", "arch": "arm64"}
    decorated["models"] = [{"name": "w.pt", "sha256": "cd" * 32}]
    assert plain["run_id"] == decorated["run_id"]


def test_absent_host_and_models_are_not_a_defect():
    run = runs.new_run("a:b", "1", SHA)
    names = [n for n, ok, _ in runs.checks({"media_binding": {"files": [{"sha256": SHA}]},
                                            "machine_intelligence": [run]})]
    assert "run[0] host" not in names and "run[0] models" not in names
