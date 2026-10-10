# Lane 6 handoff — OPI additive format alignment and producer tooling

**Status:** implementation complete, validated, committed on a lane branch.
Not merged, not pushed, not published. No format-major bump, no
facet-vocabulary freeze; the Open Picture format version stays `0`.

## 1. Worktree, branch, commits

| | |
|---|---|
| Worktree | `~/Lunar-Park/opi-latent-alignment` (isolated from the shared checkout) |
| Branch | `build/latent-alignment` |
| Base SHA | `61423fdf3280d908ab821d06a41fc92f3ed15417` (OPI `main`) |
| Implementation commit | `9ea4d2a` — 0.0.9 creator-workflow alignment, label diff, producer runner |
| Handoff commit | the commit that adds this file (final lane tip) |
| Own commits | `9ea4d2a`, then the handoff commit |

Nothing was merged into `main`, pushed, or published; the alpha repository
was not touched and no repository access or visibility changed.

## 2. Prerequisite SHAs incorporated

**None.** This lane is standalone in OPI: it was implemented and validated
against the stated OPI base with no Latent or other-lane commit folded in.
No cross-repo prerequisite was needed to reach the acceptance checks below.
The external interfaces this lane publishes for INGEST and EXCHANGE are in
§3 and §5 — those lanes consume them; they were not required here.

## 3. Files changed and public interfaces

Specification (normative chapters; `SPEC.md` regenerated from them):

- `spec/07b-attachments-and-members.md` — F1: `frame_spans` `[count, 2]` I64
  tensor, `spans` (ms) as fallback; readers prefer frames; `spans` attachment
  convenience key; validator requirement updated.
- `spec/appendix-c-proposed-facet-vocabulary-non-normative.md` — F2: `text`
  on canonical entries; C.9 realigned to §7b.3 (`vectors`/`frame_spans`,
  attachment keys).
- `spec/06-media-binding.md`, `spec/11-writer-requirements.md` — F3 portable
  paths.
- `spec/08-editorial-annotations-the-human-layer.md` — F4 (read-back owns
  `labels` only) and F5 (`by` never from a machine signer).
- `spec/16-conformance.md` — P16 wording.

Schemas: `schema/facets-0.schema.json` (`$defs/entry.text`).

Implementation (`openpicture/`, stdlib-only):

- `embeddings.py`
  - `FRAME_SPANS = "frame_spans"` (new public constant).
  - `spans(tensors) -> (unit, pairs)` (new): unit is `"frame"` / `"ms"` /
    `None`; pairs are `(start, end)`, `-1` untimed; prefers `frame_spans`.
  - `pack_vectors(..., frame_spans=[(frame_in, frame_out), ...])` (new kwarg).
  - `attachment_entry(...)` now emits `spans: "frame"|"ms"` when timed.
  - `problems(...)` validates `frame_spans` shape/dtype and the `spans`
    convenience key.
- `diff.py`
  - `LabelDiff` (new public dataclass: `added`/`changed`/`removed`, `.empty`,
    `.as_dict()`); `DiffResult.labels` (new field). Labels match on §8.2 `id`,
    falling back to `(name, value, span)` for un-`id`ed labels.
- `cli.py` — `diff` renders `label added/changed/removed`; help updated.
- `__main__.py` (new) — `python -m openpicture`.
- `__init__.py` — `__version__ = "0.0.9"`.

Tooling (not in the single-file bundle):

- `tools/conformance/producer.py` (new) — the §16.4 producer report.
  `report_for(path) -> dict`; CLI `producer.py SAMPLE [--json] [--report P]
  [--quiet]`. Each P-check row is `{id, requirement, kind, status, detail,
  requires}`; `kind ∈ {validator, producer, external}`, `status ∈ {pass,
  fail, unavailable}`; `producer_complete` is false while anything is
  unavailable or still `requires` evidence.
- `tools/README.md` documents it.

Generated artifacts kept in step (repo-required drift gates):

- `SPEC.md` (`build_spec.py`), `tools/opi_verify.py` (`build_bundle.py`),
  `docs/reference/cli.md` (`build_cli_docs.py`).

Tests and fixtures:

- `tests/test_embeddings.py`, `tests/test_annotate_diff.py`,
  `tests/test_cli_tools.py`, `tests/test_producer_conformance.py`,
  `tests/test_cross_producer_fixture.py`.
- `tests/fixtures/cross_producer.py` + `tests/fixtures/cross-producer.opi`
  (reproducible signed foreign file; `--check` gate).

Docs: `docs/status.md`, `CHANGELOG.md`.

## 4. Implemented behavior and representative commands

```bash
P=~/Lunar-Park/opi/.venv/bin/python

# validate a foreign fixture: still valid-signed
$P -m openpicture validate tests/fixtures/cross-producer.opi

# read frame-exact spans from a foreign member
$P - <<'PY'
from openpicture import reader, embeddings
side = reader.load("tests/fixtures/cross-producer.opi")
run = side.runs[0]; member = next(iter(run.attachments))
_, tensors = embeddings.unpack(side.read_member(member))
print(embeddings.spans(tensors))   # ('frame', [(0,24),(24,101),(101,240)])
PY

# compare labels by stable id
$P -m openpicture diff a.opi b.opi --json     # report["labels"]

# producer P-check report
$P tools/conformance/producer.py examples/A001_C001.mov.opi
$P tools/conformance/producer.py examples/A001_C001.mov.full.opi --json --report /tmp/p.json
```

