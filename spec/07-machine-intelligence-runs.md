## 7. `machine_intelligence` — runs

`machine_intelligence` is an array of **run** objects. A run is one producer
pass over one piece of media: one model, one version, one set of results.
Runs are independent of each other — adding, replacing or removing a run
never affects another run's signature — and each run is signed on its own
(§9.3).

*Rationale.* Intelligence is disposable and improves in passes. A shot
detector runs today; a transcription model runs next week; a better camera
motion classifier runs next year. Each pass is made by different software
with a different confidence profile and, often, a different key. Modelling
the file as a list of self-contained runs lets every pass be verified,
replaced and audited separately, and lets a consumer choose which producers
it trusts.

### 7.1 Run identity

Two runs are **the same run** when they have the same `producer`, the same
`model_version` and describe the same media. `run_id` is *derived* from that
identity, never invented:

```
run_id = lowercase_hex( SHA-256( JCS( {"model_version": <model_version>,
                                       "producer":      <producer>,
                                       "sha256":        <media sha256>} ) ) )[0:32]
```

- `JCS` is RFC 8785 (§9.1). The object has exactly those three keys; the
  canonical form sorts them and fixes the escaping, so every implementation
  hashes the same bytes.
- `<media sha256>` is `media_binding.files[]`'s `original` entry's `sha256`,
  lowercase (§6). A run therefore belongs to the *bytes* of the media, not to
  a path or an application-internal asset id.
- The result is truncated to **exactly 32 hexadecimal characters** (the first
  128 bits). No other length is a valid `run_id`.

Requirements:

- `run_id` is REQUIRED on every run and MUST equal the derivation above when
  the manifest carries an original `sha256`. A validator MUST recompute it and
  fail a run whose `run_id` differs.
- Two runs in one manifest MUST NOT share a `run_id`. (Because the id is
  derived, this is the same rule as: one run per `(producer, model_version)`.)
- A `run_id` MUST NOT change when a run is re-executed with the same identity
  (§7.4). It MUST change when either `producer` or `model_version` changes,
  which the derivation guarantees.

*Rationale.* A derived id makes "is this the same work?" answerable by
anyone holding the file, lets a reindex replace a run without a lookup
table, and removes the temptation to mint ids that mean something only to
one application.

### 7.2 Run fields

| Key | Type | Required | Meaning |
|---|---|---|---|
| `run_id` | string | **REQUIRED** | §7.1. 32 lowercase hex characters. |
| `producer` | string | **REQUIRED** | Who ran: `<tool>:<pass>[:<qualifier>…]`, e.g. `shots:scenedetect`, `asr:whisper`, `facet:camera_motion`. Lowercase ASCII letters, digits, `.`, `_`, `-`; segments separated by `:`; at least two segments; each segment 1–64 characters and starting with a letter or digit. Pattern: `^[a-z0-9][a-z0-9._-]{0,63}(:[a-z0-9][a-z0-9._-]{0,63})+$`. |
| `model_version` | string | **REQUIRED** | Opaque, 1–128 characters, names *exactly* what ran (weights, prompt version, tuning). Two runs whose outputs could differ MUST NOT share a `model_version`. |
| `facets` | object | **REQUIRED** | The intelligence, keyed by facet name (§7.5). MAY be empty. |
| `generator` | string | optional | The software that hosted the producer, e.g. `latent 0.0.45`. |
| `generated_at` | string | RECOMMENDED | When the run finished, RFC 3339 date-time. Writers SHOULD use UTC with a `Z` suffix. |
| `host` | object | optional | The **class** of machine the run executed on: `os` (`macos`, `linux`, `windows`, `other`), `arch` (`arm64`, `x86_64`, `other`), and optional `accelerator` (`cpu`, `cuda`, `metal`, `rocm`, `other`). All three are short lowercase tokens from those sets. MUST NOT carry a hostname, user name, IP or MAC address, serial number, or any other identifier of a particular machine or person (§13). |
| `models` | array of object | optional | The model artefacts this run consumed, each `{"name": …, "sha256": …}`: `name` 1–256 characters naming the weights file or checkpoint, `sha256` its 64-lowercase-hex digest. Names a *file*, not a story — prose about what ran belongs in `model_version`. |
| `supersedes` | string | optional | `run_id` of an earlier run by the same `producer` that this run replaces (§7.4). MUST NOT name the run itself. MAY name a run no longer present in the manifest. |
| `depends_on` | array of string | optional | `run_id`s of runs whose output this run consumed (a facet computed over another run's shots, embeddings taken at another run's boundaries). Every entry MUST be present in the manifest. |
| `egress` | string | optional | What left the producer's premises to make this run: `none` (fully local), `derived` (text, numbers, embeddings), `frames` (stills of the picture), `full_media` (the media itself). A consumer uses this to know what a run cost in exposure. |
| `confidence_scale` | string | optional | `unit` (default): confidences are floats in `[0, 1]`. `bp`: confidences are integers in `[0, 10000]` (basis points). Applies to every entry in the run. |
| `attachments` | object | optional | §7.6. Full profile only. |
| `signature` | object | optional | §9.3. |

