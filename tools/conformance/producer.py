"""Producer conformance against SPEC §16.4's P-checks (W20).

`tools/conformance/run.py` answers the *Validator* question: does this file
conform? This answers a different one: **has a Producer met §16.4?** A file
that validates proves the structural checks P1/P4–P9/P11/P13/P16, and nothing
else. Half of §16.4 is not decidable from one file at all — the media was not
modified, the write was atomic, two runs of the same inputs are byte-identical
— and conflating "the validator accepted my output" with "I am a conforming
Producer" is the exact overclaim §16.8 forbids.

So every P-check is reported in one of three states:

- **pass** / **fail** — the requirement is decidable from the supplied file(s)
  and the reference validator (or a small producer obligation the tool checks:
  naming, run ordering). These reuse `openpicture.validate`.
- **unavailable** — the requirement needs evidence the file cannot carry. The
  row names what a producer must supply.

A row may be `pass` and still carry `requires`: a partly-decidable check whose
remaining half is external (P2's explicit destination, P10's egress policy,
P14, P16). `producer_complete` is true only when nothing failed, nothing is
unavailable, and no row still requires evidence. Validator success is never
producer conformance.

    python tools/conformance/producer.py clip.mov.opi
    python tools/conformance/producer.py clip.mov.opi --json --report report.json

Exit status is 0 when no P-check failed, 1 when one did, 2 for usage errors.
An `unavailable` check does not fail the command — it is reported, and it is
what keeps `producer_complete` false.

Standard library only, like the rest of the suite. The FILE under test is the
producer's output; the reference implementation is only the measuring stick.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from openpicture import EXTENSION, container, validate  # noqa: E402

SUITE = "opi-0 / 2026-08-29"

PASS, FAIL, UNAVAILABLE = "pass", "fail", "unavailable"


@dataclass
class Context:
    path: Path
    manifest: dict
    report: validate.Report
    form: str

    def select(self, *needles: str) -> list:
        """Check rows whose name contains every needle."""
        return [c for c in self.report.checks if all(n in c.name for n in needles)]

    def all_ok(self, *needles: str, required: bool = True) -> tuple[str, str]:
        """pass when every matching row is ok.

        With `required=True` (the default) a needle that matches no row is a
        failure — the requirement is mandatory. With `required=False` a needle
        with no row is skipped, for optional run keys (`egress`, `host`) and
        advisory facet rows where absence *is* the passing state.
        """
        details = []
        ok = True
        for needle in needles:
            hits = self.select(needle)
            if not hits:
                if required:
                    ok = False
                    details.append(f"no check matching {needle!r}")
                continue
            bad = [c for c in hits if not c.ok]
            if bad:
                ok = False
                details.append("; ".join(f"{c.name}: {c.detail}" for c in bad))
        return (PASS if ok else FAIL), "; ".join(details)

    @property
    def runs(self) -> list[dict]:
        raw = self.manifest.get("machine_intelligence")
        return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []

    @property
    def media_name(self) -> str | None:
        mb = self.manifest.get("media_binding")
        if not isinstance(mb, dict):
            return None
        for f in mb.get("files") or []:
            if isinstance(f, dict) and f.get("role", "original") == "original":
                name = f.get("name")
                return name if isinstance(name, str) else None
        return None


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    kind: str  # validator | producer | external
    evaluate: Callable[[Context], tuple[str, str]]
    requires: str = ""
    requires_when: Callable[[Context], bool] | None = None

    def owed(self, ctx: "Context") -> bool:
        """Whether the external half of this check is still owed for `ctx`."""
        if not self.requires:
            return False
        return self.requires_when is None or self.requires_when(ctx)


def _runs_sorted(c: Context) -> tuple[str, str]:
    keys = [(str(r.get("producer")), str(r.get("model_version"))) for r in c.runs]
    if keys != sorted(keys):
        return FAIL, f"runs are not ordered by (producer, model_version): {keys}"
    return PASS, ""


def _p6(c: Context) -> tuple[str, str]:
    if not c.runs:
        return UNAVAILABLE, "the sample carries no run to check"
    status, detail = c.all_ok("run_id derived", "producer", "model_version")
    if status == FAIL:
        return status, detail
    sort_status, sort_detail = _runs_sorted(c)
    return (sort_status, sort_detail) if sort_status == FAIL else (PASS, "")


def _p2(c: Context) -> tuple[str, str]:
    if c.media_name is None:
        return UNAVAILABLE, "no original media name in the manifest"
    expected = c.media_name + EXTENSION
    if c.path.name == expected:
        return PASS, ""
    return UNAVAILABLE, (
        f"sidecar is {c.path.name!r}, not {expected!r} beside the media — "
        "conformant only if the caller gave an explicit destination")


def _p10(c: Context) -> tuple[str, str]:
    return c.all_ok("embeddings.", "still.", required=False)


def _p11(c: Context) -> tuple[str, str]:
    invalid = c.select("invalid")
    bad = [n for n in invalid if n.name.startswith("run[")]
    if bad:
        return FAIL, f"runs with an invalid signature: {[c.name for c in bad]}"
    return PASS, ""


#: §16.4, row by row. `kind` says where the *decidable* part comes from;
#: `requires` names external evidence the file cannot carry, so a `pass`
#: with `requires` is still not a complete claim.
REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement("P1", "Write a ZIP always; manifest.json first; Core = manifest.json alone", "validator",
                lambda c: ((FAIL, f"form is {c.form!r}, not a ZIP (.opi)")
                           if c.form != "zip" else c.all_ok("manifest.present", "manifest.first",
                                                            "profile matches contents"))),
    Requirement("P2", "Name the sidecar <media filename>.opi beside the media unless the caller names an explicit destination",
                "producer", _p2),
    Requirement("P3", "Never modify, append to, or rewrite the media", "external",
                lambda c: (UNAVAILABLE, "not observable from a sidecar"),
                requires="a before/after digest of the master showing it was untouched"),
    Requirement("P4", "Serialize the manifest exactly as §5.5 specifies, opi first", "validator",
                lambda c: c.all_ok("opi is first key", "has opi", "opi version")),
    Requirement("P5", "Bind by sha256 for every file; carry timecode as a reduced rational rate or null", "validator",
                lambda c: c.all_ok("media_binding.files", "media_binding.original", "time: timecode")),
    Requirement("P6", "Derive run_id; give every run producer/model_version/facets; sort runs by (producer, model_version)",
                "validator", _p6),
    Requirement("P7", "Give every facet entry a confidence key (a number in scale, or null)", "validator",
                lambda c: (UNAVAILABLE, "the sample carries no run")
                          if not c.runs else c.all_ok("runs:", "facet", required=False)),
    Requirement("P8", "Express positions as integer frames with exclusive out; seconds/timecode agree", "validator",
                lambda c: c.all_ok("time:")),
    Requirement("P9", "Declare every member once with sha256/size/media_type; align .safetensors/.bin; no ZIP64/comment; fixed timestamps",
                "validator",
                lambda c: c.all_ok("attachments.single-owner", "attachments.all-declared",
                                   "attachments.all-present", "members.aligned",
                                   "container.no-zip64", "container.no-comment", "container.timestamps")),
    Requirement("P10", "Emit embeddings in the vectors layout with opi.* metadata; stills stripped and only under an egress that permits frames",
                "validator", _p10,
                requires="the declared egress policy permitted the still member(s) present",
                requires_when=lambda c: bool(c.select("still."))),
    Requirement("P11", "Sign each run it is entitled to sign; never sign editorial_annotations", "validator",
                _p11, requires="a statement of which runs the producer is entitled to sign"),
    Requirement("P12", "Write atomically (temp, fsync, rename); preserve the human layer on rewrite", "external",
                lambda c: (UNAVAILABLE, "atomicity is not observable from a finished file"),
                requires="a rewrite showing the human layer survived, and evidence of the atomic write"),
    Requirement("P13", "Emit sensitive facets only as review flags with review_required: true and no accuracy claim", "validator",
                lambda c: c.all_ok("review_required", "accuracy claim", required=False)),
    Requirement("P14", "Apply the data-egress policy at the write, and declare egress on runs carrying derived data or frames",
                "validator",
                lambda c: c.all_ok("egress", required=False), requires="the egress policy applied at the write"),
    Requirement("P15", "Be deterministic: the same inputs produce the same bytes apart from generated_at/signed_at/signatures",
                "external", lambda c: (UNAVAILABLE, "needs a second run of the same inputs"),
                requires="two outputs from the same inputs, differing only in generated_at/signed_at/signatures"),
    Requirement("P16", "Keep identity out of what it cannot take back: host is a class; by is never from an OS user name, email, signature or machine signer",
                "validator", lambda c: c.all_ok("host", required=False),
                requires="attestation that no label `by` was taken from an OS user name, email, signature or machine signer"),
)


def inspect(path: str | Path) -> Context:
    path = Path(path)
    manifest, _profile = container.read_manifest(path)
    report = validate.validate(path)
    return Context(path, manifest, report, container.detect(path))


def report_for(path: str | Path) -> dict:
    ctx = inspect(path)
    rows = []
    for req in REQUIREMENTS:
        try:
            status, detail = req.evaluate(ctx)
        except Exception as exc:  # a producer tool must not crash on a bad file
            status, detail = FAIL, f"check raised {type(exc).__name__}: {exc}"
        requires = req.requires if req.owed(ctx) else ""
        row = {"id": req.id, "requirement": req.text, "kind": req.kind,
               "status": status, "detail": detail, "requires": requires}
        rows.append(row)
    totals = {PASS: 0, FAIL: 0, UNAVAILABLE: 0}
    for r in rows:
        totals[r["status"]] += 1
    incomplete = [r["id"] for r in rows if r["status"] == UNAVAILABLE or r["requires"]]
    return {
        "suite": SUITE,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "sample": str(path),
        "validator": {"status": ctx.report.status, "ok": ctx.report.ok},
        "checks": rows,
        "totals": totals,
        "incomplete": incomplete,
        "producer_complete": totals[FAIL] == 0 and not incomplete,
    }


def _print_summary(report: dict) -> None:
    print(f"producer conformance · {report['sample']}")
    print(f"  validator: {report['validator']['status']}  "
          f"· pass {report['totals'][PASS]}  fail {report['totals'][FAIL]}  "
          f"unavailable {report['totals'][UNAVAILABLE]}")
    for r in report["checks"]:
        mark = {PASS: "ok  ", FAIL: "FAIL", UNAVAILABLE: "n/a "}[r["status"]]
        line = f"  {mark} {r['id']:>4} [{r['kind']}] {r['detail']}".rstrip()
        print(line)
        if r["requires"]:
            print(f"        requires: {r['requires']}")
    if report["validator"]["ok"]:
        print("  note: the validator accepted the sample; that is not producer conformance.")
    if report["producer_complete"]:
        print("  producer conformance: complete for the supplied sample")
    else:
        print(f"  producer conformance: INCOMPLETE — evidence still required for {report['incomplete']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="producer-conformance", description=__doc__.splitlines()[0])
    ap.add_argument("sample", help="a .opi file the producer wrote")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--report", metavar="PATH", help="write the JSON report here")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    try:
        report = report_for(args.sample)
    except (ValueError, OSError) as exc:
        print(f"{args.sample}: {exc}", file=sys.stderr)
        return 2
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif not args.quiet:
        _print_summary(report)
    return 1 if report["totals"][FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
