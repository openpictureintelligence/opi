## Appendix C — Facet vocabulary

**Status: partly frozen.** Decision B12 closed on 2026-08-29. Seven facets
here are **frozen**, and this appendix is **normative** for them; the rest
remain proposals. It is mirrored machine-readably in
`schema/facets-0.schema.json`, and the reference implementation's
`openpicture.facets.checks()` applies the structural rules below to facets
it knows and passes everything else.

Every facet is described on **two independent axes**. Conflating them is
what B12 had to undo: `camera_motion` is an ISO vocabulary whose keys will
not move, computed by a producer that is frankly research-grade, and one
word could not say both.

| **Shape** | Meaning |
|---|---|
| `frozen` | the name, required keys, units and enums do not change without a major-version bump. A second implementer can build the facet from this text alone, `facets-0.schema.json` is normative for it, and an implementation may claim conformance on it (§16). |
| `proposed` | not frozen. Producers MAY emit it, validators MUST ignore it (§10.2), nobody may claim conformance on it, and the keys may still move. |

| **Maturity** | Meaning |
|---|---|
| `stable` | the reference producer (latent) emits it today, from real footage, with these keys |
| `proposed` | designed, not yet emitted by any producer; a second implementer could build it from this text |
| `research` | the measurement itself is unsolved; the shape may be settled but the numbers are exploratory |

### C.0.0 What B12 froze

Frozen: `shots`, `transcript`, `usability`, `exposure_color`,
`energy_curve`, `audio_usability`, `camera_motion` — and the **embeddings
attachment** form, which is §7b.3 in the normative body of this
specification, not a facet here. Eight things in all.

Held as proposals: `description`, `shot_size`, `composition`, `focus`,
`take`, `continuity`, `clearance`, `text_on_screen`, `persons`,
`audio_events`, and the embeddings *facet* form.

The freeze criterion was: a producer emits it today, from real footage,
with these keys. `description` is designed and stable in shape but nothing
emits it, so it waits — the criterion is about evidence, not elegance.
`clearance` is deliberately never frozen as a quality claim: §10.3's rules
about it are normative already and always were, the field list is not.

Freezing a facet does **not** freeze how well anyone computes it.
`camera_motion` is the clearest case: frozen shape, `research` maturity,
and C.7's confidence cap. A frozen facet is a promise about keys, never
about truth (§16.8).

### C.0 Conventions

**Where facets live.** `machine_intelligence[i].facets` is an object whose
keys are facet names and whose values are **lists of entries**. One entry
describes one span of the media (usually one shot). Entries carry no
`producer` or `model_version`; those are the run's (§7).

**Two encodings, one meaning.** The canonical form hoists a facet's keys to
the entry:

```json
"facets": {"camera_motion": [{"span": {…}, "verb": "pan", "confidence": 0.7, …}]}
```

The **row form** is a generic entry under `facets.signals[]` with
`kind: "facet.<name>"`, the same keys inside `payload`, and an optional
`text` carrying the entry's headline value:

```json
"facets": {"signals": [{"kind": "facet.camera_motion", "text": "pan",
                        "payload": {"verb": "pan", …}, "span": {…}, "confidence": 0.7}]}
```

The row form is what a store-backed producer emits naturally (one row per
signal). Readers MUST accept both and treat them as equivalent.

`text` is optional on either form (F2). The row form already carries it; on
the canonical form it is the same key, hoisted to the entry, and it holds the
entry's searchable headline value without naming a facet-specific key. A
consumer that builds a search index SHOULD read `text` when present, whichever
encoding the producer chose.

**The two encodings are permanently equivalent** (B12, 2026-08-29). Neither
is deprecated and there is no hoisting deadline: the canonical form is not
"the real one" and the row form is not a transitional concession. The trade
was one branch in every reader against a transform in every store-backed
producer, and the branch is cheaper. A producer picks whichever its storage
makes natural and a conforming reader handles both.

Tier 1 facets that are inherently rows — `transcript`, `description`,
`usability` — use `signals[]` with a bare `kind` (no `facet.` prefix) and
are listed below in that form.

**Common entry keys.**

