# Reading a `.opi` into a store

A store — a search index, a MAM's database, an archive catalog — is a
**derived index**. The media and the `.opi` beside each clip are the source
of truth; the store is something a program builds from the folder and can
build again. That sentence is the whole design: a folder that moves takes
its intelligence with it, and nothing lives only in a database.

The format makes that sentence testable, and this page is the contract a
consumer signs when it makes it true for its own store.

## The promise, stated as a test

    A = a store that registered the folder, ran its producers, exported
        a sidecar beside every clip
    B = an empty store that registered the same folder, sidecars present

Then: `shots(B) == shots(A)`, `signals(B) == signals(A)`, the same search
query returns the same assets in the same order, the human layer matches,
`export(B) == export(A)`, and the producers that ran in A have nothing to
do in B. A store deleted by accident and rebuilt from the folder alone is
the store you had.

What a rebuild **cannot** reproduce is part of the promise, because each
difference is a fact about the store, not about the footage:

| Differs after a rebuild | Why it must |
|---|---|
| `generated_at`, `signed_at`, `signature` on the document | written at another moment by another key. Per-*run* `generated_at` does survive (§7) — it is the run's own time |
| asset ids, row ids, `created_at`, ingest records | the store's bookkeeping. §6.2 makes the checksum the binding; a store never adopts a foreign primary key |
| a label's `id` | §8.2: opaque, scoped to the writer that emitted it. The round trip still converges — an unrecognised `id` imports as §8.4's third case, deduplicated on `(name, value, span)` |
| a label's `created_by` | names where *this* record came from. The human's own claim travels in `by`, which is exactly what §8.2 added it for |
| embedding vectors, to F16 and L2 | §7b.3 travels vectors normalised and half-precision; magnitude and float32 precision are not in the file |

## The rules that make it hold

1. **Pair by name, confirm by checksum.** The two-dot name pairs a sidecar
   to its media; the `media_binding` `sha256` must match the bytes you
   hold (§12). Record the hash once, at registration, and compare against
   that.
2. **A `mismatch` is a different file, not a bad one.** A sidecar whose
   checksum contradicts the bytes beside it describes another recording.
   Skip it and say so; never load it.
3. **Signatures are per run.** A run whose signature does not verify is
   refused; the runs beside it, which verify, still load — one edited run
   need not destroy four honest ones. Refuse-and-report the file whole
   only when it cannot be opened, binds bytes you do not have, or carries
   an `opi` major you do not implement. Either way the status you record
   is per run and never collapsed (§12).
4. **Unsigned loads, flagged.** A run with no signature is not evidence of
   tampering; it is evidence of a writer that did not sign. Record its
   status as what it is — `valid`, `unsigned`, `invalid` — per run, and
   never collapse them (§12).
5. **Record where each row came from.** The minimum provenance for an
   imported row: the file it came out of (`source`), the signer URN,
   the signature status, and the run's own `generated_at` (§7). "Did we
   measure this, or did it arrive?" is the first question asked of every
   imported judgment.
6. **Never re-badge attribution.** Rows land with the original `producer`
   and `model_version`. Laundering a foreign producer's judgment into a
   local one makes the archive's history unreadable.
7. **Bind by checksum, never by the file's asset ids.** `asset_id` is the
   writer's primary key and means nothing outside its store (§6.2); a
   file naming your asset by coincidence of id is still a coincidence.

**Satisfied is a property of the triple.** A producer is satisfied by an
existing run of the same `(producer, model_version)` — valid-signed, or
unsigned and flagged. A newer `model_version` is new work by definition;
an older run in a file does not satisfy it.

## When a file and the store disagree

Same `(producer, model_version)`, different content. The specification does
not mandate how a store resolves this — that a store resolves it is the
consumer's own doctrine, not a format rule. The ladder below is what the
reference consumer implements and what we recommend:

1. a valid signature beats an unsigned run;
2. same — trust tier: your own key, then keys you have vouched for, then
   keys nobody has vouched for;
3. same — the newer `generated_at` wins (compare instants, not strings:
   RFC 3339 spells one moment several ways);
4. dead tie — the store keeps what it holds, and says so.

The loser is never kept as a parallel run. It is one supersession record
in an audit log — run id, signer, reason — so "did we ever see a different
answer" stays answerable while search and exports see one truth. A
producer that regresses at the same `model_version` is a producer bug; the
fix is a new `model_version`.

## Reading the human layer back

`editorial_annotations` is mutable and unsigned, and a store MAY read it
back. If it does, §8.4 binds it:

| In the file | In the store | Import as |
|---|---|---|
| `id`, value unchanged | same `id` | nothing |
| `id`, value changed | same `id` | a new value that **supersedes** it |
| no `id` (or a foreign one) | — | a new label, deduplicated on `(name, value, span)` |
| an `id` you wrote | **absent** | a retraction |

Two rules do the protecting. **Never destroy**: a value that conflicts
with one in the store is kept alongside it, both timestamped — the store
never decides which human was right. **Never derive**: a label's `by` is
self-declared and covered by no signature; a reader MUST NOT fill it from
a run's signer or treat a signed file's labels as attributable (§8.2, §13).

Two refinements keep round trips converging rather than accumulating.
Match a file's `id` against the *chain head* of the label it names, not
against live ids — a file written two corrections ago still names the
label it named. And treat retraction as an **absence**, never as a
`value: null`: an `id` you exported and the file no longer carries means
"withdrawn" — but only for a file your store wrote. A file from somewhere
else carries none of your ids, so the rule must not reach it.

## The toolkit

- [`openpicture.discover`](../reference/python-api.md) — pairing and the
  per-pair states (`paired`, `mismatch`, `orphan`, `tampered`, …) that
  [doctor](../reference/cli.md#openpicture-doctor) reports.
- `openpicture.load` / the reader — per-run signature status and verified
  access to facets.
- `tools/opi_verify.py` — the single-file validator; gate a file through
  it before ingesting if your store does not verify signatures itself.
- The conformance suite (`tools/conformance/run.py`) — the executable
  half of the specification (§16.5); a store's ingest gate can prove
  itself against the same vectors a validator must.

This page describes a pattern with a working implementation: latent's
`register` pass pairs, verifies and rebuilds a store under exactly these
rules, and its rebuild test is the worked example behind the table above.
