# Standalone validator

`tools/opi_verify.py` is the whole validator in one file — the
canonicalizer, Ed25519, the container reader, signature verification and
the structural checks — with no dependencies beyond Python 3.11. Copy it
anywhere and run it. It is the public adoption tool: anyone can check that a
file conforms without installing or trusting anything else.

```bash
python3 opi_verify.py clip.mov.opi [more.opi ...]      # exit 0 = every file valid
python3 opi_verify.py --json clip.mov.opi               # machine-readable report
python3 opi_verify.py --media-dir /vol/footage clip.mov.opi
```

The file is **generated** from the package by `tools/build_bundle.py`; a test
fails the suite if the checked-in bundle drifts from the sources. Do not
edit it by hand.

## What it checks

| Check | Fails when |
|---|---|
| `readable` | not a `.opi`: neither a ZIP with `manifest.json` nor a JSON object |
| `canonical form` | *reported, not failed*: the file is the bare-JSON internal form |
| `has opi` / `has profile` / `has media_binding` | a required envelope key is missing |
| `opi version` | `opi` is not a non-negative integer |
| `opi is first key` | the envelope does not start with `opi` |
| `profile matches contents` | declared profile disagrees with the member list |
| `media_binding.files` | missing, empty, or an entry lacks `name` / 64-hex `sha256` |
| `media present` / `media sha256` | the named original is beside the sidecar and its hash differs (absence is allowed and reported) |
| `editorial_annotations` | present but not an object |
| `has manifest.json` | a ZIP without the manifest |
| `members declared` | a member no run declares |
| `attachment <name>` | declared but absent, or sha256/size mismatch, or two runs disagree |
| `<name> stored+aligned` | a `.bin` / `.safetensors` member is compressed or its data offset is not a multiple of 64 |
| `run[i] <status>` | per run: `valid`, `unsigned`, or `invalid` with the reason (malformed key, unsupported algorithm, signature does not verify) |

It does **not** check facet semantics. A validator that rejected a file for
an unknown facet would break the forward-compatibility rule; the JSON
Schemas exist for that, in CI, not here.

## Status vocabulary

```text
valid-signed     every check passed; every run verified
valid-partial    every check passed; some runs verified, the rest unsigned
valid-unsigned   every check passed; no run is signed
invalid          at least one check failed — see the FAIL lines
```

## Exit codes

`0` every file valid (signed or not). `1` at least one file invalid.
`2` usage error.

## Verifying without Python

The signature scheme is deliberately reproducible elsewhere. To verify a
run by hand you need an RFC 8785 canonicalizer and an Ed25519 verifier:

1. Take `media_binding` from the manifest and the run object with its
   `signature` key removed.
2. Canonicalize `{"media_binding": …, "run": …}` per RFC 8785.
3. Verify the base64 `signature` over those bytes with the hex
   `public_key` as a raw 32-byte Ed25519 key.

OpenSSL 3 will do step 3 with the key wrapped in a DER SubjectPublicKeyInfo
prefix (`302a300506032b6570032100` + the raw key); macOS's bundled
LibreSSL does not support Ed25519. The specification's Appendix B carries a
complete test vector — a fixed secret key, the exact canonical payload
bytes, and the resulting signature — for implementers to check against.