| key | type | req | meaning |
|---|---|---|---|
| `span` | object | MAY (§7.5) | the range described, in the shape §6A defines — frames are the position, seconds and timecode are derived. Absent means the whole asset, which is what a `scope: "asset"` roll-up entry uses; most facet entries here describe a span and carry one. |
| `shot_idx` | integer ≥ 0 | MAY | index into the run's (or the referenced run's) `shots[]` |
| `scope` | `"shot"` \| `"asset"` | MAY | default `shot`; `asset` for a whole-asset roll-up entry |
| `confidence` | number | see C.0.1 | how sure the producer is *that this inference is right* |
| `coverage` | number 0–1 | MAY | fraction of the span actually sampled/measured |
| `text` | string | MAY | the entry's searchable headline value (see below), so a consumer can index a canonical entry without understanding its facet-specific keys |

#### C.0.1 Confidence conventions

1. **Scale.** A run declares `confidence_scale` per §7: `"unit"` (float in
   [0, 1]) or `"bp"` (integer basis points 0–10000). Absent means `unit`.
   All `confidence` values in a run use the run's scale.

   Frozen by B12: **`unit` is the default and `bp` stays optional.** Forcing
   integers everywhere was argued for so that third-party canonicalizers
   stayed trivial; RFC 8785 implementations now exist in every language a
   producer is likely to be written in, so the argument no longer pays for
   the friction of making every producer scale its floats.
2. **Inferences carry confidence; measurements do not.** A facet whose value
   is *inferred* (shot size, camera motion verb, speech present, a
   clearance flag) MUST carry `confidence`. A facet whose value is
   *measured* by deterministic arithmetic over the pixels or samples
   (exposure statistics, energy series, audio levels) sets `confidence` to
   `null` — the key is always present, per §7, but there is nothing to be
   unsure about — and SHOULD carry `coverage` instead, saying how much of
   the span the numbers were computed from. Transitional rule: a numeric
   `confidence` on a measured facet is read as `coverage`.

   **Who enforces which half.** Presence and scale are the envelope's, and
   binding: `openpicture.runs.checks` fails any facet entry that omits
   `confidence` or carries a value outside the run's scale, for every facet,
   known or not (`runs: run[i] facet <name>`). Whether a facet is *measured*
   rather than inferred is vocabulary, so it is checked here, against this
   appendix, and only advisory: `openpicture.facets.checks` reports a number
   on a measured facet as a **passing** row noting it was read as coverage.
   The split is deliberate — a validator must not reject a file over a
   vocabulary this appendix has not frozen (§10.2), and nothing here is
   normative until B12 closes.
