# Proposing a specification change

The specification is the product, so a change to it is a change to every
file anyone has written. Proposals that can be evaluated share a shape.

## What a proposal contains

1. **The problem.** A file, producer or consumer that cannot do something
   today, stated concretely. "It would be cleaner" is not a problem.
2. **The rule**, in the specification's voice: MUST / SHOULD / MAY, with the
   sentence that would go into the relevant chapter under `spec/`.
3. **What a validator checks.** A rule the reference validator cannot check
   is a suggestion, not a rule. Say which check is added or changed and
   which existing files it would fail.
4. **Compatibility.** Additive (a new optional key, a new facet, a new
   member type) or incompatible (a required key removed or retyped, a change
   to the signature payload, the container or the detection algorithm).
   Additive changes are accepted at any time during version 0. Incompatible
   changes bump the format version and are announced first.
5. **A test vector** where bytes are involved.

Open it as an issue or a pull request against the chapter in `spec/`. A
pull request that lands includes the chapter text, the schema, a test, a
`CHANGELOG.md` line and — if it touches bytes — a regenerated
`tools/opi_verify.py`.

## Proposing a facet

Facets are open: you can emit any facet today under your own run, and no
validator will reject it. To propose one for the shared vocabulary in
Appendix C, add to the shape above:

- the entry's JSON shape, every key typed, with units and ranges;
- the vocabulary anchor if a standard has one (MPEG-7, IPTC Video Metadata
  Hub, SMPTE), or a statement that none does;
- how `confidence` is derived, and whether the facet is a measured fact
  (no confidence) or an inference (confidence required);
- whether the facet touches people or rights. If it does, the
  sensitive-facets rule in the specification applies: the facet is a review
  flag with `review_required: true`, never a determination, and no accuracy
  claim travels in the file. The proposal must say how it complies.

## What happens next

The steward evaluates against the rules in [governance](governance.md),
replies on the issue, and records an accepted change in the changelog with
its reasoning. Decisions that affect adopters — the schema freeze,
registrations, anything a third party has to implement — are announced
ahead of taking effect.
