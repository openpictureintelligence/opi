# Changelog

> Versioning: 0.0.x during the public, pre-freeze alpha. Only the steward approves a 0.x.0 bump.

> **2026-08-30 — history rewritten before publication** to remove internal
> paths, identifiers and machine names from every commit. Commit hashes
> before this date are not stable and refer to the private archive copy.

## Public alpha — 2026-10-09

The reference implementation remains 0.0.9 and the format remains major 0,
pre-freeze. Public source access, contribution guidance, and private
vulnerability reporting are available. Install from a validated source
commit; no PyPI distribution, registration, or format freeze is claimed.

## 0.0.9 — 2026-10-09

**Creator-workflow format alignment (F1–F5) and producer tooling.** Additive
and pre-freeze: no format-major bump, no `run_id` moves, every 0.0.8 file is
still valid and readable. The Open Picture format version stays `0`.

**F1 — frame-exact embedding spans.** §7b.3 gains an optional `frame_spans`
`[count, 2]` I64 tensor carrying `[frame_in, frame_out)` per row, so a timed
row is exact at the media's rational rate; the millisecond `spans` tensor
stays as the backward-compatible fallback and a reader MUST prefer frames
when both are present. A new `spans` attachment convenience key says which
the member carries. `openpicture.embeddings.spans()` returns `(unit, pairs)`
so a consumer can tell without parsing the rate itself.

**F2 — searchable `text` on a canonical facet entry.** Appendix C's common
entry keys and `facets-0.schema.json` `$defs/entry` now bless an optional
`text`: the headline value a store-backed producer already writes on a row
signal, hoisted onto the canonical form.

**F3 — portable media paths.** §6.2/§6.4/§11 now say writers SHOULD omit
`files[].path` and `provenance[].original_path`; when a location is written
it SHOULD be relative and MUST NOT be an absolute path, a home directory or a
user name. Matching is by `name` + `sha256` and was already; a validator
still MUST NOT fail a file over any path.

**F4 — non-label editorial annotation keys.** §8.3 states plainly that a
read-back producer owns `labels` only: it MUST NOT project any other clause
into its store as a label, rewrite it as an `opi.<key>` label, or write it
twice. The clauses are the holder's and are carried forward verbatim.

**F5 — human attribution, never invented.** §8.2/§8.4/§16.4 P16 now say in one
breath that a machine, a run or a signature is not a person: a tool fills
`created_by` and MUST NOT fill `by`, and read-back MUST NOT copy a run's
`signature.signer` into it.

**W17 — `openpicture diff` matches human labels by `id`.** Added, changed and
removed are decided on §8.2's stable `id`; a label without one is matched on
`(name, value, span)`. The JSON report gains a `labels` block; the text
summary prints `label added/changed/removed`.

**W18 — `python -m openpicture`.** A `__main__` module runs the same CLI
without the console script installed.

**W20 — producer P-check conformance runner.** `tools/conformance/producer.py`
reports every §16.4 P-check as pass, fail or unavailable, distinguishes
file-decidable checks from producer obligations and checks needing external
evidence, and never treats validator success as producer conformance.

**Published for INGEST/EXCHANGE.** `tests/fixtures/cross-producer.opi` is a
reproducible, signed Full file from a foreign producer exercising F1–F5 at
once (frame spans, a `text` entry, absolute foreign paths, non-label
annotation clauses, a label with no `by`, an unknown run key). A supported
annotation edit leaves it `valid-signed` with the original foreign proof
byte-identical.

**Docs.** `docs/status.md` refreshed; `docs/reference/cli.md` regenerated.

## 0.0.8 — 2026-08-30

**Ingest provenance.** The `.opi` half of the decisions in
`opi-latent-ingest-decisions.md`: what a run may say about where it ran, and
what a label may say about who made it. Additive — nothing existing changes
meaning, no `run_id` moves, and every 0.0.7 file is still valid.

**§7.2 — `host` and `models` on a run, both optional, both signed.** `host`
is a *class* of machine (`os`, `arch`, `accelerator`, from closed
vocabularies) and never an instance: a hostname or user name written under a
run signature cannot be removed again without destroying the signature, so
the validator rejects anything outside the vocabulary and §13 says why.
`models` is `[{name, sha256}]` — the artefacts the run consumed, named as
files rather than as prose. Neither enters the §7.1 derivation.