3. **What the number means, per facet,** is stated in each section below as
   either *calibrated probability* (the producer has measured that entries
   at 0.8 are right about 80% of the time) or *heuristic score* (monotone in
   the producer's belief, not calibrated). A file has no way to say which of
   the two a run emitted: §7.2 defines no key for it, and a producer that
   wants the distinction on the record states it in its conformance
   statement (§16.7) or its own documentation. **B12 decided against a
   run-level calibration flag** (2026-08-29): a boolean asserting one's own
   calibration is unfalsifiable from inside the file, and §10.3 already
   refuses accuracy claims for the facets where it would matter most. The
   conformance statement is where a producer says how it measured its
   numbers, because that is a document a reader can hold it to.
4. **Confidence is never accuracy.** A `confidence` value describes one
   entry. It MUST NOT be reported, in the file or about the file, as the
   producer's accuracy, recall or precision. Producers that know their
   benchmark numbers publish them in their own documentation, not in `.opi`
   files. For sensitive facets §10.3 makes this a MUST at the format level.

#### C.0.2 Names that mirror a standard

Where a neighbouring standard has the concept, the name is reused so an
egress is a rename, not a mapping. Standards are cited per facet as: **IPTC
VMH** (Video Metadata Hub 1.7, PVMD JSON — the only JSON-native neighbour
with an official schema), **MPEG-7** (ISO/IEC 15938-3 Visual, 15938-5 MDS
— XML, 2002, the only ISO standard that modelled machine-derived
description), or **none**.

| Ours | Mirrors | Note |
|---|---|---|
| `media_binding.files[].video_codec` | VMH `videoCoding` | |
| `media_binding.timecode.rate` | VMH `videoFrameRate` | ours is rational |
| `media_binding.duration_s` | VMH `fileDuration` | |
| `files[].width` / `height` | VMH `frameSize` | |
| `media_binding.camera` | VMH `recordingDevice` | |
| `signals[kind=transcript]` | VMH `transcript` / `transcriptLinks`; MPEG-7 `SpokenContent` | |
| `text_on_screen` | VMH `dataOnScreen` | OCR |
| `persons` | VMH `personsShown` / `personsHeard` | clusters, unnamed until labelled |
| `shots` | MPEG-7 MDS `VideoSegment` / `TemporalDecomposition` | |
| `camera_motion.verb` | MPEG-7 `CameraMotion` | eight verbs verbatim |
| `camera_motion.verbs` | MPEG-7 `FractionalPresence` | |
| `energy_curve` | MPEG-7 `MotionActivity` (concept) | ours is a series, theirs a level |
| `shot_size` → egress | VMH `videoShotTypes` (slot) + IPTC Scene NewsCodes | IPTC has a slot, not a CV |
| `clearance[flag=face]` → egress | VMH `modelReleaseStatus` | CV term on egress, never a boolean |
| `clearance[flag=logo\|artwork\|signage]` → egress | VMH `propertyReleaseStatus` | |
| run `producer` / `model_version` → egress | VMH `aISystemUsed`, `digitalSourceType` | |

---

### C.1 `shots` — Tier 1 · **frozen** · maturity `stable` · MPEG-7 MDS `VideoSegment`

The temporal decomposition of the asset into shots. Entries are
**contiguous and non-overlapping** in frame terms: entry *k*'s `frame_out`
equals entry *k+1*'s `frame_in`, and the union covers the asset (§6A.4,
which says how a writer derives the shared boundary — once, by ceiling, so
that the frame a cut falls in belongs to the outgoing shot). A continuous
take is **one** shot, never zero (a run with shot detection that found no
cuts emits a single entry spanning the asset).

| key | type | req | meaning |
|---|---|---|---|
| `idx` | integer ≥ 0 | REQUIRED | position in this run's decomposition, 0-based, dense |
| `span` | object | REQUIRED | §6A; `frame_in`, `frame_out` REQUIRED when the asset has a rate |
| `confidence` | number \| `null` | REQUIRED (§7.5) | *heuristic score* — the detector's cut confidence at `frame_in`. Undefined for `idx: 0`, which has no cut before it: write `null` there. The key is never omitted. |

```json
{"idx": 1, "span": {"t_start_s": 4.2, "t_end_s": 10.0, "frame_in": 101, "frame_out": 240,
                    "tc_in": "01:00:04:05", "tc_out": "01:00:10:00", "frames": 139}, "confidence": 0.8}
```

### C.2 `signals[kind=transcript]` — Tier 1 · **frozen** · maturity `stable` · VMH `transcript`

Timecoded speech, one entry per segment as the recognizer emitted it.

| key | type | req | meaning |
|---|---|---|---|
| `kind` | `"transcript"` | REQUIRED | |
| `text` | string | REQUIRED | the segment text, as spoken, in the source language |
| `span` | object | REQUIRED | |
| `confidence` | number | REQUIRED | *heuristic score* derived from the recognizer's log-probability; not calibrated unless the run says so |
| `payload.language` | string, BCP-47 | SHOULD | e.g. `en`, `pt-BR` |
| `payload.speaker` | string | MAY | diarization label, opaque within the run (`SPEAKER_00`); never a name |
| `payload.words` | list of `{text, t_start_s, t_end_s, confidence?}` | MAY | word timings |
| `payload.translation` | `{language, text}` | MAY | |

### C.3 `signals[kind=description]` — Tier 1 · `proposed` · maturity `proposed` · none

*Held by B12, not frozen: the shape is settled but no producer emits it
yet, and the freeze criterion is evidence from real footage. Nothing here
is expected to move.*

