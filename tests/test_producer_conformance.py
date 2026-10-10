"""The producer conformance runner (SPEC §16.4, W20).

It reuses the reference validator, so these tests prove the classification:
a validator-clean sample still leaves external checks unavailable, and a
sample that fails a P-check reports it.
"""

import json
import subprocess
import sys
from pathlib import Path

import hashlib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "conformance"))
import producer as pc  # noqa: E402

from openpicture import container, ed25519, runs, sign  # noqa: E402

REPORT_KEYS = {"suite", "generated_at", "sample", "validator", "checks", "totals",
               "incomplete", "producer_complete"}
ROW_KEYS = {"id", "requirement", "kind", "status", "detail", "requires"}


def _core(tmp_path, run_over=None, name="c.mov"):
    media = b"movie"
    run = {
        "run_id": runs.run_id("test:all", "1", hashlib.sha256(media).hexdigest()),
        "producer": "test:all", "model_version": "1",
        "facets": {"shots": [{"idx": 0, "confidence": None,
                              "span": {"frame_in": 0, "frame_out": 24}}]},
    }
    if run_over:
        run.update(run_over)
    m = {
        "opi": 0, "profile": "core",
        "media_binding": {"timecode": {"start": "00:00:00:00", "rate": {"num": 24, "den": 1},
                                       "drop_frame": False},
                          "files": [{"role": "original", "name": name, "size": len(media),
                                     "sha256": hashlib.sha256(media).hexdigest()}]},
        "machine_intelligence": [run], "editorial_annotations": {},
    }
    sign.sign_run(m, 0, ed25519.generate_secret(), signer="urn:test")
    path = tmp_path / (name + ".opi")
    container.write_core(m, path)
    return path, m


def _row(report, pid):
    return next(r for r in report["checks"] if r["id"] == pid)


def test_a_clean_sample_passes_decidable_checks_but_is_not_complete(tmp_path):
    path, _ = _core(tmp_path)
    report = pc.report_for(path)
    assert report["validator"]["ok"] is True
    assert report["totals"]["fail"] == 0
    assert report["totals"]["pass"] >= 8
    # P3, P12 and P15 are not decidable from a sidecar at all
    for pid in ("P3", "P12", "P15"):
        assert _row(report, pid)["status"] == "unavailable"
        assert _row(report, pid)["requires"]
    # a clean decidable check can still owe external evidence (P16)
    assert _row(report, "P16")["status"] == "pass" and _row(report, "P16")["requires"]
    assert report["producer_complete"] is False
    assert "P3" in report["incomplete"] and "P2" not in report["incomplete"]


def test_examples_are_classified_without_failure():
    for name in ("A001_C001.mov.opi", "A001_C001.mov.full.opi"):
        report = pc.report_for(ROOT / "examples" / name)
        assert report["validator"]["ok"] is True
        assert report["totals"]["fail"] == 0, [r for r in report["checks"] if r["status"] == "fail"]
        assert report["producer_complete"] is False


def test_full_example_owes_the_still_egress_policy():
    report = pc.report_for(ROOT / "examples" / "A001_C001.mov.full.opi")
    assert _row(report, "P10")["requires"]   # a keyframe member is present
    core = pc.report_for(ROOT / "examples" / "A001_C001.mov.opi")
    assert not _row(core, "P10")["requires"]  # no members, nothing owed


def test_a_broken_run_fails_its_producer_check(tmp_path):
    path, _ = _core(tmp_path, run_over={"run_id": "0" * 32})  # not the derived id
    report = pc.report_for(path)
    assert _row(report, "P6")["status"] == "fail"
    assert report["totals"]["fail"] >= 1 and report["producer_complete"] is False


def test_report_shape_is_stable(tmp_path):
    report = pc.report_for(_core(tmp_path)[0])
    assert set(report) == REPORT_KEYS
    assert report["suite"] == pc.SUITE
    assert set(report["totals"]) == {"pass", "fail", "unavailable"}
    for row in report["checks"]:
        assert set(row) == ROW_KEYS, row
        assert row["status"] in {"pass", "fail", "unavailable"}


def test_cli_exit_codes_and_report(tmp_path):
    good, _ = _core(tmp_path)
    out = tmp_path / "report.json"
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "conformance" / "producer.py"),
                        str(good), "--report", str(out), "--quiet"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    assert json.loads(out.read_text())["totals"]["fail"] == 0

    bad, _ = _core(tmp_path, run_over={"run_id": "0" * 32}, name="d.mov")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "conformance" / "producer.py"), str(bad)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 1 and "FAIL" in r.stdout
    assert "producer conformance: INCOMPLETE" in r.stdout