**§8.2 — `by`, `at`, `notes` and a stronger `id`.** `created_by` keeps its
meaning (where the *record* came from); `by` is new and says which human
formed the judgement, self-declared and covered by no signature. §8.2 and
§13 forbid deriving it from a signature or filling it from an OS user name
or an email address. `id` must now stay stable across rewrites, because
§8.4's read-back matches on it.

**§8.4 — read-back converges on `id`.** The B23 rule (never destroy what the
store holds) is unchanged; what is new is the four-case matching table and
the rule that **a retraction is an absence**. `value: null` was proposed for
this and rejected: §8.2 already gives it to bare tags, and a file full of
bare tags must not read as a file full of retractions.

**§12 — a recommended conflict rule for readers that keep a store.** Signed
over unsigned, then key trust, then `generated_at`, then keep what you hold
and report it. Recommended, not required: the format does not own anyone's
index, but every store hits this, and one that resolves it differently each
run is worse than one that resolves it wrongly but predictably.

Also: §11 writer bullets and §16.4 P16 for the two privacy rules; two run
vectors (`valid-`/`invalid-host-and-models.json`); schema coverage for all
of it.

**CLI, breaking in the small.** `openpicture annotate --by` now sets the
label's `by` (the human) rather than `created_by` (the record), and
`--created-by` sets `created_by`, defaulting to this tool. `--by` no longer
defaults to `$USER` — that default wrote a real person's OS account name
into files that travel, which is now forbidden outright. New: `--at`,
`--note`, and `--anonymous`, which strips `by` and `at` from every label and
deliberately leaves `created_by`, since §8.2 requires it.

**Fixed:** `annotate.add_label` wrote `"span": null` when given no span.
§8.2 gives an *absent* span the meaning "the whole medium", which `null`
does not have, and the published schema types `span` as an object — so
every label the CLI wrote without a span failed third-party schema
validation. Optional keys are now omitted rather than nulled.

## 0.0.7 — 2026-08-29

**Decision B12 is closed.** Seven facets are frozen and Appendix C is
normative for them; the embeddings attachment form was already normative in
§7b.3. Eight things in all. The rest of the appendix stays a set of
proposals: producers may emit them, validators ignore them, nobody claims
conformance on them.

Frozen: `shots`, `transcript`, `usability`, `exposure_color`,
`energy_curve`, `audio_usability`, `camera_motion`.
Held: `description`, `shot_size`, `composition`, `focus`, `take`,
`continuity`, `clearance`, `text_on_screen`, `persons`, `audio_events`, and
the embeddings *facet* form. The criterion was evidence — a producer emits
it today, from real footage, with these keys. `description` is designed and
settled but nothing emits it, so it waits. `clearance` is deliberately never
frozen as a quality claim; §10.3's rules about it were always normative, the
field list is not.

**Appendix C now describes facets on two axes.** `shape` (`frozen` /
`proposed`) is about the keys; `maturity` (`stable` / `proposed` /
`research`) is about the producer. Collapsing them into one word is what the
decision had to undo: `camera_motion` is an ISO vocabulary from 2002 whose
keys will not move, computed by a producer that is frankly research-grade,
and `stable (research-grade)` could not carry both. It is now `frozen` +
`research`, and `openpicture.facets.Facet` carries the same two fields.

The five open questions, answered in the specification rather than only in
the memo:

1. **Confidence scale** — `unit` is frozen as the default, `bp` stays
   optional (C.0.1). Forcing integers everywhere was argued for so
   third-party canonicalizers stayed trivial; RFC 8785 implementations now
   exist in every language a producer is likely written in.
2. **`camera_motion`** — shape frozen, maturity `research`, confidence cap
   kept (C.7). The cap is now stated for what it is: a **writer**
   requirement, relative to the producer's own ceilings, which a validator
   cannot check from one file. What it *can* see — an ambiguous verb scoring
   at or above a resolvable one — is reported as a note on a passing check,
   never a failure, because a short run can produce it honestly.
3. **Row form vs canonical** — permanently equivalent (C.0). Neither is
   deprecated and there is no hoisting deadline; one branch in every reader
   beats a transform in every store-backed producer.
4. **`log_profile`** — enumerated (C.5): `ARRI_LogC3` `ARRI_LogC4`
   `Sony_SLog2` `Sony_SLog3` `Panasonic_VLog` `Canon_CLog2` `Canon_CLog3`
   `Nikon_NLog` `RED_Log3G10` `BMD_BRAWFilm` `Rec709`, with
   `x-<vendor>_<profile>` for anything else and `null` for *not identified*.
   Free text alone drifts into `slog3`, `S-Log3` and `sony_slog_3` inside a
   year. Adding a name is additive; renaming one is not.
