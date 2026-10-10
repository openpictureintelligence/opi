# Member vectors — §4, §7b

Binary `.opi` files, regenerated deterministically by `make_vectors.py`
(`--check` verifies the checked-in bytes); edit the generator, not the
ZIPs.

- `valid-full.opi` — the reference Full file. `expected.json`'s
  `valid.file` pins its sha256 and the exact `data_offsets` of every
  aligned member; a Reader computing offsets from the local header MUST
  get these numbers.
- `case-*.opi` — valid containers exercising one edge each;
  `expected.json`'s `cases[<file>]` gives `must_fail` (check name) and
  `why` (rule).

Every file here is a complete file. Full shape: `vectors/README.md`.
