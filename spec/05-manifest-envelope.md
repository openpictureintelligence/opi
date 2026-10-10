## 5. Manifest envelope

The manifest is one JSON object (RFC 8259) stored as `manifest.json`
(§3, §4). This chapter defines every key of that object except the contents
of the three blocks it carries, which have their own chapters: `media_binding`
(§6), `machine_intelligence` (§7) and `editorial_annotations` (§8).

Conventions used by the key tables in §5, §6 and §8:

- **Req.** — `MUST` (required), `MUST-if` (conditional, condition stated),
  `SHOULD` (recommended), `MAY` (optional). A key marked `MAY` with a
  **default** is read as that default when absent.
- **Signed** — whether the key's value is covered by a run signature (§9.2).
  `runs` means every run signature covers it; `no` means it is informative
  and may change without touching any signature.
- **Writer** — who legitimately writes the key: `producer` (the software
  that generated a run), `human` (an editor, a MAM, the holder), `any`.
- **Check** — the reference validator row that enforces the rule
  (`openpicture validate`), or `schema` when the rule is enforced by
  `schema/opi-0.schema.json` and not (yet) by a validator row. A rule with
  neither is a writer requirement (§11) that a reader cannot observe.

### 5.1 Top-level keys

| Key | Type | Req. | Values / constraints | Default | Signed | Writer | Check |
|---|---|---|---|---|---|---|---|
| `opi` | integer | MUST, **first key** | `0` for files conforming to this document. `≥ 0`. Booleans are not integers. | — | no (§5.4) | producer | `has opi`, `opi version`, `opi is first key` |
| `profile` | string | MUST | `"core"` \| `"full"`. MUST equal the profile §3.3 derives from the members. | — | no | producer | `has profile`, `profile matches contents` |
| `media_binding` | object | MUST | §6. | — | runs | producer | `has media_binding`, §6 rows |
| `machine_intelligence` | array | MAY | Array of run objects (§7). MAY be empty. Absent ≡ empty. | `[]` | each run signs itself | producer | `runs: *` |
| `editorial_annotations` | object | MAY | §8. Absent ≡ `{}`. | `{}` | **never** | human | `editorial_annotations` |
| `generator` | string | SHOULD | Free text naming the writing software and version, e.g. `"latent 0.0.45"` or `"acme-indexer 2.1"`. ≤ 256 characters. | — | no | producer | schema |
| `generated_at` | string | SHOULD | RFC 3339 `date-time`; writers SHOULD use UTC (`Z` or `+00:00`). The moment the manifest was written — not when any run finished (that is `run.generated_at`, §7.2). | — | no | producer | schema |
| `$schema` | string | MAY | A URI. An informative hint for editors and linters; readers MUST NOT fetch it and MUST NOT fail on an unknown value. | — | no | any | schema |

**There is no top-level `signatures` array.** Signatures live on runs
(§7.2, §9.3). A top-level `signatures` key is an unknown key: preserved and
ignored like any other (§5.3). Readers MUST NOT interpret it as a signature.

### 5.2 Key order

`opi` MUST be the first key of the object, so a reader can dispatch on the
version before parsing anything else and a human opening the file sees what
it is on line 2. A validator MUST fail a manifest whose first key is not
`opi`.

The order of every other key is free. Writers SHOULD emit the top-level keys
in the order of the table above and SHOULD preserve the order of keys they
carry forward from an existing file (§8.3). Key order is never significant
to a reader and is not covered by signatures (§9.1 canonicalizes it away).

### 5.3 Version and unknown keys

`opi` is an integer major version. Readers MUST refuse a major they do not
implement. Within a major, readers MUST ignore keys they do not recognise,
at every level of the document, and writers rewriting a file MUST preserve
unknown keys verbatim in the blocks they do not own. Minor evolution is
additive and unversioned; that is what "ignore unknown keys" buys.

Consequently `additionalProperties` is `true` at every level of the envelope
schema. Known keys are typed and constrained; unknown keys are merely
carried.

### 5.4 What the envelope signs

Nothing in §5.1 except `media_binding` is under a signature. `opi`,
`profile`, `generator`, `generated_at` and `$schema` are informative
envelope facts a rewrite may change without invalidating any run. The
consequence a verifier must understand: a signed run proves *what a
producer said about which media*; it does not prove which software
assembled the surrounding file or when. That is by design — the same runs
must survive a regeneration by a different writer (§11).

### 5.5 Serialization

The bytes of `manifest.json` are: UTF-8; the JSON text produced by
`json.dumps(indent=2, ensure_ascii=False, allow_nan=False)` with insertion
key order preserved; followed by exactly one `\n`. Non-ASCII characters are
emitted literally, not escaped. `NaN` and infinities MUST NOT appear. No
byte-order mark.

A validator MUST confirm that a file's `manifest.json` re-serializes to
these exact bytes from its parsed value (`canonical form` row). This is what
makes the Core file and the Full file's manifest one document rather than
two.

### 5.6 Size

`manifest.json` MUST NOT exceed **16 MiB** (16 777 216 bytes) uncompressed.

*Rationale.* A timecoded transcript runs ~150 KB per hour of speech; 16 MiB
holds roughly a hundred hours of dense dialogue plus every other facet, and
a single clip is rarely more than an hour. Anything larger is bulk data —
per-frame series, dense embeddings — and belongs in a member (§7b), where
it is aligned, hashed and never parsed as text. The cap also bounds what a
reader must hold in memory to answer "what is this file about".

A validator MUST NOT parse a `manifest.json` whose uncompressed size exceeds
the cap; it MUST report the file as invalid (`manifest size`) without
loading the JSON. Writers SHOULD keep manifests under 1 MiB and MUST move
any array that would carry more than 65 536 entries into a member.

### 5.7 Numbers

Frame rates are rational `{"num": int, "den": int}` (§6A.1). Positions are
integer frames (§6A.3). Seconds and timecode strings MAY be present as
derived conveniences and MUST agree with the frames when they are. Floats
are permitted where the model calls for them (confidence, seconds,
measurements) and are canonicalized per RFC 8785 when signed; producers
SHOULD prefer integers in signed material so that third-party
canonicalizers stay trivial. Booleans are never accepted where a number is
specified.