A per-shot natural-language description from a vision-language model:
what is visible, concretely and searchably. `text` is the description;
`payload` records how it was made: `backend`, `model`, `prompt_version`,
`sample_times` (seconds), `frames_sent`, `frame_width`, `frame_height`,
`elapsed_ms`. `confidence` MAY be absent (a free-text description has no
single probability); when present it is a *heuristic score*.

### C.4 `signals[kind=usability]` — Tier 1 · **frozen** · maturity `stable` · none

Cheap per-shot production-readiness metrics, measured. No `confidence`;
`coverage` = `frame_count_sampled / requested`.

| payload key | type · unit | meaning |
|---|---|---|
| `blur_var` | number ≥ 0 | variance of the Laplacian over sampled frames; lower is softer |
| `mean_luma` | number 0–1 | mean luminance, normalized |
| `peak_luma` | number 0–1 | |
| `low_luma_ratio` | number 0–1 | fraction of sampled frames below the black threshold — lens-cap / black detector |
| `audio_rms_dbfs` | number ≤ 0 or null | window RMS level |
| `frame_count_sampled` | integer ≥ 0 | |
| `flags` | list of strings | MAY: `black`, `blur`, `clipped_audio`, `silent` — the producer's booleans, named |

### C.5 `exposure_color` — Tier 2 · **frozen** · maturity `stable` · none

Exposure and colour state, measured over sampled frames. **No
`confidence`**; `coverage` from `frames_sampled`.

| key | type · unit · range | req | meaning |
|---|---|---|---|
| `mean_ire` | number, IRE, 0–109 | REQUIRED | mean luminance on the IRE scale (0 = black, 100 = reference white) |
| `clipped_highlight_ratio` | number 0–1 | REQUIRED | fraction of sampled pixels at or above the clip level |
| `crushed_black_ratio` | number 0–1 | REQUIRED | fraction at or below the crush level |
| `contrast` | number 0–1 | REQUIRED | normalized luminance spread (interdecile range / full scale) |
| `wb_drift` | `{r_over_g, b_over_g}` numbers > 0 | REQUIRED | channel means relative to green; 1.0 = neutral |
| `log_profile_likely` | boolean | REQUIRED | flat histogram + lifted blacks pattern of a log encode |
| `log_profile` | enum or null | MAY | the encoding, when identifiable — see below. `null` when it is not. |
| `frames_sampled` | integer ≥ 0 | REQUIRED | |

```json
{"span": {"frame_in": 0, "frame_out": 1199, "t_start_s": 0.0, "t_end_s": 50.008},
 "mean_ire": 36.2, "clipped_highlight_ratio": 0.0, "crushed_black_ratio": 0.00021,
 "contrast": 0.1915, "wb_drift": {"r_over_g": 1.0188, "b_over_g": 0.9452},
 "log_profile_likely": false, "frames_sampled": 4, "coverage": 1.0}
```

**`log_profile` vocabulary** (frozen by B12). Enumerating these is what
lets a grade-prep tool compare files from two different producers; free
text alone drifts into `slog3`, `S-Log3`, `Sony S-Log3` and `sony_slog_3`
inside a year.

`ARRI_LogC3` · `ARRI_LogC4` · `Sony_SLog2` · `Sony_SLog3` ·
`Panasonic_VLog` · `Canon_CLog2` · `Canon_CLog3` · `Nikon_NLog` ·
`RED_Log3G10` · `BMD_BRAWFilm` · `Rec709`

`Rec709` is not a log encode; it is the honest "this looks like display
gamma" answer, and is distinct from `null`, which means *not identified*.

An encoding outside the list is written **`x-<vendor>_<profile>`** —
`x-DJI_DLog`, `x-Fujifilm_FLog2` — never as unconstrained free text. A
validator accepts the enumeration and the `x-` form and rejects anything
else, so a new profile is a one-line addition here rather than a silent
divergence. Adding a name to the enumeration is additive and does not need
a major bump; renaming one does.

### C.6 `energy_curve` — Tier 2 · **frozen** · maturity `stable` · MPEG-7 `MotionActivity` (concept)

Motion intensity and audio energy over time — the series a machine uses to
find *the moment* inside a clip. Measured; **no `confidence`**; `coverage`
= `samples / requested`. One entry per shot and, optionally, one with
`scope: "asset"` spanning the whole clip.

