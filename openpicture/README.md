# openpicture — the reference implementation

Standard-library Python; `cryptography` is an optional fast path, never
required. SPEC.md is normative; this package is its reference reading.

## Layout

Two kinds of module live side by side:

- **Chapter domains** — named for the concept a specification chapter
  defines: `time` (§6A), `runs` (§7), `members` (§4, §7b), `facets`
  (Appendix C), and the human layer around them: `annotate`,
  `companion`, `keyframes`, `embeddings`, `diff`.
- **Plumbing** — the container and crypto the chapters sit on:
  `jcs` (RFC 8785), `ed25519` (RFC 8032), `container` (the ZIP rules),
  `keys`, and the front doors built on both: `reader`, `validate`,
  `discover`, `cli`.

## Where does a new test go?

| Module(s) | Test file |
|---|---|
| `annotate`, `diff` | `tests/test_annotate_diff.py` |
| `cli` | `tests/test_cli_tools.py` |
| `companion` | `tests/test_companion.py` |
| `container`, `sign`, `validate` | `tests/test_container_sign_validate.py` |
| `discover` | `tests/test_discover.py` |
| `ed25519` | `tests/test_ed25519.py` |
| `embeddings` | `tests/test_embeddings.py` |
| `facets` | `tests/test_facets.py` |
| `jcs` | `tests/test_jcs.py` |
| `keyframes` | `tests/test_keyframes.py` |
| `keys` | `tests/test_keys.py` |
| `members` | `tests/test_members.py` |
| `reader` | `tests/test_reader.py` |
| `runs` | `tests/test_runs.py` |
| `time` | `tests/test_time.py` |

Cross-cutting suites: the JSON Schema (`tests/test_schema.py`), the
manifest envelope key by key via `vectors/manifest/`
(`tests/test_manifest.py`), the generated artifacts
(`tests/test_bundle.py`, `tests/test_spec_build.py`), the conformance
runner (`tests/test_conformance.py`), and spec cross-references
(`tests/test_spec_xrefs.py`).
