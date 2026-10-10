## 10. Validation

### 10.1 The checks

A conforming validator MUST check, and report each as pass/fail with a
reason:

1. **readable** — the file detects as Core or Full (§3.1) and parses as a
   JSON object (Full: `manifest.json` present and parseable).
2. **envelope** — `opi`, `profile`, `media_binding` present; `opi` a
   non-negative integer and the first key; `profile` matches the bytes.
3. **binding** — `media_binding.files` non-empty; each entry has a basename
   `name` and a 64-lowercase-hex `sha256`; exactly one entry is the
   `original` (§6.3); an `original` present beside the sidecar matches its
   digest.
4. **human layer** — `editorial_annotations`, if present, is an object.
5. **attachments** — the union of run attachments is consistent (§7.6);
   Core declares none.
6. **members** (Full) — `manifest.json` present and byte-identical to the
   Core serialization; every member declared; every declared member
   present with matching SHA-256 and size; every `.bin` member STORED at a
   64-aligned data offset.
7. **signatures** — §9.4, per run.

Overall result: `invalid` if any check fails; otherwise `valid-signed`,
`valid-partial` or `valid-unsigned` from the signature status.

### 10.2 What a validator MUST NOT reject

A validator MUST NOT reject a file for unknown top-level keys, unknown run
keys, or unknown facets. Structural checks for *known* facets and the
sensitive-facet rules of §10.3 are part of the Validator class (§16.3);
anything beyond that is a separate, optional layer.

The complete list of checks a conforming Validator evaluates — including
the time (§6A.7), run (§7.8) and member (§7b.6) checks added by those
chapters — the result vocabulary and exit codes are collected in §16.3.
The vector suite that proves them is §16.5.

### 10.3 Sensitive facets — review flags, never determinations

Some facets describe people and rights: whether a **minor** appears, whether
a **face** is recognizable, whether a **logo**, **artwork**, **signage** or
**licensed music** is present. These are the clearance facets (Appendix C).
For every such facet:

1. A producer MUST emit it as a **review flag**, with `review_required:
   true`, never as a determination. The file records that a human should
   look here; it does not record a conclusion.
2. The file MUST NOT carry an accuracy, recall or precision claim for the
   producer of a sensitive facet. Calibrated `confidence` on the entry is
   permitted; a statement about how often the producer is right is not.
3. Producers SHOULD tune sensitive facets for recall over precision — a false
   positive costs a reviewer seconds; a false negative costs a lawsuit.
4. Readers and validators MUST NOT treat the **absence** of a sensitive facet
   as a negative determination. "No minor flag" means "not flagged", never
   "no minor present".
5. No `.opi` producer, validator or reader may represent a sensitive facet as
   a clearance certification. Certification is a licensed human act.

These are format rules, not product guidance: a file that violates 1 or 2
is non-conformant.