| key | type · unit | req | meaning |
|---|---|---|---|
| `t` | list of numbers, seconds from media head | REQUIRED | sample times, ascending, uniform spacing (`sample_rate_hz` = 1 / Δt) |
| `motion` | list of numbers ≥ 0, same length as `t` | REQUIRED | mean optical-flow magnitude per sample, normalized to frame width (1.0 = one frame-width per frame) |
| `audio` | list of numbers ≤ 0 or null, same length | REQUIRED | RMS level per sample in dBFS; null where no audio |
| `peak_t` | number | REQUIRED | `t` at the maximum of the composite |
| `motion_mean` | number or null | SHOULD | |
| `audio_mean_dbfs` | number or null | SHOULD | |
| `samples` | integer ≥ 0 | REQUIRED | |
| `composite` | list of numbers 0–1 | MAY | producer's fused curve; if absent consumers derive their own |

Sampling rule: producers SHOULD sample at ≥ 0.5 Hz and MUST keep `t`
uniform within an entry; the series is *the* value, so a reader can
resample but never reconstruct dropped samples.

### C.7 `camera_motion` — Tier 2 · **frozen** · maturity `research` · MPEG-7 `CameraMotion`

Camera kinematics for a shot, expressed in MPEG-7's eight verbs with an
editorial layer on top. *Inference*: `confidence` REQUIRED, *heuristic
score*, and — because zoom-vs-dolly cannot be disambiguated without parallax
(CameraBench) — a producer MUST cap confidence for `zoom`, `dolly`, `track`,
`boom` and `zoom_or_dolly` below its cap for `fixed`, `pan`, `tilt`, `roll`.

That cap is a **writer requirement** (§11): it is relative to the
producer's own ceilings, and a validator sees only samples drawn under
them, never the ceilings themselves, so it cannot be checked from one file.
What a validator can see is the ordering being contradicted — an ambiguous
verb scoring at or above everything claimed for a verb the producer can
resolve — and `openpicture.facets` reports that as a **note on a passing
check**, never a failure, because a short run can produce it honestly.

*Why this is frozen anyway.* B12 froze the shape, not the producer. The
eight verbs are ISO's from 2002 and are not going to move; what is
research-grade is anyone's ability to compute them, which the `research`
maturity and this cap both say out loud. A consumer that wants a promise
about accuracy will not find one here, or anywhere else in this document
(§16.8).

| key | type | req | meaning |
|---|---|---|---|
| `verb` | enum | REQUIRED | dominant motion: `fixed` `pan` `tilt` `roll` `zoom` `dolly` `track` `boom` (MPEG-7), plus `zoom_or_dolly` (scale change, parallax inconclusive) and `unknown` (tracking failed) |
| `verbs` | object verb → number 0–1 | SHOULD | MPEG-7 *FractionalPresence*: share of the span in which each verb is present; keys from the enum above |
| `direction` | `{pan, tilt, zoom}` | SHOULD | `pan`: `left`/`right`/null · `tilt`: `up`/`down`/null · `zoom`: `in`/`out`/null (camera-relative; `in` = subject grows) |
| `magnitude` | number ≥ 0 or null | SHOULD | for translations: mean speed in frame-widths per second; for scale changes: mean \|scale − 1\| per second |
| `editorial` | list of enum | SHOULD | the editor's words, zero or more: `static` `push` `pull` `whip` `drift` `handheld` `locked_off` `reveal` |
| `jitter` | number ≥ 0 or null | MAY | high-frequency residual of the motion path, frame-widths; handheld indicator |
| `parallax` | number 0–1 or null | MAY | depth-parallax evidence used for zoom/dolly; 0 = none observed |
| `roll_deg` | number | MAY | net roll over the span, degrees, cw positive |
| `samples` | integer ≥ 0 | REQUIRED | motion samples analysed |
| `confidence` | number | REQUIRED | heuristic score, capped as above |