Interfaces published for INGEST / EXCHANGE (exact, implemented):

- Embeddings: read the member with `openpicture.embeddings.unpack(bytes)`,
  then `openpicture.embeddings.spans(tensors)`. `unit == "frame"` means the
  pairs are `[frame_in, frame_out)` at the file's `media_binding.timecode.rate`
  and are exact; `unit == "ms"` is the fallback. The attachment convenience
  key `spans` gives the same answer from the manifest alone.
- Canonical facet entries may carry an optional `text` (string) as the
  searchable headline; it is equivalent to a row signal's `text`.
- Diff: `openpicture.diff.diff(a, b).labels` is
  `{"added": [...], "changed": [{"id","from","to"}], "removed": [...]}`.
- Producer conformance: `tools/conformance/producer.py --json` shape, with
  `producer_complete` explicitly false when external evidence is owed.

## 5. Validation commands and results

Run from the lane worktree with the intended checkout on `sys.path`
(`openpicture.__file__` resolved to the worktree, not the shared checkout):

```bash
$P -m pytest -q
# 439 passed, 11 skipped

$P tools/build_spec.py --check      # SPEC.md up to date
$P tools/build_bundle.py --check    # bundle up to date
$P tools/build_cli_docs.py --check  # docs/reference/cli.md up to date
$P tools/conformance/run.py --self --quiet   # validator suite all-pass
$P tools/opi_verify.py examples/*.opi        # valid-signed (CI stdlib step)
$P tools/opi_verify.py tests/fixtures/cross-producer.opi   # valid-signed
$P tools/conformance/producer.py tests/fixtures/cross-producer.opi --quiet  # exit 0
```

Cross-producer fixture gate: `python tests/fixtures/cross_producer.py --check`
is byte-stable (fixed key, fixed `generated_at`/`signed_at`, STOREd
container). CI scrub sweep (`git grep` for private identifiers) is clean on
tracked content.

Artifacts: `tests/fixtures/cross-producer.opi`;
producer reports are written wherever `--report` points.

## 6. Remaining limitations and unresolved decisions

- **Producer conformance is not decidable from one file.** The runner reports
  P3, P12 and P15 as `unavailable` and P2/P11/P14/P16 as carrying an external
  `requires`; this is deliberate, and `producer_complete` stays false. The
  tool does **not** accept a claims file that would flip these to pass — an
  unfalsifiable self-attestation is exactly what §16.8 warns against. If D
  wants producer attestations recorded, that is a policy decision, not a
  format one.
- **No native Premiere validation** is in this lane (out of scope for OPI);
  nothing here claims NLE delivery.
- **Frame-span interpretation needs the file's rate.** `frame_spans` is
  self-locating only against `media_binding.timecode.rate`, which is in the
  same `.opi`; a consumer holding a bare member must supply the rate. The
  spec says so; a fully self-contained rate on the member was not added
  (would duplicate the envelope).
- **Unresolved, left to D:** whether the `spans` attachment convenience key
  should ever be promoted to REQUIRED for a timed member (kept SHOULD/MAY,
  additive); and whether `frame_spans` should eventually displace the ms
  `spans` tensor entirely (kept as a permanent fallback while pre-freeze).
- **Latent half is not implemented here** — W7/W8/W10 (Latent intake that
  actually reads these fields, keeps original signed proof apart, and reports
  the three OPI starting conditions) belong to the Latent CORE/INGEST lanes.

## 7. Merge dependencies

- **Installation:** OPI is a stdlib-only package; from the merged checkout,
  `python -m pip install -e "~/Lunar-Park/opi"` (or run from the tree with it
  on `sys.path`). No new runtime dependencies. `tests/` needs `pytest`.
- **Integration order:** this OPI commit should land **before** the INGEST/
  DIGEST/EXCHANGE consumers that read `frame_spans`/`text`/`labels`, and
  before APP wiring and the reconciliation/alpha step. Latent's
  `latent/exchange/opi.py` depends on `openpicture` (pip `-e`, lazy import);
  no API it already calls changed incompatibly — only additions.
- **No other lane needs to be merged first** for this lane to be valid; it
  depends on nothing outside OPI at this base.
- Latent-side `W9` (the latent half of the format items) should follow the
  OPI commit: it reads `frame_spans`, stops writing a machine attribution into
  `by`, and stops projecting non-label annotation keys into the store.

---

## Summary for D

Lane 6 (OPI) is done on `build/latent-alignment` (base `61423fd`,
implementation `9ea4d2a` + handoff commit): all five additive format items
F1–F5, the label diff by stable id, `python -m openpicture`, and the producer
P-check runner, with SPEC.md/`opi_verify.py`/cli.md kept in step. 439 tests
pass, all drift and conformance gates green, and a reproducible signed
foreign fixture (`tests/fixtures/cross-producer.opi`) proves the additions
round-trip and that an annotation edit leaves original signed proof intact.
Existing files stay readable; no format-major bump; nothing pushed or merged.
The producer runner reports honestly that validator success is not producer
conformance (P3/P12/P15 unavailable, P2/P11/P14/P16 owe external evidence).
The Latent half (W7/W8/W10) is a separate lane and is the only real
integration dependency beyond landing this commit before the consumers.