5. **Calibration flag** — decided against (C.0.1). A boolean asserting one's
   own calibration is unfalsifiable from inside the file, and §10.3 already
   refuses accuracy claims for the facets where it would matter most; §16.7's
   conformance statement is where a producer says how it measured.

Nothing that was valid at 0.0.6 becomes invalid. The three real pilot-run
sidecars still validate `valid-signed` against the frozen vocabulary.

## 0.0.6 — 2026-08-29

Reconciling the two halves of the deep specification pass. Chapters 04, 06a,
07, 07b and Appendix C were written in part 1; chapters 05, 06, 08 and 16 in
part 2. Where the two halves describe the same thing they now say the same
thing:

- **The confidence rule was stated twice, differently.** §7.5 said `null`
  means "did not estimate" and that a measurement the producer is certain of
  carries `1.0`; C.0.1 said a *measured* facet sets `confidence` to `null`
  and that a number on one is read as `coverage`. Under the first rule a
  producer emitting `1.0` for exposure statistics is correct; under the
  second that same `1.0` is silently reinterpreted as coverage. C.0.1 is what
  `openpicture.facets` implements, so §7.5 now states that rule: the key is
  always present, `null` covers both "not estimated" and "measured, so there
  is nothing to be unsure about", and a measured entry SHOULD carry
  `coverage`. Which facets are measured stays vocabulary, and stays C.0.1's
  to say.
- **`media_type` was optional in §7.6 and REQUIRED in §7b.2** — and required
  in the schema, and in §16.4 P9. §7.6 no longer carries its own stale copy
  of the attachment object; it defines the ownership rule and points at
  §7b.2 for the shape.
- **§6A.3.5 and C.1 contradicted each other at a shot boundary.** Floor-in /
  ceil-out applied independently to both sides of one cut overlaps by a frame
  wherever the cut does not land on one, and C.1 forbids exactly that
  overlap. §6A.4 now says how a decomposition derives a shared boundary:
  once, by ceiling, so the frame a cut falls in belongs to the outgoing shot
  — which is what C.1's example, §6A.3's example and
  `vectors/facets/valid-shots.json` have carried all along. Outer edges are
  §6A.3.5 unchanged. Found by the reference producer, which could not satisfy
  both texts at once.
- **C.0.1 cited `confidence_calibrated: true` as a §7 run key.** No such key
  exists — not in §7.2, not in the schema, not in the implementation. The
  reference is removed, and whether to add such a flag is now an open
  question in `proposals/decided/facets-freeze-2026-08-29.md` (recommendation: no —
  a boolean asserting one's own calibration is unfalsifiable from inside the
  file).
