## 6A. Time model

Everything in a `.opi` that names a moment in the media — the start
timecode, every facet `span`, every label range — uses one model:

> **A position is an integer frame count at an exact rational rate.**
> Seconds and `HH:MM:SS:FF` labels are renderings of that count. They are
> never the value.

This chapter is normative for `media_binding.timecode` and for every object
named `span` anywhere under `machine_intelligence[*].facets` or
`editorial_annotations`. Test vectors: `vectors/time/`. Reference:
`openpicture/time.py`.

### 6A.1 Rate

```json
"rate": {"num": 24000, "den": 1001}
```

- `num` and `den` MUST be positive integers and MUST be in lowest terms
  (`gcd(num, den) == 1`). `{"num": 48000, "den": 2002}` is invalid, not
  merely unusual.
- Any positive rational is a legal rate. **Timecode semantics** (labels,
  drop-frame, the `HH:MM:SS:FF` renderings) are defined only for the rates
  in Table 6A-1. A rate outside the table MAY appear (a 1000/1 tick rate for
  variable-frame-rate phone media, for instance); positions at such a rate
  are frames, and no timecode field may be present.
- A rate MUST NOT be written as a float anywhere in the manifest. `23.976`
  is a label; the value is `24000/1001`. Writers that receive a float from
  a probe MUST snap it to the nearest table rate within 0.01 fps or refuse
  to assign timecode semantics.

**Table 6A-1 — rates with timecode semantics.**

| `num/den` | label | nominal (frames per labelled second) | drop-frame |
|---|---|---|---|
| 24000/1001 | 23.976 | 24 | not defined |
| 24/1 | 24 | 24 | not defined |
| 25/1 | 25 | 25 | not defined |
| 30000/1001 | 29.97 | 30 | 2 labels dropped per minute |
| 30/1 | 30 | 30 | not defined |
| 48000/1001 | 47.952 | 48 | not defined |
| 48/1 | 48 | 48 | not defined |
| 50/1 | 50 | 50 | not defined |
| 60000/1001 | 59.94 | 60 | 4 labels dropped per minute |
| 60/1 | 60 | 60 | not defined |
| 120000/1001 | 119.88 | 120 | 8 labels dropped per minute |
| 120/1 | 120 | 120 | not defined |

The *nominal* is `ceil(num/den)`: the count at which the FF field wraps.
At 23.976 there are 24 labels per labelled second and the labels run slow
against wall clock — that shortfall is what drop-frame exists to correct at
the NTSC 30 and 60 families, and it is exactly why SMPTE ST 12-1 §7.2 states
that no drop-frame counting applies to 24-frame counting. **23.976 DF does
not exist** and MUST be rejected.

### 6A.2 `media_binding.timecode`

```json
"timecode": {
  "start": "01:00:00:00",
  "recorded": "01:00:00:00",
  "rate": {"num": 24000, "den": 1001},
  "drop_frame": false,
  "label": "23.976"
}
```

| Key | Requirement |
|---|---|
| `rate` | REQUIRED when `timecode` is an object. §6A.1. |
| `drop_frame` | REQUIRED. Boolean. MUST be `false` unless `rate` is `30000/1001`, `60000/1001` or `120000/1001` (Table 6A-1, per SMPTE ST 12-1 §5.2.2 and ST 12-3). A validator MUST fail `true` at any other rate. |
| `start` | RECOMMENDED. The source timecode label of frame 0 of the media, rendered at `rate`/`drop_frame`. MUST parse as a label that exists (a dropped label is an error). Media with no recorded timecode MUST use `"00:00:00:00"`, so that every downstream offset reads as a record-frame offset — stated behaviour, not a missing field. |
| `recorded` | optional, informative. What the camera actually wrote, verbatim, or `null`. |
| `label` | optional, informative. MUST equal the canonical label of `rate` + `drop_frame` (`"29.97DF"`) when present. Readers MUST NOT parse it as the rate. |

`timecode` MUST be `null` (not absent, not `{}`) for media that has no
frame rate — a wildtrack WAV, a still. With `timecode: null`, every span in
the file is seconds-only (§6A.3).

### 6A.3 Positions and spans

