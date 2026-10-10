"""The conformance runner (SPEC §16.6) against the reference validator and a fake."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tools" / "conformance" / "run.py"

sys.path.insert(0, str(ROOT / "tools" / "conformance"))
import run as conformance  # noqa: E402

REPORT_KEYS = {"suite", "generated_at", "validator", "classes", "totals", "vectors"}
ROW_KEYS = {"id", "class", "kind", "expected", "expected_check", "exit_code", "outcome", "reason_match",
            "observed_failures", "note"}


def test_self_run_is_all_pass():
    report = conformance.run_suite(conformance.REFERENCE_VALIDATOR)
    failing = [r for r in report["vectors"] if r["outcome"] == "fail"]
    assert not failing, [(r["id"], r["exit_code"], r["observed_failures"][:3]) for r in failing]
    assert report["totals"]["fail"] == 0
    assert report["totals"]["pass"] >= 40
    assert report["totals"]["unit_only"] >= 5
    # every must-fail vector that names a check was rejected for that reason
    mismatched = [r["id"] for r in report["vectors"] if r["reason_match"] is False]
    assert not mismatched, mismatched


def test_suite_covers_every_vector_directory():
    """SPEC §16.5: every directory under vectors/ is in the suite and catalogued."""
    on_disk = {p.name for p in (ROOT / "vectors").iterdir() if p.is_dir()}
    ids = {r["id"].split("/")[0] for r in conformance.collect()}
    assert ids == on_disk == {"manifest", "time", "runs", "members", "facets"}
    catalogue = (ROOT / "vectors" / "README.md").read_text()
    for name in on_disk:
        assert f"`{name}/`" in catalogue, f"vectors/README.md does not catalogue {name}/"


def test_report_shape_is_stable():
    report = conformance.run_suite(conformance.REFERENCE_VALIDATOR, dirs=["members"])
    assert set(report) == REPORT_KEYS
    assert report["suite"] == conformance.SUITE
    assert set(report["totals"]) == {"pass", "fail", "unit_only", "reason_mismatch"}
    for row in report["vectors"]:
        assert set(row) == ROW_KEYS, row
        assert row["outcome"] in {"pass", "fail", "unit-only"}
    assert report["classes"] == {"validator": {"pass": report["totals"]["pass"], "fail": 0}}


def test_a_validator_that_accepts_everything_fails_the_must_fail_vectors(tmp_path):
    fake = tmp_path / "yes.sh"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    report = conformance.run_suite(f"{fake} {{file}}", dirs=["members", "runs"])
    must_fail = [r for r in report["vectors"] if r["expected"] == "must-fail"]
    assert must_fail and all(r["outcome"] == "fail" for r in must_fail)
    assert all(r["outcome"] == "pass" for r in report["vectors"] if r["expected"] == "valid")
    assert report["totals"]["fail"] == len(must_fail)


def test_cli_writes_report_and_exit_codes(tmp_path):
    out = tmp_path / "report.json"
    r = subprocess.run([sys.executable, str(RUNNER), "--self", "--dir", "members", "--report", str(out), "--quiet"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    doc = json.loads(out.read_text())
    assert doc["totals"]["fail"] == 0 and doc["totals"]["pass"] == 11
    fake = tmp_path / "yes.sh"
    fake.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(fake, 0o755)
    r = subprocess.run([sys.executable, str(RUNNER), "--validator", f"{fake} {{file}}", "--dir", "members"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 1 and "FAIL" in r.stdout


def test_reason_mismatch_is_reported_not_failed():
    # A must-fail vector rejected for a different reason still passes on exit
    # code; reason_match records the disagreement.
    v = conformance.Vector("x", "validator", "manifest", "must-fail", "members.aligned")
    row = conformance.evaluate(v, 1, ["runs: run[0] producer"])
    assert row["outcome"] == "pass" and row["reason_match"] is False
    row = conformance.evaluate(v, 1, [])
    assert row["outcome"] == "pass" and row["reason_match"] is None
    row = conformance.evaluate(v, 0, [])
    assert row["outcome"] == "fail"