Verb definitions (MPEG-7 §): `pan` rotation about the vertical axis; `tilt`
about the horizontal; `roll` about the optical axis; `zoom` focal-length
change; `dolly` translation along the optical axis; `track` translation
perpendicular to it, horizontal; `boom` translation vertical; `fixed` none
of the above above the noise floor. Editorial: `push`/`pull` a deliberate
slow dolly-or-zoom in/out; `whip` a pan faster than the span's frame
duration allows the eye to follow; `drift` slow unmotivated translation;
`handheld` jitter above the producer's threshold; `locked_off` fixed on a
support; `reveal` a move that brings a new subject into frame; `static`
synonym of `locked_off` used by the reference producer.

```json
{"span": {"frame_in": 0, "frame_out": 1199}, "verb": "fixed", "verbs": {"fixed": 1.0},
 "direction": {"pan": null, "tilt": null, "zoom": null}, "magnitude": 0.00005,
 "editorial": ["static"], "jitter": 0.00008, "parallax": 0.02, "samples": 16, "confidence": 0.75}
```

### C.8 `audio_usability` — Tier 2 · **frozen** · maturity `stable` · none

Whether the audio can carry a scene. Mixed: the levels are measured, the
classification is inferred. `confidence` REQUIRED on the entry, *heuristic
score*, describing `dominant`; `null` when the asset has no audio.

| key | type · unit · range | req | meaning |
|---|---|---|---|
| `dominant` | enum | REQUIRED | `speech` `tonal_or_music` `ambience` `silence`; null only when no audio stream |
| `rms_dbfs` | number ≤ 0 | REQUIRED | |
| `noise_floor_dbfs` | number ≤ 0 | REQUIRED | low-percentile level |
| `speech_ratio` | number 0–1 | REQUIRED | fraction of frames judged speech-like |
| `clipping_ratio` | number 0–1 | REQUIRED | fraction of samples at full scale |
| `snr_db_est` | number or null | REQUIRED | estimated speech-to-floor ratio |
| `intelligibility_proxy` | number 0–1 or null | REQUIRED | monotone proxy for dialogue intelligibility; **not** a P.835/DNSMOS score unless `dnsmos_ovrl` is also present |
| `dnsmos_sig` / `dnsmos_bak` / `dnsmos_ovrl` | number 1–5 | MAY | when a DNSMOS model ran |
| `wind` / `music_bed` / `room_tone` | boolean | MAY | |
| `frames` | integer ≥ 0 | REQUIRED | analysis frames |

### C.9 `embeddings` — reference · attachment form **frozen** by §7b.3 · facet form `proposed`

Vectors live in a Full-profile member (safetensors, 64-byte aligned, §4.4),
declared in the run's `attachments` (§7). The **attachment entry** carries
the descriptive convenience keys §7b.3 defines, and that form is stable:

| attachment key | type | meaning |
|---|---|---|
| `model` | string | model identifier |
| `model_version` | string | version / checkpoint / weights hash |
| `dim` | integer > 0 | vector length |
| `count` | integer ≥ 0 | rows |
| `dtype` | `F32` `F16` `I8` `U8` | `vectors` dtype (§7b.3) |
| `normalized` | `"l2"` \| `"none"` | row normalization |
| `scope` | string | `shot` \| `segment` \| `asset` \| producer-documented |
| `rows` | string | facet whose entries the rows correspond to |
| `spans` | `"frame"` \| `"ms"` | which span tensor the member carries (F1) |
| `sha256`, `size`, `media_type` | | §7b.2 fields |

The member's safetensors header names `vectors` `[count, dim]` first and, for
timed rows, `frame_spans` `[count, 2]` I64 — `frame_in`, `frame_out` per row,
so a row is self-locating at the media's rate without the manifest — with the
millisecond `spans` tensor as a backward-compatible fallback (§7b.3, F1).
The **facet form**, `facets.embeddings[]`, is proposed for the freeze: one
entry per row group, `{member, model, dim, dtype, per: shot|segment|asset,
normalized, rows: [{row, shot_idx?, span}]}`, and it MAY carry the common
`text` key (F2).

### C.10 `shot_size` — Tier 2 · `proposed` · VMH `videoShotTypes` slot + IPTC Scene codes