A **span** is a half-open range of frames from the head of the media:

```json
"span": {
  "frame_in": 0,        REQUIRED when the media has a rate   — first frame, inclusive
  "frame_out": 101,     REQUIRED when the media has a rate   — exclusive
  "frames": 101,        optional  — MUST equal frame_out - frame_in
  "t_start_s": 0.0,     optional  — derived seconds
  "t_end_s": 4.2,       optional  — derived seconds
  "tc_in": "01:00:00:00",   optional — derived: timecode.start + frame_in
  "tc_out": "01:00:04:05"   optional — derived: timecode.start + frame_out
}
```

Rules:

1. **Frames are the position.** When the media has a rate, a writer MUST
   emit `frame_in` and `frame_out`. They are non-negative integers, and
   `frame_out > frame_in`: a span covers at least one frame. There is no
   zero-length span.
2. **Out is exclusive.** `frame_out - frame_in` is the duration in frames.
   Adjacent spans `[a, b)` and `[b, c)` butt without overlap. This is the
   convention FCPXML and CMX 3600 share.
3. **Seconds are derived.** `t_start_s = frame_in × den / num`;
   `t_end_s = frame_out × den / num`. Both MAY be present as JSON numbers.
   When present with frames they MUST agree: a validator compares them as
   exact fractions and fails a span whose seconds lie more than half a
   frame from the frame boundary they claim (`t_end_s` MAY lie anywhere in
   the last frame, because out points are ceiled — §6A.3.5).
4. **Timecode strings are derived.** `tc_in`/`tc_out` MUST render exactly
   as `timecode.start + frame_in` / `+ frame_out` at the media rate.
   Present without frames, or with a `start` unknown, they are invalid.
   Frames need no `start` to be meaningful; labels do.
5. **Deriving a span from sub-frame seconds.** A producer holding a moment
   as real seconds `(t0, t1)` MUST set `frame_in = floor(t0 × num/den)` and
   `frame_out = ceil(t1 × num/den)`, and if that yields an empty span, set
   `frame_out = frame_in + 1`. The exported range always *contains* the
   moment; it never trims a frame off either end. (Reference:
   `span_from_seconds`.)
6. **Media without a rate.** With `timecode: null`, a span MUST carry
   `t_start_s`/`t_end_s` only. `frame_*`, `frames`, `tc_*` MUST be absent.
7. **Seconds-only spans at a rated medium** are permitted for backward
   compatibility but NOT RECOMMENDED; a validator reports them as
   consistent. New writers emit frames.

### 6A.4 Shot spans

`facets.shots` is the one facet whose spans carry structure beyond the
rules above. In a run that emits `shots`:

- shots MUST be sorted by `frame_in`;
- shots MUST NOT overlap;
- shots SHOULD be contiguous — each `frame_in` equals the previous
  `frame_out` — and SHOULD cover `[0, duration_frames)`. A detector that
  finds no cuts emits exactly one shot covering the whole medium (a
  continuous take is one shot, not zero).

**A cut is one boundary, not two endpoints.** §6A.3.5 derives an isolated
span by flooring the in and ceiling the out, so that the span contains the
moment. Applied independently to both sides of the *same* cut it would
ceil the outgoing shot's `frame_out` and floor the incoming shot's
`frame_in` from one instant — and wherever the cut does not land exactly
on a frame those differ by one, which is the overlap the rule above
forbids. So a writer decomposing a medium MUST derive each interior
boundary **once** and give it to both neighbours, and MUST derive it by
**ceiling**: the frame the cut falls in belongs to the outgoing shot, and
the incoming shot starts at the first frame wholly after the cut. That is
what a cut means to an editor, and it is what C.1's worked example, the
span example in §6A.3 and `vectors/facets/valid-shots.json` all carry — a
cut at 4.2 s at 23.976 fps is frame 101 on both sides.

The outer edges are §6A.3.5 unchanged: the first shot's `frame_in` floors
and the last shot's `frame_out` ceils, so the decomposition still contains
the whole medium. Two cuts too close together to occupy distinct frames
are pushed apart, because §6A.3.1 admits no zero-length span. Facets that
are *not* a decomposition — transcript segments, camera-motion ranges,
labels — take §6A.3.5 per entry as written, and may overlap.

