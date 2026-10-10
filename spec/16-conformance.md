## 16. Conformance

This chapter says what an implementation may claim, and what it must do to
claim it. Three classes exist. An implementation may claim any subset, and
may qualify a claim by profile (§3.3). Every MUST below is a cross-reference
to the rule that defines it; this chapter adds no new rules, it collects
them.

### 16.1 Classes

| Class | Claims to | Proven by |
|---|---|---|
| **Reader** | open a `.opi` and expose its contents correctly | the requirements in §16.2 and the reader clauses of the vector suite (§16.5) |
| **Validator** | decide whether a `.opi` conforms to this specification, and say why | every vector in the suite: valid files accepted, must-fail files rejected for the stated reason |
| **Producer** | write `.opi` files that a conforming validator accepts | the writer requirements in §16.4; its output validated by the reference validator or any conforming validator |

A **Reader** is not required to verify signatures cryptographically, but it
MUST report what it did not verify. A **Validator** is a Reader plus the
checks in §16.3. A **Producer** is not required to be a Reader, but a
Producer that rewrites existing files (§8.3) necessarily reads them.

### 16.2 Reader

A conforming Reader MUST:

| # | Requirement | Rule |
|---|---|---|
| R1 | Detect the physical form from the first bytes, never from the extension; accept the bare-JSON internal form only as documented | §3.2, §3.4 |
| R2 | Read `manifest.json` and derive the profile from the member list (Core = `manifest.json` alone), not from the `profile` key alone | §3.3, §3.5 |
| R3 | Refuse a file whose `opi` major it does not implement; otherwise ignore unknown top-level keys, unknown run keys, unknown facets and — in future majors — unknown reserved directories | §5.3, §4.3 |
| R4 | Bind a sidecar to media by `media_binding.files[].sha256`, never by `path` or by filename alone; treat `path` as untrusted text | §2.2, §6, §13 |
| R5 | Treat `editorial_annotations` as unsigned and mutable; never report a change to it as tampering | §8 |
| R6 | Report signature status **per run** — which run, which signer, which reason — using the vocabulary `valid` / `invalid` / `unsigned`, and the file-level vocabulary `signed` / `partial` / `unsigned` / `invalid`; never collapse `partial` into `signed`; treat an unsigned file as valid | §9.4 |
| R7 | Select the current run per producer by the §7.3 rule (`supersedes`, then latest `generated_at`, then array position) when several runs share a producer | §7.3 |
| R8 | Handle both profiles: read only `manifest.json` for Core semantics from a Full file; compute member data offsets from the local header and tolerate unknown extra-field records | §3.3, §4.4 |
| R9 | Interpret positions as integer frames at the rational rate, treat seconds and timecode strings as derived, and treat a `timecode: null` medium as seconds-only | §6A.2, §6A.3 |
| R10 | Never treat the absence of a sensitive facet as a negative determination | §10.3 |

A Reader that exposes embeddings MUST read them through the `vectors`
tensor and `opi.*` metadata (§7b.3). A Reader that cannot verify signatures
MUST say so rather than reporting `unsigned`.

### 16.3 Validator

A conforming Validator MUST implement every Reader requirement and MUST
evaluate the following checks, reporting each as pass or fail with a reason.
Check names are those of the reference implementation; another validator
MAY name its checks differently but MUST be able to map each of these to
one of its own (the conformance runner, §16.6, matches by substring).