Framing scale of the primary subject. *Inference*: `confidence` REQUIRED,
*calibrated probability* expected of a classifier with temperature
scaling; producers SHOULD omit the entry rather than emit below their
calibration floor.

| key | type | req | meaning |
|---|---|---|---|
| `value` | ordered enum | REQUIRED | `ECU` extreme close-up (part of a face/object fills frame) · `CU` head and shoulders · `MCU` chest up · `MS` waist up · `MWS` knees up · `WS` full figure with ground and headroom · `EWS` figure small in environment |
| `subject_height_ratio` | number 0–1 | SHOULD | primary-subject bounding-box height / frame height — the measurement the class came from |
| `subject` | enum | MAY | `person` `object` `landscape` `none` |
| `iptc_scene_code` | enum | MAY | nearest IPTC Scene NewsCode for egress: `011800` close-up · `010100` headshot · `010200` half-length · `010300` full-length · `011000` general view · `011200` aerial view |
| `confidence` | number | REQUIRED | |

Egress note: IPTC VMH has a *slot* (`videoShotTypes`, CvTerm) but no
controlled vocabulary; the Scene codes are photo-derived (headshot ≈ CU,
half-length ≈ MS, full-length ≈ WS). Publish the mapping; do not claim IPTC
defines shot size.

### C.11 `composition` — Tier 2 · `proposed` · none

Framing geometry of the primary subject and the horizon. Measured from
pose keypoints and line detection: **no `confidence`**; `coverage` and a
`subject_detected` boolean instead.

| key | type · range | meaning |
|---|---|---|
| `subject_detected` | boolean | REQUIRED; when false the subject keys are absent |
| `headroom` | number 0–1 | distance from the subject's crown to the top edge / frame height |
| `leadroom` | number 0–1 | space ahead of the subject's facing direction / frame width |
| `rule_of_thirds` | number 0–1 | 1 − normalized distance from eye-centre to nearest thirds intersection |
| `symmetry` | number 0–1 | mirror-symmetry score of the luminance field |
| `horizon_tilt_deg` | number | detected horizon angle, cw positive; absent if no horizon |
| `subject_position` | enum `left` `center` `right` | horizontal third the subject centre falls in |

### C.12 `focus` — Tier 2 · `proposed` · none

| key | type · range | req | meaning |
|---|---|---|---|
| `sharpness` | number ≥ 0 | REQUIRED | subject-region Laplacian variance, normalized to frame area |
| `in_focus` | boolean | REQUIRED | inference; `confidence` REQUIRED alongside (heuristic) |
| `shallow_dof` | boolean | SHOULD | background/foreground sharpness ratio below threshold |
| `focal_feel` | enum `wide` `normal` `long` | MAY | perspective compression estimate |
| `anamorphic` | boolean | MAY | oval bokeh / horizontal flare signature |
| `flare` | boolean | MAY | |

### C.13 `continuity` — Tier 2 · `research` · none

The keys an editor needs to answer "what can this cut to". Nothing here is
emitted yet; the shape is fixed so producers converge. *Inference*:
`confidence` REQUIRED, heuristic.

| key | type · range | meaning |
|---|---|---|
| `screen_direction` | enum `screen_left` `screen_right` `center_facing` | primary subject's facing |
| `eyeline_yaw_deg` | number −180…180 | head yaw, screen-right positive |
| `eyeline_pitch_deg` | number −90…90 | |
| `staging_position` | enum `left` `center` `right` | |
| `key_light_side` | enum `left` `right` `front` `top` `back` | |
| `time_of_day` | enum `day` `night` `dawn_dusk` `interior` | |
| `weather` | enum `clear` `overcast` `rain` `snow` `fog` | exterior only |
| `location_hint` | string | free text, short |

The 180° rule (two shots are compatible when their yaws have opposite
sign) is a consumer's rule, not a field.

### C.14 `take` — Tier 2 · `proposed` · none

Slate and setup structure for scripted or commercial work.

