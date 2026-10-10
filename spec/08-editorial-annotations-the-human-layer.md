## 8. `editorial_annotations` — the human layer

A JSON object. **Never signed.** It belongs to whoever holds the file — an
editor, a MAM, the client. Readers MUST NOT treat a change here as
tampering, and a run signature MUST NOT be computed over any part of it
(§9.2).

Table conventions are §5's. Nothing in this chapter is under a signature.

### 8.1 Keys

| Key | Type | Req. | Values / constraints | Writer | Check |
|---|---|---|---|---|---|
| `labels` | array | MAY | §8.2. **Reserved:** owned by the producer that maintains the labels (the reference producer writes its live labels here and carries nothing else forward from its own store). Absent ≡ empty. | producer | `editorial_annotations`, schema |
| `notes` | string | MAY | Free text about the medium as a whole, from whoever holds the file. 1–4096 characters. Not a vocabulary term, never machine-read: a validator checks its type and nothing else. | human | schema |
| *any other key* | any JSON | MAY | The holder's. A rating, notes, tags, a MAM's field map, a colourist's LUT name — anything. Writers regenerating the file MUST carry these forward verbatim (§8.3). | human | — |

The object as a whole MUST be an object; an array or scalar is invalid
(`editorial_annotations`). An empty object is the normal state of a freshly
produced file.

Keys beginning with `opi.` are reserved for future versions of this
specification and MUST NOT be used by holders.

### 8.2 `labels[]` entries

A label is one human judgement about the medium or a span of it.

| Key | Type | Req. | Values / constraints | Default |
|---|---|---|---|---|
| `name` | string | MUST | The vocabulary term: `"select"`, `"scene"`, `"take"`, `"note"`. 1–128 characters. Vocabularies are the holder's — this document defines none. | — |
| `value` | string \| number \| boolean \| `null` | MUST | The judgement. `null` means the label is a **bare tag** — a `select` with nothing further said. It is not a retraction; §8.4 retracts by absence. | — |
| `created_by` | string | MUST | Who made it — a person, a tool, or a read-back provenance such as `"opi:<signer>"` (§8.4). 1–256 characters. | — |
| `created_at` | string | SHOULD | RFC 3339 `date-time`. | — |
| `by` | string | MAY | The human who made the judgement, **self-declared**: an opaque account identifier or a chosen handle, 1–256 characters. Distinct from `created_by`, which says where the *record* came from — `by` says who formed the opinion. Never a proof (§8.4, §13). | — |
| `at` | string | MAY | RFC 3339 `date-time`: when the human made the judgement, which MAY predate `created_at` (when the record was written). | — |
| `notes` | string | MAY | Free text about this label. 1–4096 characters. | — |
| `span` | object | MAY | §6A.3. The part of the medium the label applies to. Absent means the whole medium. | whole medium |
| `id` | string | MAY | Stable identifier for this label, 1–128 characters. A writer that emits `id` MUST keep it the same across rewrites for as long as the label is the same label, so that a later import recognises it (§8.4). Opaque — readers MUST NOT parse it, and MUST NOT assume it means anything outside the file that carries it. | — |

Any other key MAY be present and MUST be preserved. Two labels with the same
`name` and `value` over the same `span` are one label; writers SHOULD not
duplicate them, readers MUST tolerate duplicates.

**Identity here is a claim, not a proof.** `by` is written by whoever holds
the file, is covered by no signature, and can be changed by anyone who can
write the file. A reader MUST NOT derive `by` from a run's signer, and MUST
NOT present a label as attributable because the file's runs are signed — the
human layer sits outside every signature by construction (§9.2). Writers
SHOULD fill `by` from an opaque account identifier rather than a legal name,
and MUST NOT fill it from an operating-system user name or an email address
(§13). `openpicture annotate --anonymous` strips `by` and `at` from every
label before a file travels; it does not strip `created_by`, which is record
provenance rather than personal identity and which §8.2 requires.

