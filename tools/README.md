# tools

Generators and the conformance runner. Only one file here is not source.

- **`build_spec.py`** — assembles `SPEC.md` from the chapters in `spec/`
  (order: `spec/CHAPTERS.txt`). `--check` exits 1 if SPEC.md is stale;
  `tests/test_spec_build.py` enforces that in CI. Edit the chapters,
  never SPEC.md.
- **`build_bundle.py`** — concatenates the five stdlib-only validator
  modules (`jcs`, `ed25519`, `container`, `sign`, `validate`) into
  `opi_verify.py`. Deterministic; `tests/test_bundle.py` fails if the
  checked-in bundle drifts from the sources.
- **`opi_verify.py`** — **generated, do not edit.** The single-file
  validator (~133 KB, larger than SPEC.md) for MAM vendors and CI jobs:
  copy it next to a shell script, no install, no import path. Regenerate
  with `build_bundle.py` after changing those five modules.
- **`conformance/run.py`** — the §16 conformance runner.
  `--self` must be all-pass for the reference validator;
  `--validator "your-validator --json {file}"` produces a report for any
  outside implementation. `tests/test_conformance.py` covers the runner
  itself.
- **`conformance/producer.py`** — the §16.4 producer P-check report.
  Reuses the reference validator and reports each P-check as pass, fail or
  unavailable, separating file-decidable checks from producer obligations and
  checks that need external evidence; validator success is not producer
  conformance. `tests/test_producer_conformance.py` covers it.
