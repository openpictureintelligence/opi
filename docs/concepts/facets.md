# Facets

A **facet** is one kind of claim a run makes about the clip: shot
boundaries, a transcript segment, a camera movement, an exposure
measurement. Facets live under `machine_intelligence[i].facets.<name>` as
lists of entries. Each entry may carry a `span` (integer frames at the
binding's rate, out-point exclusive, with derived seconds and timecode),
a `confidence`, and a `shot_idx` into the run's own shots.

## Facets are open

The specification does not enumerate facets, and a validator **must not**
reject a file for a facet it has not heard of. That is the
forward-compatibility contract of version 0: readers ignore what they do
not know.

Part of the vocabulary below is now **frozen** — decision B12 closed on
2026-08-29 — and Appendix C is normative for those facets: their names,
required keys, units and enums do not change without a major-version bump,
and an implementation may claim conformance on them. The rest remain
proposals, published so that producers converge, mirrored machine-readably
in `schema/facets-0.schema.json`, and non-normative until they freeze too.

## Three tiers of description

**Tier 0 — facts** come from the file: container, codec, dimensions, frame
rate, source timecode, camera. These live in `media_binding`, and where the
IPTC Video Metadata Hub has a slot the names mirror it (`videoCoding`,
`videoFrameRate`, `fileDuration`, `frameSize`, `recordingDevice`) so an
IPTC egress is a rename, not a mapping.

**Tier 1 — content** is what most tools produce today: shot boundaries,
timecoded diarized transcript, per-shot description, on-screen text,
person clusters, audio events, usability flags, embeddings.

**Tier 2 — edit-descriptive** is how the shot behaves as film. This is the
layer no shipped format has carried, and the one an editor works in.

| Facet | What it captures | Vocabulary anchor |
|---|---|---|
| `camera_motion` | dominant movement, direction, magnitude, editorial intent | **MPEG-7 CameraMotion** (ISO/IEC 15938-3): `fixed` `pan` `tilt` `roll` `zoom` `dolly` `track` `boom`; plus an `editorial` layer: `static` `push` `pull` `whip` `drift` `handheld` `locked_off` `reveal` |
| `shot_size` | ECU · CU · MCU · MS · MWS · WS · EWS, with the measured subject-height ratio | own ordered CV; IPTC Scene NewsCodes on egress |
| `composition` | headroom, lead room, thirds, symmetry, horizon tilt, subject position | geometry, deterministic |
| `exposure_color` | clipped highlights, crushed blacks, mean luma, log-profile suspected, white-balance drift | DSP, deterministic |
| `focus` | sharpness, in focus, shallow depth of field, anamorphic, flare | |
| `continuity` | screen direction, eyeline yaw/pitch, staging, key-light side, time of day, weather | the unclaimed layer |
| `take` | scene / shot / take from the slate, setup cluster, circle take | |
| `audio_usability` | speech present, intelligibility, SNR, level, clipping, wind, music bed, room tone | |
| `energy_curve` | visual and audio intensity over the span, sampled | MPEG-7 MotionActivity lineage |
| `clearance` | review flags: logo, face, minor, artwork, licensed music, signage, text | governed by the sensitive-facets rule |
| `embeddings` | references into the run's safetensors members | |

Standing on MPEG-7's 2002 vocabulary for kinematics is deliberate: it is
an ISO enum with a quarter-century of citations, and the editorial layer
on top of it is what MPEG-7 never had.

```json
{"base": "dolly", "direction": "in", "magnitude": 0.35, "editorial": "push",
 "fraction_of_span": 0.9, "confidence": 8200,
 "span": {"frame_in": 0, "frame_out": 96}}
```

## Confidence is per entry and honest

Every entry may carry `confidence` — a float in [0, 1] or a basis-point
integer 0–10000 (integers are preferred in signed blocks so third-party
canonicalizers stay trivial). A producer that cannot measure a facet at
useful confidence omits it: an absent facet is honest, a low-confidence
guess is a liability. The reference producer ships its optical-flow
camera-motion classifier as *research grade*, capping confidence at 0.75
for pan/tilt and 0.6 for zoom-versus-dolly, because that distinction is
genuinely hard without parallax.

## Sensitive facets are review flags, never determinations

Facets about people and rights — whether a **minor** appears, whether a
**face** is recognizable, whether a **logo**, **artwork**, **signage** or
**licensed music** is present — are governed by a normative rule
(specification §10.3):

1. They are emitted as review flags with `review_required: true`, never as
   determinations.
2. The file may not carry an accuracy, recall or precision claim for the
   producer of a sensitive facet.
3. Producers should tune them for recall over precision: a false positive
   costs a reviewer seconds, a false negative costs a lawsuit.
4. Absence of a flag is never a negative determination.
5. No producer, validator or reader may present them as a clearance
   certification. Certification is a licensed human act.

A file that violates 1 or 2 is non-conformant. This is a format rule, not
product guidance, because the alternative — a percentage beside the word
"minor" in a marketing claim — is how this goes wrong.

## What B12 froze, and what it did not

**Frozen (2026-08-29):** `shots`, `transcript`, `usability`,
`exposure_color`, `energy_curve`, `audio_usability`, `camera_motion` — and
the embeddings *attachment* form, which §7b.3 made normative already. The
criterion was evidence: a producer emits it today, from real footage, with
these keys.

**Still proposals:** `description`, `shot_size`, `composition`, `focus`,
`take`, `continuity`, `clearance`, `text_on_screen`, `persons`,
`audio_events`. Producers may emit them, validators ignore them, nobody
claims conformance on them, and the keys may still move.

Two things worth being clear about. **Freezing a shape is not a quality
claim.** `camera_motion` is frozen and its maturity is `research`: the
eight verbs are ISO's from 2002 and will not move, while anyone's ability
to compute them is another matter, which is why C.7 caps its confidence.
And **`clearance` is deliberately never frozen as a quality claim** — the
§10.3 rules governing it are normative and always were; the field list is
not.

*Normative text: specification §7.5, §10.3, and Appendix C for the frozen
facets; proposals: the rest of Appendix C and
`schema/facets-0.schema.json`.*
