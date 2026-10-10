"""Run a command-line .opi validator against the vector suite (SPEC §16.6).

    python tools/conformance/run.py --validator "my-validator --json {file}" --report report.json
    python tools/conformance/run.py --self                      # the reference validator

`{file}` in the validator command is replaced by the path of one `.opi`. The
validator MUST exit 0 for a valid file and 1 for an invalid one (§16.3). If
it prints JSON with a `checks` list of `{name, ok, detail}` objects, the
runner also matches the *reason* a must-fail vector was rejected.

Standard library only. Materialising manifest-shaped vectors into `.opi`
files uses the reference implementation from this repository (`openpicture`
on `sys.path`); the validator under test can be anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VECTORS = ROOT / "vectors"
SUITE = "opi-0 / 2026-08-29"
REFERENCE_VALIDATOR = f"{shlex.quote(sys.executable)} {shlex.quote(str(ROOT / 'tools' / 'opi_verify.py'))} --json {{file}}"

sys.path.insert(0, str(ROOT))
from openpicture import container, runs as opi_runs  # noqa: E402

# A medium every wrapped vector is bound to: 23.976 fps, three bytes of "media".
_SHA = hashlib.sha256(b"opi").hexdigest()
_BINDING = {
    "timecode": {"start": "00:00:00:00", "rate": {"num": 24000, "den": 1001}, "drop_frame": False},
    "files": [{"role": "original", "name": "clip.mov", "size": 3, "sha256": _SHA}],
}


# ── vectors ──────────────────────────────────────────────────────────────


class Vector:
    """One thing to hand a validator, or one thing we cannot."""

    def __init__(self, vid: str, klass: str, kind: str, expected: str | None = None,
                 expected_check: str | None = None, manifest: dict | None = None,
                 file: Path | None = None, note: str = ""):
        self.id, self.klass, self.kind = vid, klass, kind
        self.expected, self.expected_check = expected, expected_check
        self.manifest, self.file, self.note = manifest, file, note

    def __getitem__(self, key: str):
        """Expose the stable report fields for lightweight suite inspection."""
        return getattr(self, key)


def _load(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def _wrap(facet: str, entries, rid_suffix: str) -> dict:
    """A complete manifest around facet entries (vectors/README.md, facets/)."""
    entries = [dict(e) for e in (entries if isinstance(entries, list) else [entries])]
    flattened = []
    for entry in entries:
        payload = entry.get("payload")
        if isinstance(payload, dict):
            flat = dict(payload)
            flat.update({k: v for k, v in entry.items() if k not in {"kind", "payload"}})
            entry = flat
        flattened.append(entry)
    entries = flattened
    for e in entries:
        e.setdefault("confidence", None)
    producer, mv = "conformance:vectors", f"1-{rid_suffix}"
    return {
        "opi": 0, "profile": "core",
        "media_binding": _BINDING,
        "machine_intelligence": [{
            "run_id": opi_runs.run_id(producer, mv, _SHA),
            "producer": producer, "model_version": mv,
            "facets": {facet: entries},
        }],
        "editorial_annotations": {},
    }


def collect(dirs: list[str] | None = None) -> list[Vector]:
    out: list[Vector] = []
    want = set(dirs) if dirs else None

    def take(d: str) -> bool:
        return want is None or d in want

    if take("members"):
        exp = _load(VECTORS / "members" / "expected.json")
        valid = exp["valid"]["file"]
        out.append(Vector(f"members/{valid}", "validator", "file", "valid", file=VECTORS / "members" / valid))
        for name, case in sorted(exp["cases"].items()):
            out.append(Vector(f"members/{name}", "validator", "file", "must-fail", case["must_fail"],
                              file=VECTORS / "members" / name, note=case.get("why", "")))

    if take("manifest"):
        for p in sorted((VECTORS / "manifest").glob("*.json")):
            d = _load(p)
            vid = f"manifest/{p.name}"
            expect = d.get("expect", {})
            if "manifest" not in d or expect.get("validator") is None:
                # `invalid-oversize.json` is synthetic (no manifest to ship), and a
                # vector the schema catches but no validator row does yet cannot
                # be handed to a validator as a file. Both are unit-only.
                out.append(Vector(vid, "validator", "unit-only", note=d.get("title", "")))
                continue
            expected = "valid" if expect["validator"] == "valid" else "must-fail"
            out.append(Vector(vid, "validator", "manifest", expected, expect.get("check"),
                              manifest=d["manifest"], note=d.get("title", "")))

    if take("runs"):
        for p in sorted((VECTORS / "runs").glob("*.json")):
            d = _load(p)
            vid = f"runs/{p.name}"
            if "manifest" in d:
                exp = d.get("expect", {})
                if exp.get("failing"):
                    out.append(Vector(vid, "validator", "manifest", "must-fail", exp["failing"][0], manifest=d["manifest"]))
                else:
                    out.append(Vector(vid, "validator", "manifest", "valid", manifest=d["manifest"]))
            elif "before" in d and "after" in d:
                out.append(Vector(vid + "#before", "validator", "manifest", "valid", manifest=d["before"]))
                out.append(Vector(vid + "#after", "validator", "manifest", "valid", manifest=d["after"]))
            else:
                out.append(Vector(vid, "validator", "unit-only", note=d.get("description", "")))

    if take("facets"):
        for p in sorted((VECTORS / "facets").glob("*.json")):
            d = _load(p)
            expected = "must-fail" if "expect_failure_in" in d else "valid"
            out.append(Vector(f"facets/{p.name}", "validator", "manifest", expected, d.get("expect_failure_in"),
                              manifest=_wrap(d["facet"], d["entry"], p.stem)))

    if take("time"):
        for p in sorted((VECTORS / "time").glob("*.json")):
            d = _load(p)
            if p.name != "consistency.json":
                out.append(Vector(f"time/{p.name}", "validator", "unit-only", note=d.get("description", "")))
                continue
            for i, case in enumerate(d["cases"]):
                producer, mv = "conformance:time", f"1-{i}"
                m = {
                    "opi": 0, "profile": "core",
                    "media_binding": {
                        "timecode": None if case.get("rate") is None else {
                            "start": case.get("start", "00:00:00:00"), "rate": case["rate"],
                            "drop_frame": case.get("drop_frame", False)},
                        "files": _BINDING["files"],
                    },
                    "machine_intelligence": [{
                        "run_id": opi_runs.run_id(producer, mv, _SHA), "producer": producer, "model_version": mv,
                        "facets": {"shots": [{"idx": 0, "span": case["span"], "confidence": None}]},
                    }],
                    "editorial_annotations": {},
                }
                out.append(Vector(f"time/consistency.json#{i}", "validator", "manifest",
                                  "valid" if case["valid"] else "must-fail",
                                  None if case["valid"] else "time: span", manifest=m, note=case.get("note", "")))
    return out


# ── running ──────────────────────────────────────────────────────────────


def materialise(v: Vector, workdir: Path) -> Path:
    if v.file is not None:
        return v.file
    target = workdir / (v.id.replace("/", "__").replace("#", "_") + ".opi")
    container.write_core(v.manifest, target)
    return target


def run_validator(template: str, path: Path, timeout: float = 120.0) -> tuple[int, list[str]]:
    """Exit code and the names of failing checks, if the validator spoke JSON."""
    cmd = shlex.split(template.replace("{file}", shlex.quote(str(path))))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    failures: list[str] = []
    text = proc.stdout.strip()
    if text:
        try:
            doc = json.loads(text)
            docs = doc if isinstance(doc, list) else [doc]
            for d in docs:
                for c in d.get("checks", []) if isinstance(d, dict) else []:
                    if isinstance(c, dict) and c.get("ok") is False:
                        failures.append(str(c.get("name", "")))
        except json.JSONDecodeError:
            pass
    return proc.returncode, failures


def evaluate(v: Vector, exit_code: int, failures: list[str]) -> dict:
    row = {
        "id": v.id, "class": v.klass, "kind": v.kind, "expected": v.expected,
        "expected_check": v.expected_check, "exit_code": exit_code,
        "observed_failures": failures, "note": v.note,
    }
    if v.expected == "valid":
        row["outcome"] = "pass" if exit_code == 0 else "fail"
        row["reason_match"] = None
    else:
        row["outcome"] = "pass" if exit_code == 1 else "fail"
        if v.expected_check and failures:
            row["reason_match"] = any(v.expected_check in f for f in failures)
        else:
            row["reason_match"] = None
    return row


def run_suite(template: str, dirs: list[str] | None = None, klass: str | None = None) -> dict:
    vectors = [v for v in collect(dirs) if klass is None or v.klass == klass]
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="opi-conformance-") as tmp:
        workdir = Path(tmp)
        for v in vectors:
            if v.kind == "unit-only":
                rows.append({"id": v.id, "class": v.klass, "kind": v.kind, "expected": None, "expected_check": None,
                             "exit_code": None, "outcome": "unit-only", "reason_match": None,
                             "observed_failures": [], "note": v.note})
                continue
            path = materialise(v, workdir)
            code, failures = run_validator(template, path)
            rows.append(evaluate(v, code, failures))
    classes: dict[str, dict] = {}
    totals = {"pass": 0, "fail": 0, "unit_only": 0, "reason_mismatch": 0}
    for r in rows:
        if r["outcome"] == "unit-only":
            totals["unit_only"] += 1
            continue
        c = classes.setdefault(r["class"], {"pass": 0, "fail": 0})
        c[r["outcome"]] += 1
        totals[r["outcome"]] += 1
        if r["reason_match"] is False:
            totals["reason_mismatch"] += 1
    return {
        "suite": SUITE,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "validator": template,
        "classes": classes,
        "totals": totals,
        "vectors": rows,
    }


def _print_summary(report: dict) -> None:
    t = report["totals"]
    print(f"suite {report['suite']} · validator: {report['validator']}")
    print(f"  pass {t['pass']}  fail {t['fail']}  unit-only {t['unit_only']}  reason mismatch {t['reason_mismatch']}")
    for r in report["vectors"]:
        if r["outcome"] == "fail":
            print(f"  FAIL  {r['id']}  expected {r['expected']}"
                  + (f" ({r['expected_check']})" if r["expected_check"] else "")
                  + f", exit {r['exit_code']}"
                  + (f", failures: {', '.join(r['observed_failures'][:4])}" if r["observed_failures"] else ""))
        elif r["reason_match"] is False:
            print(f"  note  {r['id']}  rejected, but not for '{r['expected_check']}': {', '.join(r['observed_failures'][:4])}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="conformance", description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--validator", metavar="CMD", help="validator command; {file} is replaced by each .opi path")
    g.add_argument("--self", action="store_true", help="run the reference validator (tools/opi_verify.py)")
    ap.add_argument("--class", dest="klass", choices=["validator"], help="only vectors for this conformance class")
    ap.add_argument("--dir", action="append", choices=["manifest", "time", "runs", "members", "facets"],
                    help="only these vector directories")
    ap.add_argument("--report", metavar="PATH", help="write the JSON report here")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    template = REFERENCE_VALIDATOR if args.self else args.validator
    report = run_suite(template, args.dir, args.klass)
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not args.quiet:
        _print_summary(report)
    return 0 if report["totals"]["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