Any other key MAY be present and MUST be preserved and ignored by readers.
`parent`, used by pre-release writers, is not defined; a reader MAY treat it
as `supersedes`.

*On `host` and `models`.* Both are evidence about a run, not part of its
identity: neither enters the §7.1 derivation, so adding either to a run
changes neither its `run_id` nor any other run. Both fall under the run
signature — §9.3 covers every key of the run object except `signature` — so
a producer that emits them attests to them. Neither is required, and a
reader MUST NOT treat absence as a defect; most producers will not know
their model hashes. They exist so that "what ran, on what" stays answerable
from the file alone years later, which `generator` and `model_version` only
approximate.

`host` is deliberately a class and never an instance. A sidecar travels, and
a hostname or user name inside a signed run cannot be edited out again
without breaking the signature that makes the run worth having (§13).

*Rationale for the two lineage relations.* "Replaces" and "was computed
from" are different facts. A run that replaces another makes the old one
non-current (§7.3); a run that depends on another is invalidated in spirit,
not in signature, when its input is replaced — a consumer may want to know
that. Folding both into one `parent` key made neither answerable.

### 7.3 Which run is current

A manifest MAY carry several runs by the same `producer` (an old and a new
`model_version`, kept for comparison). A reader that wants *one* answer per
producer MUST select it as follows:

1. Discard every run named by another run's `supersedes`.
2. Of the remaining runs sharing a `producer`, take the one with the latest
   `generated_at`.
3. If none carries `generated_at`, or several tie, take the one that appears
   last in the array.

Readers MUST NOT depend on array order for anything else.

### 7.4 Re-running

**Same identity → replace in place.** Running the same `producer` at the same
`model_version` on the same media again yields the same `run_id`. A writer
MUST replace the existing run object (new `facets`, new `generated_at`, new
`signature`) rather than append a second one. Other runs and their signatures
are untouched.

**New `model_version` → a new run.** A writer MUST append a new run with the
new `run_id` and SHOULD set `supersedes` to the run it replaces. The writer
MAY retain the superseded run (so a reader can diff the two) or MAY drop it;
either is conformant.

**Removing a run** never invalidates any other run. Signatures cover one run
and the media binding, nothing else (§9.3).

*Rationale.* A store that re-indexes owes the file a fresh run, not a
growing pile of stale ones; but a producer that keeps history wants to show
what changed. The rule allows both while keeping "current" unambiguous.

### 7.5 Facets

`facets` maps a **facet name** to an **array of entries**.

**Names.** Lowercase, dotted: `shots`, `transcript`, `camera_motion`,
`clearance.faces`. Pattern: `^(x-[a-z0-9]+\.)?[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$` — the vendor
segment is lowercase alphanumeric (`openpicture.runs.FACET_NAME_RE`).
Names without a prefix are reserved for this specification's vocabulary
(Appendix C); anything else MUST be namespaced `x-<vendor>.<name>`, e.g.
`x-acme.color_match`. A validator MUST NOT reject a facet name it does not
recognise; it MUST reject one that does not match the pattern.

**Entries.** Each entry is an object and:

