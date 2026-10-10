# Security

## What `.opi` promises, and what it does not

- **Signed, never encrypted.** A `.opi` is readable by anyone who has it.
  Signatures let a reader verify *who produced* a run of machine
  intelligence and *which media* it describes; they do not hide anything.
- **Per-run signatures.** Each producer run in `machine_intelligence` is
  signed separately over the RFC 8785 canonical form of
  `{"media_binding": …, "run": …}`. Tampering with a run or with the media
  binding invalidates that run's signature. The `editorial_annotations`
  block is deliberately unsigned and editable.
- **Unsigned is valid.** A verifier reports `unsigned`, never `invalid`, for
  a file with no signatures. Consumers must decide their own trust policy;
  the key log (`openpicture keys`) is the recommended trust anchor.
- **The `path` field is untrusted.** `media_binding.files[].path` records
  where the producer saw the media. Readers must bind on `sha256`, never on
  the path.
- **Members are declared and hashed.** Every ZIP member other than
  `manifest.json` must be declared in a signed run's `attachments` with its
  SHA-256 and size; undeclared or mismatched members fail validation.
- **`openpicture unpack` refuses zip-slip.** Member names that would escape
  the target directory are rejected.
- **Size limits.** Members over 2 GiB are not permitted (ZIP64 padding would
  break the alignment guarantee). Validators should bound the manifest size
  they will parse from untrusted sources.

## Key custody

Secret keys are 32 raw bytes stored hex-encoded by `openpicture keygen`
with mode `0600`. The reference implementation never transmits keys. Loss of
a secret key means no further signatures from that identity; it does not
invalidate historical files — public keys are never withdrawn from a key log.

## Reporting a vulnerability

Please do not open a public issue for a security problem in the format or
the reference implementation. Use GitHub's private reporting form:
[Report a vulnerability](https://github.com/openpictureintelligence/opi/security/advisories/new).
You can also email the steward at **hello@openpicture.io**. Include a
description and, if possible, a synthetic file that reproduces the problem;
do not send private footage or production signing keys.

The steward will acknowledge the report within a few days and provide a fix
or a written assessment before any public disclosure. The
[governance page](https://github.com/openpictureintelligence/opi/blob/main/docs/contribute/governance.md)
describes stewardship.