- **C.1 let a shot omit `confidence`** ("undefined for `idx: 0`, MAY be
  omitted there") while §7.5 requires the key on every entry and
  `openpicture.runs.checks` fails an entry without it — the vector suite was
  papering over the gap by having the conformance runner insert the key when
  materialising a facet vector. C.1 now says what shot 0 writes: `null`.
  `vectors/facets/valid-shots.json` carries it.
- **`validate._attachments` claimed to enforce ownership and did not.** It
  failed only when two runs declared the same member *differently*, letting
  an identical duplicate through — which §7.6 forbids "even with identical
  hashes". Ownership is decided by `runs.checks` from the manifest
  (`runs: run[i] attachment <name>`, any profile) and by `members.checks`
  from the archive (`attachments.single-owner`, Full); both were already
  correct. The union survives only to answer §7.6's other rule, that a Core
  manifest declares no attachments.
- **Where the confidence rule is enforced is now stated once**, in C.0.1:
  presence and scale are the envelope's and binding, for every facet known
  or not; whether a facet is *measured* is vocabulary, checked against
  Appendix C and only advisory. `schema/facets-0.schema.json` states the same
  rule in the same words, and says that it does not itself enforce presence.
- Smaller: C.0's `span` row restated a partial copy of §6A at `SHOULD` while
  §7.5 said `MAY`; §7.8's summary said a member is declared by "at most one"
  run while §7.6 and §7b.1 said "exactly one"; §7.5 quoted the facet-name
  pattern with an undefined `<vendor>` placeholder that could not be compared
  to `FACET_NAME_RE`.

New drift gates in `tests/test_spec_xrefs.py`: a regex quoted in the prose
must be one the reference compiles (and the schema must agree), and a
reference like §6A.3.5 is now resolved against the numbered list it points
into rather than allowlisted, so §6A.3.9 would fail.

## 0.0.5 — 2026-08-29

Deep specification pass, part 2 — the manifest key by key, and a
conformance chapter that says what an implementation may claim:

- **§5 Manifest envelope, §6 `media_binding`, §8 `editorial_annotations`**
  (rewritten): every key given a type, a requirement level, its range,
  whether a run signature covers it, who legitimately writes it, and the
  validator row that enforces it. `media_binding` gains `duration_frames`,
  `xxh64be` and a `provenance[]` array; §6.3 states exactly-one-original and
  why; §8 states preservation-on-rewrite (§8.3) and read-back (§8.4, B23).
- **§16 Conformance** (new): Reader, Validator and Producer classes, each a
  numbered MUST list cross-referenced to the rule that defines it; the
  result vocabulary and exit codes; the vector suite as the executable half
  of the specification, versioned `opi-0 / 2026-08-29`; a conformance
  statement template; and §16.8, which says conformance is a statement
  about the file, never about the intelligence in it.
- **`schema/opi-0.schema.json`** tightened to say what the chapters say:
  RFC 3339 date-times, the `role` enumeration, exactly-one-original via
  `contains`/`minContains`/`maxContains`, basename `name`, `media_type`
  required on attachments, the `producer` `vendor:pass` pattern, run
  required keys, member-name patterns, and a `labels[]` shape.
- **`tools/conformance/run.py`** (new): runs any command-line validator
  against the suite and writes the §16.6 report, matching the *reason* a
  must-fail vector was rejected. `--self` is all-pass: 72 pass, 0 fail,
  9 unit-only, 0 reason mismatch.
- **`vectors/manifest/`** (new): 15 vectors for §5, §6 and §8, each naming
  the check it is expected to fail. `vectors/README.md` catalogues every
  directory and its JSON shape.

Fixed in review of the above:

- `media_binding.original` and `time: duration` were named in §6's Check
  columns and in §6.5's MUST list but no validator implemented them: a
  manifest with zero or two originals, or a `duration_frames` that
  contradicts `duration_s`, passed `openpicture validate`. Both now exist.
  `media_binding.files` also enforces §6.2's basename rule.
- Stale §-references left behind as chapters were written one at a time
  (§8.1 for the human layer's preservation rule, §5.2 for unknown keys,
  §7.5 for attachments, §4.3 for the 2 GiB ceiling and for alignment,
  §7.3 for determinism, `§6a` for `§6A`). §10 gained numbered subsections
  so Appendix C's citation of §10.2 resolves. `tests/test_spec_xrefs.py`
  is the drift gate.
- `vectors/manifest/` was not collected by the conformance runner, so the
  published suite did not exercise the manifest chapter at all.
- GitHub issue and pull-request templates; `docs/build/producers.md`
  defines the `flat_vectors` stand-in its example uses; the home page keeps
  its navigation drawer below 60em.

## 0.0.4 — 2026-08-29

Deep specification pass, part 1 — the format is now defined chapter by
chapter in `spec/` (SPEC.md is generated):

- **§6a Time model** (new): reduced rational rates, integer frame positions
  with exclusive out, derived seconds/timecode that MUST agree, SMPTE
  drop-frame at 30000/1001, 60000/1001, 120000/1001, floor-in/ceil-out,
  round-trip formulas for FCPXML/OTIO/EDL/xmeml. `openpicture.time`;
  vectors in `vectors/time/`.
- **§7 Runs** (rewritten): `run_id` is derived — `sha256(JCS({producer,
  model_version, sha256}))[:32]`; producer `vendor:pass` naming; `supersedes`
  / `depends_on` lineage; re-run replaces in place; writers sort runs; every
  facet entry carries a `confidence` key (number or `null`). `openpicture.runs`.
- **§4 / §7b Container and members** (rewritten/new): ISO 21320-1 profile
  restated, reserved directories `embeddings/ keyframes/ extensions/`,
  ASCII case-insensitive uniqueness, ZIP64 prohibited, fixed timestamps,
  exactly-one-owner attachments with `media_type`, safetensors `vectors
  [count, dim]` layout with required `opi.*` metadata, stills as FRAMES-class
  egress with metadata chunks forbidden. `openpicture.members`.
- **Appendix C Facets** (rewritten): every facet field by field with
  maturity (stable / proposed / research), MPEG-7 verbs, IPTC names,
  confidence conventions, the §10.3 sensitive-facet rule enforced.
  `openpicture.facets`; `schema/facets-0.schema.json` regenerated;
  `proposals/decided/facets-freeze-2026-08-29.md` for the B12 decision.
- Validator runs every chapter's checks through a registry; the single-file
  `tools/opi_verify.py` carries all of them.
- Docs site rebuilt to the look-and-feel brief; examples sanitized and
  re-signed with derived run ids; `pack` stamps the correct profile and
  `media_type`; `sign` and `annotate` rewrite Full files in place.

## 0.0.3 — 2026-08-29

- `embeddings.member_name` sanitises to `[A-Za-z0-9._-]` (colon → `-`, slash → `_`), so a member named after a producer like `emb:visual` extracts on every filesystem.

## 0.0.2 — 2026-08-29

Decisions taken (see the behavior spec §13 and `DECISIONS.md`):

- **B14 — a `.opi` is always a ZIP.** Core = a container whose only member is
  `manifest.json`; Full adds members. `container.detect()` now reports the
  byte form (`"zip"` / `"json"`); the profile is a property of the contents
  (`profile_of_members`). `write_core` writes a ZIP; `write_json` writes the
  bare internal form, which readers still accept and the validator flags
  (not fails) as non-canonical. Examples regenerated as ZIPs and re-signed.
- **B21 — the command is `openpicture`.** The bare `opi` entry point is gone
  (openSUSE's package installer and the Linux Foundation OPI Project own
  that name). Module names unchanged.
- **B15 — key log decided.** Append-only, keys never withdrawn; the public
  key hex is the key id. SPEC §9.3 / §13 updated.
- **Sensitive facets (SPEC §10.3).** Clearance facets — minors, faces, logos,
  licensed music — are review flags with `review_required: true`, never
  determinations; no accuracy claim may travel in the file; absence is not a
  negative.
- **Proposed facet vocabulary** — SPEC Appendix C and
  `schema/facets-0.schema.json` (non-normative until B12): MPEG-7 camera-motion
  verbs as the base enum with an editorial layer on top, a shot-size CV with
  IPTC Scene-code mapping, composition, exposure/color, focus, continuity,
  take, audio usability, energy curve, clearance, embedding references; Tier
  0/1 names mirror IPTC Video Metadata Hub where a slot exists.
- **Companions (B18).** `openpicture companion clip.opi --kind iconik|flat`
  writes a same-basename `.json` beside the `.opi` in iconik's documented
  sidecar shape or a flat one-level shape — the lossy projection a MAM will
  actually pair, since none ingests an unknown extension.

All notable changes to the `openpicture` reference implementation. The
**format** version (`"opi": N` in the manifest) is tracked separately in
`SPEC.md` §15; this file is about the software.

## 0.0.1 — 2026-08-29

First working implementation of `.opi` format version 0.

- `openpicture.jcs` — RFC 8785 canonicalization, standard library only,
  tested against the RFC's Appendix B number vectors and UTF-16 key order.
- `openpicture.ed25519` — RFC 8032 Ed25519 (pure Python reference
  algorithm; `cryptography` used automatically when present), tested
  against RFC 8032 §7.1 vectors and OpenSSL 3 interop.
- `openpicture.container` — Core (JSON) and Full (ZIP) profiles, byte-level
  profile detection, 64-byte-aligned `.bin` members via a local-header
  extra field (id `0x4F50`), atomic writes, reproducible archives.
- `openpicture.sign` — per-run Ed25519 signatures over
  `{media_binding, run}`; statuses `signed / partial / unsigned / invalid`.
- `openpicture.validate` — structural validator: envelope, binding (on-disk
  sha256 when the media is present), members, alignment, signatures.
- `opi` CLI — `validate`, `inspect`, `pack`, `unpack`, `keygen`, `sign`.
- `tools/opi_verify.py` — the validator as a single copyable file, built by
  `tools/build_bundle.py`; CI fails on drift.
- `SPEC.md` (normative, version 0), `schema/opi-0.schema.json` (JSON Schema
  2020-12 for the envelope), test vectors in SPEC.md Appendix B.
- `examples/` — a real Core and Full file produced from a latent store.

Decisions deferred (marked **[PENDING]** in the spec): always-ZIP vs
dual-profile (B14); key rotation / append-only key log (B15); read-back of
the human layer; the intelligence facet schema.
