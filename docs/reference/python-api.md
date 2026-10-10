# Python API

The `openpicture` package is standard-library Python 3.11+. Every module
below is importable on its own; the validator modules together are the
[standalone validator](validator.md). Signatures are taken from the code;
docstrings in the source carry the rationale.

## Reading a file — `openpicture.load`

```python
import openpicture

sc = openpicture.load("A001_C001.mov.opi")       # raises ValueError / UnsupportedVersion
sc.profile            # "core" | "full"
sc.version            # 0
sc.signature_status   # "signed" | "partial" | "unsigned" | "invalid"
sc.sha256             # original file's sha256, or None
sc.original           # the files[] entry with role "original"
sc.annotations        # editorial_annotations dict (mutable, unsigned)

for run in sc.runs:                 # openpicture.reader.Run
    run.producer, run.model_version, run.run_id
    run.status                      # "valid" | "invalid" | "unsigned"
    run.verified                    # status == "valid"
    run.facets                      # dict
    run.attachments                 # dict

sc.trusted_facets("shots")          # values from verified runs only
list(sc.facets("camera_motion"))    # (run, value) pairs, all runs
sc.members()                        # member names (Full only)
sc.read_member("keyframes/shot_0000012.webp")
view = sc.map_member("embeddings/siglip.safetensors")   # zero-copy memoryview over mmap
```

`load(path, *, max_version=SPEC_VERSION)` refuses an `opi` major above
`max_version` with `UnsupportedVersion`, per the reader rules.

## Container — `openpicture.container`

```python
from openpicture import container

container.detect(path_or_bytes)         # "zip" | "json" | None
container.profile_of_members(names)     # "core" | "full"
manifest, profile = container.read_manifest(path)
container.write_core(manifest, path)    # ZIP with manifest.json only; atomic
container.write_full(manifest, path, members={"embeddings.bin": data}, aligned=None)
container.write_json(manifest, path)    # the bare internal form (not a deliverable)
container.member_data_offset(path, name)   # byte offset from the local header
container.manifest_bytes(manifest)      # the canonical Core serialization
container.ALIGNMENT, container.ALIGNED_SUFFIXES   # 64, (".bin", ".safetensors")
```

`write_full` STOREs and 64-byte-aligns members whose names end in an aligned
suffix (or those named in `aligned`), DEFLATEs the manifest, fixes
timestamps for reproducibility, and writes atomically.

## Signing — `openpicture.sign`

```python
from openpicture import sign, ed25519

secret = ed25519.generate_secret()                 # 32 bytes
sign.sign_run(manifest, index, secret,
              signer="urn:example:producer",       # keyword-only
              role="machine_producer", signed_at=None)   # -> signature entry, in place
sign.sign_all(manifest, secret, signer="urn:example:producer")   # every unsigned run; returns count
sign.run_payload(manifest, run)                    # the exact bytes that are signed

report = sign.verify_manifest(manifest)            # VerifyReport
report.status                                      # signed | partial | unsigned | invalid
for r in report.runs:                              # RunResult
    r.index, r.run_id, r.producer, r.status, r.signer, r.public_key, r.reason
```

`openpicture.ed25519` exposes `generate_secret`, `public_key(secret)`,
`sign(secret, msg)`, `verify(public, msg, sig)` and `BACKEND` (`"pure-python"`
or `"cryptography"` when that package is importable — results are identical).
`openpicture.jcs.canonicalize(value) -> bytes` is the RFC 8785
canonicalizer.

## Validation — `openpicture.validate`

```python
from openpicture import validate

report = validate.validate(path, media_dir=None)   # media_dir is keyword-only; never raises for a bad file
report.ok                 # every check passed
report.status             # valid-signed | valid-partial | valid-unsigned | invalid
report.profile, report.version, report.signature_status
for check in report.checks:                        # Check(name, ok, detail)
    ...
report.as_dict()
```

## Embeddings — `openpicture.embeddings`

```python
from openpicture import embeddings

data = embeddings.pack_vectors(rows, 768,                    # [count, dim] nested, or flat
    model="siglip-so400m", model_version="1")                # -> `vectors` tensor + opi.* metadata
metadata, tensors = embeddings.unpack(data)     # tensors["vectors"] -> (dtype, shape, memoryview)
embeddings.member_name("siglip-so400m")         # "embeddings/siglip-so400m.safetensors"
embeddings.attachment_entry(data, rows="shots") # {"sha256", "size", "media_type", "dim", "count", …}
embeddings.f32(seq), embeddings.f16(seq), embeddings.i64(seq)
embeddings.DTYPES                               # raw `pack(tensors, metadata)` is there too
```

`pack_vectors` writes the §7b.3 layout: a `vectors` tensor `[count, dim]`
first (optionally a `spans` tensor of millisecond pairs), and the required
`__metadata__` keys `opi.model`, `opi.model_version`, `opi.dim`,
`opi.dtype`, `opi.normalized`, `opi.scope`.

The header is space-padded to a multiple of 64 so the tensor buffer is
64-byte aligned in the file when the member itself is aligned.

## Keyframes — `openpicture.keyframes`

```python
from openpicture import keyframes
keyframes.describe(data)                          # {"media_type", "width", "height"} for WebP/JPEG/PNG
keyframes.member_name("shot", 12)                 # "keyframes/shot_0000012.webp"
keyframes.attachment_entry(data, frame=12, t_s=0.5)
```

## Discovery — `openpicture.discover`

```python
from openpicture import discover
pairings = discover.scan(root, verify_media=False)   # list[Pairing]: state, media, sidecar, detail
discover.summarize(pairings)                          # {state: count}
renames = discover.repair(root, pairings, apply=False)   # re-pair orphans by sha256
discover.MEDIA_EXTENSIONS
```

## Keys — `openpicture.keys`

```python
from openpicture import keys
keys.add(log_path, key, signer, note=None)      # key: public hex or a secret-key file's bytes
entries = keys.load(log_path)                   # list[KeyEntry]
keys.lookup(entries, public_key_hex)
keys.trust_report(manifest, entries)            # per run: trusted | unknown-signer | signer-mismatch | n/a
```

## Human layer — `openpicture.annotate`

```python
from openpicture import annotate
annotate.set_fields(path, {"rating": 5, "notes": "…"})
annotate.remove_fields(path, ["notes"])
annotate.add_label(path, "scene", "42B", created_by="ae", span=None)
annotate.edit(path, mutate)     # mutate(editorial_annotations) -> None; raises AnnotationRefused on escape
```

## Diff and companions

```python
from openpicture import diff, companion
result = diff.diff(manifest_a, manifest_b)      # DiffResult; .machine_identical, .identical, .as_dict()
companion.iconik_json(manifest)                 # iconik sidecar shape
companion.flat_json(manifest)                   # one-level projection
companion.write_companion(opi_path, kind="iconik", dest=None)   # -> Path
companion.companion_path(opi_path)              # clip.mov.opi -> clip.mov.json
```

## Layering

`core`-style discipline applies: nothing in the package imports outside the
standard library. `ed25519` upgrades itself to the `cryptography` backend
when that package happens to be present, and nothing else changes.
