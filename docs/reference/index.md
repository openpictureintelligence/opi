---
body_class: opi-wide
---

# Reference

The exact material for implementers and validators. Read the tutorials to
understand the format; use this section when you need the command, schema or
normative rule that a tool must follow.

## Choose the level of detail

| | |
|---|---|
| Need to implement the file format | [Specification](../spec/index.md) — normative version 0, generated from the chapters in `spec/`. Where it disagrees with a tutorial, this wins. |
| Need to use the reference CLI | [Command line](cli.md) — every `openpicture` subcommand and its current `--help` output. |
| Need to integrate from Python | [Python API](python-api.md) — loading, container access, signing, validation, runs, time, members, keys and annotations. |
| Need a dependency-free validation gate | [Standalone validator](validator.md) — one standard-library file, its checks, statuses and exit codes. |
| Need machine-readable shape | [JSON Schemas](schema.md) — the envelope schema and the provisional facet vocabulary. |

Test vectors for implementers in other languages live in the repository
under `vectors/` and in the specification's Appendix B.
