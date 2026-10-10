# Runs and signatures

## The machine layer is a list of runs

`machine_intelligence` is an array. Each element is a **run**: one pass of
one producer with one model version over this clip.

```json
{
  "run_id": "d23f5d13c94f0918ab672cda134e80f5",
  "producer": "shots:scenedetect",
  "model_version": "scenedetect-0.7",
  "generator": "latent 0.0.45",
  "facets": {"shots": [ … ], "signals": [ … ]},
  "attachments": {"embeddings/example-hash.safetensors": {"sha256": "…", "size": 272,
                                                          "media_type": "application/x-safetensors"}},
  "signature": { … }
}
```

The producer and model are named once, on the run, never repeated per
facet entry. `run_id` is not invented but derived: the SHA-256 of the RFC
8785 canonical form of `{producer, model_version, sha256}`, truncated to
32 hex characters. The same work on the same media yields the same id, a
signature made today still describes a file rebuilt tomorrow, and a
validator recomputes the id and fails a run that disagrees. Runs are
sorted by `(producer, model_version)`. Lineage is explicit: a re-run sets
`supersedes` to the id of the run it replaces, and `depends_on` names runs
whose output this one consumed.

Why runs and not one big block: a model pass is the unit that gets
re-done. Re-running one producer replaces one run and leaves every other
run — and every other run's signature — untouched. Signals are disposable;
the run is what gets disposed of.

## Each run is signed on its own

A run's `signature` is an Ed25519 signature (RFC 8032) over the **RFC 8785
canonical form** of exactly this object:

```json
{"media_binding": <manifest.media_binding>, "run": <the run without its "signature" key>}
```

Including `media_binding` means every run signature also asserts *which
media* the intelligence describes. Excluding other runs means appending a
second producer's work never voids the first. Excluding the envelope and
the human layer means editors can edit without "corrupting" anything.

The signature entry:

| Key | Value |
|---|---|
| `algorithm` | `"Ed25519"` |
| `signer` | A stable identifier for the producer — a URN |
| `public_key` | The raw 32-byte public key, 64 hex characters. **This is the key id.** |
| `signed_at` | RFC 3339 timestamp, informative |
| `signature` | Base64 of the raw 64-byte signature |
| `role` | Informative; default `machine_producer` |

Raw RFC 8032 keys — no PEM, no X.509, no certificate authority. A solo
producer can sign with a key it generated this morning.

!!! warning "`json.dumps(sort_keys=True)` is not RFC 8785"
    Python's default serializer sorts keys by code point where JCS sorts by
    UTF-16 code unit, and formats `1e+16` where JCS writes
    `10000000000000000`. Use a real canonicalizer. The reference
    implementation's `openpicture/jcs.py` is one, tested against the RFC's
    own vectors; JCS libraries exist for JavaScript, Go, Rust and Java.

## What a verifier reports

Per run: `valid`, `invalid` (with a reason), or `unsigned`. Then for the
file:

| Status | Meaning |
|---|---|
| `signed` | every run valid |
| `partial` | some runs valid, none invalid, some unsigned |
| `unsigned` | no signatures at all |
| `invalid` | any run failed to verify |

A verifier must say **which run** and never collapse `partial` into
`signed`. And **unsigned is valid**: a file with no signatures is honest; a
file with a bad one is not. This matters for adoption — a producer with no
key yet can still write conformant files.

```text
valid-signed   clip.mov.opi  (profile=core, opi=0, signatures=signed)
  ok   run[0] valid: shots:scenedetect by urn:openpicture:example:producer
  ok   run[1] valid: facet:camera_motion by urn:openpicture:example:producer
```

## Keys: an append-only log

A producer publishes every public key it has ever signed with — signer,
date added, a note — and **never withdraws one**. A retired or compromised
key is *marked*, not removed, so every file it legitimately signed stays
verifiable forever; compromise is handled by marking and re-signing, never
by deleting history.

A verifier holding a producer's log adds a second axis to each run:
`trusted` (key in the log) or `unknown-signer` (not). A valid signature by
an unknown key is still a valid signature — the log answers *whose*, not
*whether*.

```bash
openpicture keys add producer-keys.jsonl --key producer.key --signer urn:example:producer
openpicture validate clip.mov.opi --keylog producer-keys.jsonl
```

## What a signature does and does not mean

A valid signature means: *this key signed these facets about this media*.
It says nothing about whether the model was right. Truth is what
`confidence` and the producer's published evaluation are for; the
signature is about origin and integrity.

*Normative text: specification §7 and §9.*