| Group | Checks (reference names) | Rule |
|---|---|---|
| readable | `readable`, `canonical form` | §3.2, §3.4 |
| envelope | `has opi`, `has profile`, `has media_binding`, `opi version`, `opi is first key`, `profile matches contents` | §5 |
| binding | `media_binding`, `media_binding.files`, `media present`, `media sha256` | §6, §2.2 |
| human layer | `editorial_annotations` (must be an object) | §8 |
| time | `time: timecode.rate`, `time: timecode.label`, `time: timecode.start`, `time: duration`, `time: span <path>`, `time: spans` | §6A.7, §6.5 |
| runs | `runs: run[i] required`, `producer`, `model_version`, `run_id form`, `run_id derived`, `run_id unique`, `generated_at`, `egress`, `confidence_scale`, `attachments`, `attachment <name>`, `supersedes`, `depends_on`, `facet <name>` (confidence key on every entry) | §7.8 |
| members | `members: container.*` (readable, methods, no-encryption, no-data-descriptors, no-patched-data, no-zip64, no-comment, timestamps, entry-count, signature), `manifest.present`, `manifest.first`, `names.valid`, `names.case-unique`, `names.no-directory-entries`, `members.aligned`, `attachments.all-declared`, `attachments.all-present`, `attachments.single-owner`, `attachment.<name>`, `embeddings.<name>`, `still.<name>` | §4, §7b.6 |
| facets | `facets: run[i] <facet>` structure for **known** facets only, plus the sensitive-facet rules `review_required` and `accuracy claim` | Appendix C, §10.3 |
| signatures | `run[i] valid` / `invalid` / `unsigned`, per §9.4 | §9.4 |

A Validator MUST NOT reject a file for: unknown top-level keys; unknown run
keys; unknown facets; unknown keys *within* an attachment object (member
names themselves are constrained by §4.2–§4.3); a numeric `confidence` on a
measured facet (read as coverage, C.0.1); the absence of signatures. The
facet checks for unknown facets are "pass, not evaluated".

**Result vocabulary.** The file-level result is exactly one of:

| Result | Meaning | Exit code |
|---|---|---|
| `valid-signed` | every check passed; every run's signature verified | 0 |
| `valid-partial` | every check passed; some runs verified, none failed, some unsigned | 0 |
| `valid-unsigned` | every check passed; no run carries a signature | 0 |
| `invalid` | at least one check failed, or any signature failed to verify | 1 |

A command-line validator MUST exit `0` for the three `valid-*` results and
`1` for `invalid`, and SHOULD offer a machine-readable report with, at
minimum, `status` and a list of `checks` each carrying `name`, `ok` and
`detail`. Usage errors (no such file, bad arguments) SHOULD exit `2`.

### 16.4 Producer

A conforming Producer MUST:

