# Open Picture Intelligence — `.opi` file format, version 0

**Status:** Draft, version 0 (pre-freeze). **Date:** 2026-08-29.
**Reference implementation:** the `openpicture` Python package in this repository.
**Schema:** `schema/opi-0.schema.json`.

A `.opi` file is a per-clip sidecar that carries the *intelligence layer* —
shots, transcript, labels, embeddings, provenance — beside the media it
describes. It is bound to that media by checksum, signed per producer, and
owned by whoever owns the footage. It is readable with a text editor or
`unzip`, forgeable by nobody, and encrypted never.

This document is normative. Where it and the reference implementation
disagree, this document is wrong and MUST be fixed — the implementation is
what shipped. Behaviour that is *recommended but not yet decided* is marked
**[PENDING]** and uses SHOULD/MAY, never MUST. B14 (one physical form) and B15 (key log) were decided on 2026-08-29 and are normative in this revision.

---
