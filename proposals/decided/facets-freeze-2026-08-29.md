# Facet freeze proposal — memo to D for decision B12

> **DECIDED 2026-08-29. B12 is closed.** The recommendation below was
> accepted with one addition: `description` was in neither table, and is
> **held** — its shape is settled but nothing emits it, and the freeze
> criterion is evidence from real footage. Seven facets are frozen in
> Appendix C, plus the embeddings attachment form in §7b.3: eight things.
> The five open questions were answered as follows, and the answers are in
> the specification, not only here.
>
> 1. **Confidence scale** — freeze `unit`, keep `bp` optional. RFC 8785
>    implementations now exist everywhere a producer is likely written, so
>    forcing integers no longer buys a third party enough to justify making
>    every producer scale its floats. (C.0.1)
> 2. **`camera_motion`** — freeze the shape, mark the facet `research`, keep
>    the confidence cap; do not hold the freeze for it. This is what forced
>    the appendix onto two axes: shape and maturity are different facts, and
>    one word could not carry both. (C.0, C.7)
> 3. **Row form vs canonical** — permanently equivalent, no hoisting
>    deadline. One branch in every reader beats a transform in every
>    store-backed producer. (C.0)
> 4. **`log_profile`** — enumerate the known encodings and require
>    `x-<vendor>_<profile>` for anything else. Enums are what make files
>    comparable across producers; free text alone drifts. (C.5)
> 5. **Calibration flag** — leave it out of the file. Self-asserted
>    calibration is unfalsifiable from inside the file; §16.7's conformance
>    statement is where a producer says how it measured. (C.0.1)
>
> Kept below as written, as the record of what was proposed and why.

*Non-normative. 2026-08-29. Written against Appendix C as revised today and
against what latent actually emits on real footage (the Day 3 pilot run,
August 2026).*

## What "freeze" means here

Freezing a facet means: its name, required keys, units and enums stop
changing without a major-version bump; a second implementer can build it
from Appendix C alone; `facets-0.schema.json` becomes normative for it.
Facets *not* frozen stay in the appendix as proposals — producers may emit
them, validators ignore them, nobody may claim conformance on them.

## Recommendation

**Freeze eight, hold ten.**

### Freeze for v1 (emitted today, deterministic or well-understood)

| facet | why it is safe to freeze |
|---|---|
| `shots` | the substrate every other facet hangs on; MPEG-7 MDS shape; latent emits it on every asset |
| `transcript` | recognizer-agnostic shape (text + span + score + language); latent emits it via Whisper |
| `usability` | measured metrics, no model risk |
| `exposure_color` | pure DSP, review tier **High**; latent emits with these exact keys |
| `energy_curve` | pure DSP, review tier **High**; latent emits; MPEG-7 MotionActivity lineage |
| `audio_usability` | levels are measured; the one inference (`dominant`) is coarse and honest; review **Medium** |
| `camera_motion` | **freeze the shape, not a quality claim.** MPEG-7's eight verbs are a 2002 ISO vocabulary — the *keys* will not move. What is research-grade is the producer, and C.7 already forces confidence caps on zoom/dolly. Review tier **Low** — keep the "research-grade" label in every doc |
| `embeddings` (attachment form) | the safetensors member + attachment keys are stable and exercised end to end |

### Hold (do not freeze in v1)

| facet | reason |
|---|---|
| `shot_size` | review **Medium**, nobody emits it yet, the enum boundary between MWS/WS is contested in the trade; freeze after one real producer runs on real footage |
| `composition` | measured and **High**, but needs a pose model nobody has wired; hold to avoid freezing keys we have never produced |
| `focus` | same |
| `take` | slate OCR on handwriting is the weak link; shape may need `alternatives[]` |
| `continuity` | review **Low**; the hardest problem; `research` |
| `clearance` | **never freeze as a quality claim**; the §10.3 rules are normative already, the field list is not. Hold until the C4 clearance posture and D2 data-handling terms are in a contract |
| `text_on_screen`, `persons`, `audio_events` | Tier 1 proposals with no producer yet |
| `embeddings` (facet form) | the attachment form suffices until a consumer needs per-row metadata |

## What latent emits today vs. what freezing requires

| facet | latent today | gap to freeze |
|---|---|---|
| `shots`, `transcript`, `usability` | canonical/row form as specified | none |
| `exposure_color`, `energy_curve` | row form, keys match C.5/C.6; carries `confidence` = coverage | switch to `coverage` key (transitional rule covers it meanwhile) |
| `camera_motion` | row form, keys match C.7 | none; caps already implemented |
| `audio_usability` | row form, keys match C.8 | none |
| `embeddings` | attachment form with `kind/dim/count/dtype/normalized` | none |
| hoisting | everything is row form (`signals[] kind=facet.*`) | producers SHOULD hoist to `facets.<name>[]` after freeze — a one-function change in the reference producer's OPI writer |

## What a second implementer needs

1. Appendix C as written — every frozen facet has keys, units, ranges, enums
   and an example.
2. `facets-0.schema.json` for machine validation of the frozen set.
3. `openpicture.facets.checks()` as the reference behaviour for structural
   and §10.3 checks (unknown facets pass).
4. Vectors in `vectors/facets/` — one valid entry per frozen facet from real
   producer output, and the failure cases.
5. Two things the text cannot give them: an eval corpus to calibrate against,
   and the producer implementations. That is by design — the format is free,
   filling it well is the product.

## Open questions for D

1. **Confidence scale default.** C.0.1 says `unit` floats unless the run
   declares `bp`. The A3 audit argued for integers everywhere so third-party
   canonicalizers stay trivial. Freeze `unit` (what latent emits) or force
   `bp`? Recommendation: freeze `unit`, keep `bp` optional.
2. **`camera_motion` in v1 or not.** Freezing the shape while the producer is
   research-grade is defensible (the vocabulary is ISO's) but it will be read
   as a claim. Alternative: freeze everything else, ship camera motion as the
   one visibly-experimental facet.
3. **Hoisting deadline.** Do we require canonical form at freeze, or keep the
   row form as a permanent equivalent encoding? Recommendation: permanent
   equivalence — it costs readers one branch and saves every store-backed
   producer a transform.
4. **`log_profile` enum.** The list in C.5 is a start; whether to enumerate at
   all or leave free text is a taste call.
5. **A run-level calibration flag.** C.0.1 distinguishes a *calibrated
   probability* from a *heuristic score*, but a file cannot say which one a
   run emitted: §7.2 defines no key for it. C.0.1 used to cite
   `confidence_calibrated: true` as if §7 defined it; it never did, and the
   dangling reference is now removed. Either add an optional run key at the
   freeze, or leave the claim to the producer's conformance statement
   (§16.7). Recommendation: leave it out of the file. A boolean asserting
   one's own calibration is unfalsifiable from inside the file, and §10.3
   already refuses accuracy claims for the facets where it would matter
   most.