| # | Requirement | Rule |
|---|---|---|
| P1 | Write a ZIP always; `manifest.json` first; Core = `manifest.json` alone | §3.1, §4.3 |
| P2 | Name the sidecar `<media filename>.opi` beside the media unless the caller names an explicit destination | §2.1 |
| P3 | Never modify, append to, or rewrite the media | §2.3 |
| P4 | Serialize the manifest exactly as §5.5 specifies, `opi` first | §5.5, §5.2 |
| P5 | Bind by `sha256` for every file; carry `timecode` as a reduced rational rate or `null` | §6, §6A.1, §6A.2 |
| P6 | Derive `run_id` as §7.1 specifies; give every run `producer`, `model_version`, `facets`; sort runs by (`producer`, `model_version`) | §7.1, §7.2, §7.7 |
| P7 | Give every facet entry a `confidence` key (a number in the run's scale, or `null`) | §7.5, C.0.1 |
| P8 | Express positions as integer frames with exclusive out; when seconds or timecode strings are also written, they agree | §6A.3 |
| P9 | Declare every member in exactly one run's `attachments` with `sha256`, `size` and `media_type`; store `.safetensors` and `.bin` members uncompressed at 64-byte-aligned offsets; write no ZIP64, no comment, fixed timestamps | §4.4–§4.7, §7b.1, §7b.2 |
| P10 | Emit embeddings in the `vectors [count, dim]` layout with the required `opi.*` metadata; emit stills stripped of metadata chunks, only under an egress declaration that permits frames | §7b.3, §7b.4 |
| P11 | Sign each run it is entitled to sign over the §9.2 payload; never sign `editorial_annotations` | §9.2, §9.3, §8 |
| P12 | Write atomically (temp file, `fsync`, rename); preserve the human layer of an existing file on rewrite | §11, §8.3 |
| P13 | Emit sensitive facets only as review flags with `review_required: true` and no accuracy claim | §10.3 |
| P14 | Apply any data-egress policy at the write, and declare `egress` on runs that carry derived data or frames | §11, §7.2 |
| P15 | Be deterministic: the same inputs produce the same bytes apart from `generated_at`, `signed_at` and signatures | §4.5, §7.7, §11 |
| P16 | Keep identity out of what it cannot take back: `host` names a machine class and never an instance; a label's `by` is never taken from an OS user name, an email address, a signature or a machine run's signer | §7.2, §8.2, §8.4, §13 |

A Producer proves conformance by validating its output. Its conformance
statement names the validator used.

### 16.5 The vector suite

The vectors under `vectors/` are the executable half of this specification.
They are versioned with the format: **suite `opi-0 / 2026-08-29`**. A vector
is either a **complete file** (a `.opi` on disk, or a manifest the runner
materialises into one) with an expectation `valid` or `must-fail <check>`,
or a **unit vector**: something that cannot be presented to a validator as
a file. Two things are. One is a function a Validator's internals should
reproduce — a rate label, a drop-frame conversion, a `run_id` derivation.
The other is a rule enforced by `schema/opi-0.schema.json` and by no
validator row (§5's table convention): a file breaking it is well-formed to
a validator, so the suite records the schema verdict instead.

`vectors/README.md` catalogues every directory and its JSON shape. A
conforming Validator MUST accept every complete-file vector marked valid and
MUST reject every must-fail vector; it SHOULD reject each for the stated
reason (matched by substring on its own check names).

### 16.6 The conformance runner and its report

`tools/conformance/run.py` runs any command-line validator against the
suite and writes a report. It is standard-library Python and is a public
artefact of this specification.

```
python tools/conformance/run.py --validator "my-validator --json {file}" \
                                --report report.json
python tools/conformance/run.py --self        # the reference validator; must be all-pass
```

The report is JSON with this shape (stable within a major):

```json
{
  "suite": "opi-0 / 2026-08-29",
  "generated_at": "2026-08-29T21:00:00Z",
  "validator": "my-validator --json {file}",
  "classes": {"validator": {"pass": 40, "fail": 0}},
  "totals": {"pass": 40, "fail": 0, "unit_only": 11, "reason_mismatch": 0},
  "vectors": [
    {
      "id": "members/case-misaligned.opi",
      "class": "validator",
      "kind": "file",
      "expected": "must-fail",
      "expected_check": "members.aligned",
      "exit_code": 1,
      "outcome": "pass",
      "reason_match": true,
      "observed_failures": ["members: members.aligned"]
    }
  ]
}
```

`outcome` is `pass` when the exit code agrees with the expectation, `fail`
otherwise, and `unit-only` for vectors that cannot be materialised.
`reason_match` is `true` when a failing check name contains the expected
check name, `false` when the file was rejected for a different stated
reason, and `null` when no expected check or no machine-readable report was
available. A `reason_match` of `false` does not fail the vector — a
validator may legitimately discover a different violation first — but the
count is reported so an implementer can see where their check granularity
differs from the reference.

### 16.7 Conformance statement

An implementation publishes a statement of this form, and keeps it current:

```
Implementation:  <name> <version>
Classes:         Reader (Core and Full) · Validator · Producer (Core only)
Specification:   .opi major 0, suite opi-0 / 2026-08-29
Validator used:  <name or "reference tools/opi_verify.py">   (Producers)
Runner report:   <URL or path to report.json>                (Validators)
Not claimed:     <e.g. "signature verification — reports 'unverified'">
Date:            <YYYY-MM-DD>
```

Partial conformance is stated by qualifying the class — "Reader, Core
profile only", "Validator, members checks not implemented" — never by
claiming a class and omitting requirements silently. A Reader that does not
verify signatures says so in *Not claimed*. A statement that omits the suite
version is not a conformance statement.

### 16.8 What conformance does not mean

Conformance is a statement about the file, not about the intelligence in it.
A conformant Producer may write facets that are wrong; a conformant
Validator confirms structure, binding and signatures, not truth. No class in
this chapter licenses an implementation to describe its output as accurate,
certified, or cleared (§10.3).