| key | type | meaning |
|---|---|---|
| `scene` / `shot` / `take` | string | as written on the slate (`42B`, `A`, `3`) — strings, slates are not integers |
| `roll` | string | camera roll / card id |
| `slate_text` | string | full OCR of the slate |
| `slate_span` | span | where the slate is visible |
| `clap_frame` | integer | frame of the clapper contact, when detected |
| `setup_cluster` | string | opaque id shared by shots judged the same camera setup |
| `circle_take` | boolean | |
| `confidence` | number | REQUIRED — heuristic; OCR of handwriting is the weak link |

### C.15 `clearance` — Tier 2 · `proposed` · governed by §10.3

Review flags for rights and people. **Every entry is a flag that a human
should look here**, never a determination (§10.3 rules 1–5). `review_required`
MUST be `true`; the entry MUST NOT carry `accuracy`, `precision` or `recall`
keys; absence of a flag means "not flagged", never "clear".

| key | type | req | meaning |
|---|---|---|---|
| `flag` | enum | REQUIRED | `logo` `face` `minor` `artwork` `licensed_music` `signage` `text` |
| `review_required` | `true` | REQUIRED | constant |
| `bbox` | `[x, y, w, h]` numbers 0–1 | SHOULD for visual flags | normalized to frame |
| `label` | string | MAY | e.g. a brand name the detector proposes — a hint for the reviewer, not a finding |
| `note` | string | MAY | |
| `confidence` | number | REQUIRED | heuristic; producers SHOULD tune for recall |

Egress maps `face`/`minor` to VMH `modelReleaseStatus` and `logo`/
`artwork`/`signage` to `propertyReleaseStatus` as CV terms set by the
*reviewer*, never by the producer.

### C.16 `text_on_screen` — Tier 1 · `proposed` · VMH `dataOnScreen`

OCR results: `text` (REQUIRED), `bbox` normalized, `language` BCP-47,
`kind` ∈ `caption` `slate` `sign` `screen` `jersey` `other`, `confidence`
REQUIRED (heuristic).

### C.17 `persons` — Tier 1 · `proposed` · VMH `personsShown` / `personsHeard`

Unlabelled person clusters. `cluster` (REQUIRED, opaque id stable within
the run), `modality` ∈ `seen` `heard` `both`, `bbox` for `seen`, `speaker`
(the transcript's diarization label) for `heard`, `confidence` REQUIRED.
**Identities never appear in the machine layer**; a name attached by a
client is a label in `editorial_annotations`.

### C.18 `audio_events` — Tier 1 · `proposed` · none

Non-speech sound: `event` (string from the producer's taxonomy, e.g.
AudioSet display names), `confidence` REQUIRED. Indexes video that does not
talk.

---

### C.19 Summary

| facet | tier | shape | maturity | confidence | mirrors |
|---|---|---|---|---|---|
| `shots` | 1 | **frozen** | stable | heuristic (cut) | MPEG-7 MDS |
| `transcript` (signals) | 1 | **frozen** | stable | heuristic | VMH, MPEG-7 SpokenContent |
| `description` (signals) | 1 | proposed | proposed | optional | — |
| `usability` (signals) | 1 | **frozen** | stable | none (measured) | — |
| `exposure_color` | 2 | **frozen** | stable | none (measured) | — |
| `energy_curve` | 2 | **frozen** | stable | none (measured) | MPEG-7 MotionActivity |
| `camera_motion` | 2 | **frozen** | research | heuristic, capped | MPEG-7 CameraMotion |
| `audio_usability` | 2 | **frozen** | stable | heuristic | — |
| `embeddings` | ref | **frozen** (attachment, §7b.3) | proposed | — | — |
| `shot_size` | 2 | proposed | proposed | calibrated | VMH slot + IPTC Scene |
| `composition` | 2 | proposed | proposed | none (measured) | — |
| `focus` | 2 | proposed | proposed | heuristic | — |
| `continuity` | 2 | proposed | research | heuristic | — |
| `take` | 2 | proposed | proposed | heuristic | — |
| `clearance` | 2 | proposed | proposed | heuristic, review flag | VMH release status (egress) |
| `text_on_screen` | 1 | proposed | proposed | heuristic | VMH dataOnScreen |
| `persons` | 1 | proposed | proposed | heuristic | VMH personsShown/Heard |
| `audio_events` | 1 | proposed | proposed | heuristic | — |
