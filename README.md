# Open Picture Intelligence — `.opi`

**An open, signed sidecar file that carries what a machine knows about a
piece of footage, beside the footage, owned by whoever owns the footage.**

[Documentation](https://openpictureintelligence.github.io/opi/) ·
[Specification](SPEC.md) ·
[JSON Schema](schema/) ·
[Changelog](CHANGELOG.md) ·
Apache-2.0

---

## The idea

A camera writes the first layer of metadata: codec, frame rate, timecode,
lens. A machine can write a second layer: where the shots are, what was said,
how the camera moved, what a shot could cut to, whether it is usable — and
how confident it is about each claim.

Today that second layer lives inside whatever application produced it, in a
database you do not control, or in a cloud you had to upload the footage to.
`.opi` puts it in a file next to the clip:

```
A001_C001.mov          the footage — never modified
A001_C001.mov.opi      everything a machine knows about it
```

Three properties make it a format rather than an export:

| | |
|---|---|
| **Open** | A ZIP with a JSON manifest. `unzip -p clip.mov.opi manifest.json` and you have everything. Readers ignore what they do not understand. |
| **Signed** | Every producer run inside is signed (Ed25519 over RFC 8785 canonical JSON). A verifier says *which* run by *whom* checks out. Nothing is encrypted. |
| **Bound** | To the media by SHA-256, not by filename. Rename it, move it, archive it — the sidecar still knows which bytes it describes. |

And one rule that makes it usable by people: the **human layer** —
`editorial_annotations` — is never signed. An editor's rating, a MAM's tags, a
scene number: anyone can change them, nothing "breaks", and a producer that
regenerates the file preserves them.

## What is in the file

```
manifest.json
├── opi: 0                        format major version
├── media_binding                 files (sha256, size, name), rational timecode, provenance
├── machine_intelligence[]        one entry per producer run, each self-signed
│   ├── run_id, producer, model_version
│   ├── facets{ shots, transcript, camera_motion, … }
│   ├── attachments{ member → sha256,size }   binary members this run owns
│   └── signature{ signer, public_key, signature }
└── editorial_annotations         the human layer — unsigned, yours
embeddings/<model>.safetensors    optional, stored uncompressed, 64-byte aligned (mmap it)
keyframes/*.webp                  optional proof stills
extensions/<reverse.dns>/         optional vendor blocks
```

A file with only `manifest.json` is the **Core** profile; with members it is
**Full**. Same extension, same manifest, detected from the bytes.

## Quick start

```bash
git clone https://github.com/openpictureintelligence/opi && cd opi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"          # no runtime dependencies
python -m pytest -q

openpicture validate examples/A001_C001.mov.opi          # valid-signed
openpicture inspect  examples/A001_C001.mov.full.opi     # members, offsets, manifest
unzip -p             examples/A001_C001.mov.full.opi manifest.json | head
```

Make one, sign it, check it:

```bash
openpicture keygen producer.key
openpicture pack   manifest.json clip.mov.opi --member embeddings/x.safetensors=x.safetensors
openpicture sign   clip.mov.opi --key producer.key --signer urn:example:producer
openpicture validate clip.mov.opi
```

Read one from Python:

```python
import openpicture

sc = openpicture.load("clip.mov.opi")
sc.sha256                       # the media it describes
sc.signature_status             # signed | partial | unsigned | invalid
for run in sc.runs:
    print(run.producer, run.model_version, run.status, run.signer)
sc.trusted_facets("shots")      # only from runs whose signature verified
view = sc.map_member("embeddings/x.safetensors")   # zero-copy memoryview
```

## The toolkit

| Command | |
|---|---|
| `openpicture validate` | Structural + signature validation; `--keylog` adds trust; exit 0/1 |
| `openpicture inspect` | Manifest and members with data offsets |
| `openpicture doctor DIR` | Pair media with sidecars across a tree; report missing/orphan/mismatch/tampered; re-pair by hash |
| `openpicture keygen` / `sign` | Ed25519 keys; sign every unsigned run |
| `openpicture keys` | Append-only key log — the trust anchor |
| `openpicture annotate` | Edit the human layer safely; refuses to touch anything signed |
| `openpicture diff` | Two sidecars, what changed — intelligence is diffable |
| `openpicture pack` / `unpack` | Members in, members out |
| `openpicture companion` | Flat or iconik-shaped JSON beside the `.opi` for MAM pairing |
| `tools/opi_verify.py` | The validator as **one file**, standard library only. Copy it anywhere. |

Everything in `openpicture/` is standard-library Python. `cryptography` is
used as a fast path when present and never required.

## For producers and consumers

- **Writing `.opi` files** — create runs, attach members, sign with your key.
  The reference producer is Latent (Lunar Park's footage-intelligence
  pipeline; not yet public), which writes a sidecar for every clip it
  indexes. See *Ecosystem → Producers* in the docs.
- **Reading them** — any language with a ZIP reader and a JSON parser gets
  the manifest; verifying needs an Ed25519 implementation and an RFC 8785
  canonicalizer (both widely available). The single-file validator is the
  reference behaviour.
- **MAMs** — no asset manager auto-ingests an unknown extension. Emit a
  companion JSON (`openpicture companion`) in the MAM's own shape beside the
  authoritative `.opi`.

## Status

Format major version **0 — pre-freeze.** The container, envelope, binding,
run structure and signing are stable enough to build against. Seven
facets are frozen (SPEC Appendix C, `schema/facets-0.schema.json`); the
rest of the vocabulary is proposals. This is a **public alpha**, open to
feedback and integrations. Package versions remain `0.0.x` during this
pre-freeze stage; public availability does not freeze the format.

`openpicture` is not on PyPI yet. Install from this repository; consumers
should pin a validated commit rather than a moving branch.

Registrations (IANA media types, macOS UTI) are drafted and wait on the
schema freeze. See [`docs/status.md`](docs/status.md).

## Repository

```
SPEC.md              the normative specification
schema/              JSON Schema 2020-12 — envelope and proposed facets
openpicture/         reference implementation (stdlib only)
tools/opi_verify.py  single-file validator, generated from the package
examples/            real files from the reference producer, sanitized and signed
docs/                the documentation site (MkDocs)
tests/               400+ tests incl. RFC 8785 / RFC 8032 vectors
```

Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md) ·
Security: [`SECURITY.md`](SECURITY.md) ·
Governance: [`docs/contribute/governance.md`](docs/contribute/governance.md)

Stewarded by Lunar Park. Licensed under the Apache License 2.0.
