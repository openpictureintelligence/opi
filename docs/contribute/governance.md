# Governance

## License

The specification, the schemas, the reference implementation and this
documentation are licensed under **Apache License 2.0**. You may implement
the format, read and write `.opi` files, embed the validator, and build
commercial products on any of it, with attribution and without a patent
concern from the authors.

## Who decides, today

The format is stewarded by **Lunar Park**, which also builds the reference
producer. Standards are commonly born this way — a single author with a
working implementation — and the intent is that the format outlives that
arrangement: a neutral, descriptive name; a published specification that
outranks the implementation when they disagree (§0 of the spec puts it the
other way round for now, deliberately: what shipped is the truth until the
freeze, and the spec is corrected to match); and a validator anyone can
run.

Decisions that change the format are recorded, dated, with reasoning, in
the steward's decision log. Decisions that affect adopters — the schema
freeze, registrations, anything a third party has to implement — will be
announced in the changelog ahead of taking effect.

## How the specification changes

1. Open an issue or a pull request against the chapter in `spec/` (`SPEC.md` is generated from those chapters). State the rule, the
   reason, and what a validator would check.
2. Additive changes (a new optional key, a new facet, a new member type)
   are accepted at any time during version 0 and do not change the format
   version.
3. Incompatible changes — a required key removed or retyped, a change to
   the signature payload or container rules — bump the format version and
   are announced first.
4. Every accepted change lands with a `CHANGELOG.md` entry, updated tests
   in the reference implementation, and a regenerated standalone validator.
5. Where the spec and the shipped implementation disagree, the
   implementation is the truth until the freeze and the spec is corrected.

## Versioning

- **Format:** the integer `opi` in the manifest. `0` is pre-freeze; `1`
  will be the first frozen version.
- **Software:** `openpicture` follows `0.0.x` during the public, pre-freeze
  alpha; only the steward moves the minor or major.

## Proposing a facet

Facets are open, so you can emit any facet today under your own run. To
propose one for the shared vocabulary: describe the entry shape, the
vocabulary anchor if a standard has one (MPEG-7, IPTC, SMPTE), how
confidence is derived, and whether the facet touches people or rights — in
which case the sensitive-facets rule applies and the proposal must say how
it complies.

## Conduct

Be precise, be kind, cite sources. Claims about accuracy, adoption or
compatibility come with a number and a link or they are marked unverified.