Other facets (transcript segments, camera-motion ranges, labels) MAY overlap
freely; nothing is implied between their spans.

### 6A.5 Drop-frame counting (SMPTE ST 12-1 §5.2.2)

Drop-frame is a *labelling* scheme, not a rate. 29.97 DF and 29.97 NDF run
at the same speed and differ only in which labels exist. A frame index is
the same integer under both.

At nominal 30, labels `;00` and `;01` are skipped at the start of every
minute **except** minutes 00, 10, 20, 30, 40 and 50. At nominal 60, labels
`;00`–`;03` are skipped; at nominal 120 (ST 12-3, "30 DF × 4"), `;00`–`;07`.
So after `00:00:59;29` comes `00:01:00;02`, but after `00:09:59;29` comes
`00:10:00;00`. Over one hour 108 labels are dropped at nominal 30 and the
label drift against wall clock is under 3 ms.

**Label → frame index**, with `N` = nominal, `D` = dropped per minute,
`M = hours×60 + minutes`:

```
if seconds == 0 and frames < D and M mod 10 != 0:  the label does not exist → error
index = ((hours×60 + minutes)×60 + seconds)×N + frames  −  D × (M − M div 10)
```

**Frame index → label**: with `per_minute = 60N − D` and
`per_ten = 600N − 9D`, let `tens, within = divmod(index, per_ten)`; add
`9·D·tens` to the index; if `within ≥ D`, add `D × ((within − D) div
per_minute)`; then split the adjusted count into `HH:MM:SS:FF` at nominal
`N`. Both directions are given as code in `openpicture/time.py` and are
exercised frame by frame in `vectors/time/timecode.json`.

Rendering: a drop-frame label SHOULD use `;` before the frame field and a
non-drop label `:`. Readers MUST accept either separator; the rate, not the
punctuation, says whether labels drop.

### 6A.6 Round trips to interchange formats

| Target | Position | Rate | Lossless? |
|---|---|---|---|
| **FCPXML** | rational seconds `frame×den/num` followed by `s`, reduced (`"3600s"`, `"101101/24000s"`) | `frameDuration="den/num s"` (`"1001/24000s"`), `tcFormat="DF"\|"NDF"` | **Yes.** Frame-aligned by construction, which is what FCP's "not on an edit frame boundary" check requires. |
| **OTIO** | `RationalTime{value: frames, rate: num/den}` | stored as a double | **No** — the rate is a double. Importers MUST snap `rate` to the nearest Table 6A-1 rational within 1e-6 and `round()` the value, never truncate. |
| **CMX 3600 EDL** | source timecode = `timecode.start + frame` rendered at the rate | none; `FCM: DROP FRAME` / `NON-DROP FRAME` is the only signal | **Yes** given the rate out of band. An EDL alone cannot say 24 from 25; a consumer MUST be told the rate. |
| **FCP7 XML (xmeml)** | integer frames at `<timebase>` | `<timebase>` = nominal, `<ntsc>TRUE</ntsc>` when `den == 1001` | **Yes.** |
| **MXF** | edit-unit count | `EditRate` rational | **Yes.** |

Writers of these formats MUST derive from frames, never from `t_start_s`.

### 6A.7 What a validator checks

For `media_binding.timecode`: object or `null`; `rate` reduced and positive;
`drop_frame` legal at the rate; `start` parses and is not a dropped label;
`label`, if present, names the rate. For every `span`: rules 1–7 of §6A.3,
reported per span with the path (`run[1].facets.shots[3]`) and a summary
row `spans: k/n consistent`. `vectors/time/consistency.json` enumerates the
cases a conforming validator MUST accept and MUST reject.

### 6A.8 Rationale

Floats drift. A 60-minute reel at 23.976 is 86 314 frames; representing
positions as float seconds and multiplying back by 23.976 lands off-by-one
often enough that a professional will never trust the file again. Rational
rate and integer frames make the arithmetic exact and make the FCPXML and
EDL round trips *identities* rather than approximations. Keeping seconds
and labels in the file as derived, checkable renderings costs a few bytes
and gives a human something to read and a validator something to catch.