- MUST carry a `confidence` key. Its value is a number in the run's
  `confidence_scale`, or `null` when no confidence was estimated — `null`
  is honest; omitting the key is not. Booleans are never confidences.

  `null` covers two cases, and a reader cannot tell them apart from the
  key alone. One: the producer made an inference but did not estimate how
  sure it is. Two: the value was **measured** by deterministic arithmetic
  over the pixels or samples — exposure statistics, an energy series,
  audio levels — so there is nothing to be unsure about. A measured entry
  SHOULD instead carry `coverage`, a number in [0, 1] saying how much of
  the span the numbers were actually computed from. Which facets are
  measured rather than inferred is vocabulary, so it is Appendix C's to
  say (C.0.1), not this chapter's.
- MAY carry `span` (§6A — the time model). An entry without a `span`
  describes the whole media.
- MAY carry `id`, a string unique within the run, so another run's
  `depends_on` results or a human annotation can point at it.
- MAY carry `evidence`, an object the producer uses to say *why* (a frame,
  a transcript line, a score breakdown). Unconstrained.
- MAY carry any other key; the per-facet vocabulary (Appendix C) says what
  they mean. Appendix C is normative for the facets B12 froze and a set of
  proposals for the rest; C.0.0 says which are which.

A validator MUST check the name pattern, the array shape and the
`confidence` rule. It MUST NOT check per-facet keys in version 0.

*Rationale.* Two things make the layer trustworthy to an editor: every
claim says how sure it is, and every claim can say why. Requiring the first
and making room for the second is the whole of the facet contract; the
vocabulary can evolve underneath it.

### 7.6 Attachments

`attachments` maps a member name (a path inside the Full container, §4)
to an attachment object. **§7b.2 defines that object** — `sha256`, `size`
and `media_type`, all three REQUIRED, plus the per-kind keys of §7b.3–§7b.5.
What this chapter adds is the ownership rule:

- A member MUST be declared by **exactly one** run — the run that produced
  it. Two runs MUST NOT declare the same member name, even with identical
  hashes; a validator MUST fail the second declaration
  (`attachments.single-owner`, §7b.6).
- The declaring run's signature therefore covers the member's content by
  hash (§9.3); the container's own directory is never signed.
- A Core-profile manifest MUST NOT declare attachments.
- Member names follow §4 (relative, no `..`, filesystem-safe characters).

*Rationale.* Ownership answers "who is responsible for these bytes" and
"whose signature covers them" with one rule. Allowing shared declarations
would make both answers ambiguous for no gain — a run that needs another
run's member names it in `depends_on`.

### 7.7 Ordering

A writer MUST order runs by `(producer, model_version)`, bytewise, so that
identical inputs produce identical manifests (§11). A reader MUST NOT infer
anything from order except the §7.3 tie-break.

### 7.8 Conformance summary

| Requirement | Level |
|---|---|
| `run_id`, `producer`, `model_version`, `facets` present | MUST |
| `run_id` equals the §7.1 derivation when the media sha256 is known | MUST |
| `run_id` unique within the manifest | MUST |
| `producer` matches the pattern; `model_version` 1–128 chars | MUST |
| `generated_at` RFC 3339 when present | MUST |
| `supersedes` never names the run itself; `depends_on` entries present | MUST |
| `egress` and `confidence_scale` from their enumerations | MUST |
| `host`, when present, an object whose `os`/`arch`/`accelerator` come from their enumerations and name no instance | MUST |
| `models`, when present, an array of `{name, sha256}` with 64-lowercase-hex digests | MUST |
| facet names match the pattern; entries are objects with a valid `confidence` | MUST |
| a member declared by no more than one run (§7.6, `attachments.single-owner`); §7b.6 requires no fewer | MUST |
| runs ordered by `(producer, model_version)` | MUST (writer) |
| same identity replaces in place; new `model_version` appends | MUST (writer) |
| `supersedes` set on the replacing run | SHOULD |
| `generated_at` present | SHOULD |
| `host` and `models` present when the producer can determine them | SHOULD |

Reference implementation: `openpicture/runs.py` (`run_id`, `new_run`,
`current_runs`, `lineage`, `checks`). Test vectors: `vectors/runs/`.
