# Run vectors — §7

- `valid-run-id.json` — the §7.1 `run_id` derivation; `payload` is the
  exact JCS bytes hashed. Unit.
- `valid-rerun-replace-in-place.json` — a signed run re-run at the same
  identity. The key is RFC 8032 test key 1, so the recorded signatures
  reproduce. Unit (the runner also materialises `before` and `after` as
  valid files).
- `valid-host-and-models.json` / `invalid-host-and-models.json` — the §7.2
  `host` and `models` keys. The invalid one carries the mistake the rule
  exists to stop: a machine name and a user name written into `host`, where
  a signature would make them permanent.
- `valid-*.json`, `invalid-*.json` — complete manifests. `expect.all_ok`,
  `expect.failing` (check names), `expect.current` (§7.3 selection),
  `expect.lineage_of_new` (§7.3 lineage).

Each file: `{"manifest": {...}, "expect": {...}}`. Full shape:
`vectors/README.md`.
