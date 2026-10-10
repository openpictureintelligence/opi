# Time vectors — §6A

Five JSON tables, each `{"description": str, "cases": [...], ...}`.
Filenames are bare because these are data tables, not pass/fail cases.

- `rates.json`, `timecode.json`, `spans.json`, `interop.json` — unit
  vectors for the time model, including the §6A.6 round-trip strings.
- `consistency.json` — complete files: the runner materialises each case
  into a manifest; `valid: false` cases MUST fail a `time:` check.

Per-case shapes: `vectors/README.md`.