A tool recording an imported or machine-produced judgement fills `created_by`
(where the record came from) and MUST NOT fill `by`: a machine, a run or a
signature is not a person. On read-back it therefore MUST NOT copy a run's
`signature.signer` into `by`, and MUST NOT otherwise turn a machine signer
into a human attribution (F5, §8.4).

### 8.3 Preservation on rewrite

A writer regenerating a sidecar that already exists at the target MUST read
the existing `editorial_annotations` first and carry forward every key it
does not own, verbatim — including keys it does not understand. The
reference writer owns `labels` only. Without this rule every regeneration
silently destroys the editor's work, which is the failure the human layer
exists to prevent.

A writer MUST NOT reorder, reformat or "clean up" carried-forward values.

A producer that reads the block back into its own store owns `labels` only. It
MUST NOT project any other clause into the store as a label: in particular it
MUST NOT rewrite a non-`labels` key as an `opi.<key>` label, nor write such a
key twice (once as itself and once as a label). Every other clause belongs to
the holder — carry it forward verbatim (§8.4 is about `labels` alone). This is
F4: the human layer's non-label keys are data, not a vocabulary to absorb.

### 8.4 Read-back

Decided 2026-08-29 (B23), refined the same day with the `id` matching rule
below. A producer that maintains its own store MAY read
`editorial_annotations` back. If it does, it MUST:

- record each imported value with provenance naming the file or the signer
  (the reference producer uses `created_by = "opi:<signer|filename>"`);
- never destroy what it already holds: a value that conflicts with one in
  the store is retained **alongside** it, both timestamped. A store MAY
  decide which of the two is *live*; it MUST keep the other;
- never derive a label's `by` from a run signature, and never present an
  imported label as attributable (§8.2);
- never import anything from `machine_intelligence` — the machine layer is
  regenerated by re-running producers, not copied.

**Matching on `id`.** A producer that wrote `id` on the labels it emitted
MAY use it to converge on read-back rather than accumulate duplicates. If it
does, these are the four cases:

| In the file | In the store | Import as |
|---|---|---|
| `id` present, value unchanged | same `id` | nothing |
| `id` present, value changed | same `id` | a new label that supersedes the store's; the store's becomes non-live |
| `id` absent | — | a new label, deduplicated on `(name, value, span)` |
| an `id` this producer wrote | **absent from the file** | a **retraction**: the store's label becomes non-live |

Retraction is by **absence**. It is deliberately not `value: null`, because
`null` already means a bare tag (§8.2) and a file full of bare tags must not
read as a file full of retractions. A store records a retraction as a
superseding event carrying no value, so "was this ever asserted" stays
answerable; the next file that producer writes carries only live labels, so
the file shows one value per `id` while the store keeps the history.

Two files that disagree are imported in arrival order: the last read is
live, and both are in the store's history.

None of this is required *of a file*. It is what a producer that keeps a
store owes its own users, and it is the reason `id` is worth writing at all.

The file itself guarantees only that a rewrite will not lose the human
layer (§8.3); read-back is the producer's contract with its own store.

### 8.5 Size

`editorial_annotations` counts toward the manifest cap (§5.6). It SHOULD
stay under 1 MiB. It is a place for judgements, not for bulk data: a holder
who wants to store a transcript edit or a large structured document beside
the medium SHOULD use an `extensions/` member (§7b) and reference it from
here by name.

### 8.6 Validation

A validator MUST fail a manifest whose `editorial_annotations` is present
and not an object. It MUST NOT fail a manifest for any content of that
object other than a malformed `labels` array (schema: entries lacking
`name`, `value` or `created_by`). The optional keys of §8.2 — `id`, `by`,
`at`, `notes` — are checked for type and length when present and never for
presence: a validator MUST NOT fail a label for lacking them, and MUST NOT
fail one because it does not recognise a `by`, there being no registry of
people. It MUST NOT compare the human layer to anything signed. `openpicture annotate` is the reference tool for editing
this block; it refuses to write if anything outside `editorial_annotations`
would change.
