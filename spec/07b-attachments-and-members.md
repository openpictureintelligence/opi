## 7b. Attachments and members

A *member* is a file inside the archive other than `manifest.json`. An
*attachment* is a member's declaration in the manifest. Every member has
exactly one attachment; every attachment names exactly one member. The
manifest is the authority: a member the manifest does not declare is a
defect, not a bonus.

### 7b.1 Ownership

Attachments live on **runs** (§7). The run that produced a member declares
it under `machine_intelligence[i].attachments`, and that run's signature
covers the declaration. A member MUST be declared by **exactly one** run.
Two runs that want the same bytes declare two members.

The `editorial_annotations` block MUST NOT declare attachments: the human
layer is unsigned, and an unsigned declaration cannot vouch for bytes.

### 7b.2 The attachment object

```json
"attachments": {
  "embeddings/clip-vit-b32.safetensors": {
    "sha256":     "…64 hex…",
    "size":       133184,
    "media_type": "application/x-safetensors",
    "model":      "clip-vit-b32", "dim": 512, "count": 130,
    "dtype":      "F16", "normalized": "l2", "scope": "shot", "rows": "shots"
  },
  "keyframes/shot_0001_0000024.webp": {
    "sha256":     "…", "size": 7636, "media_type": "image/webp",
    "width": 512, "height": 288, "frame": 24, "t_s": 1.001, "shot_id": "…"
  }
}
```

Keys are member names exactly as they appear in the archive (§4.2).

| Key | Req. | Type | Meaning |
|---|---|---|---|
| `sha256` | MUST | string, 64 lower-case hex | SHA-256 of the member's **uncompressed** bytes |
| `size` | MUST | integer ≥ 0 | uncompressed length in bytes |
| `media_type` | MUST | string | IANA media type of the member's bytes; `application/x-safetensors` for embeddings, `image/webp` / `image/jpeg` for stills, `application/octet-stream` when nothing better applies |

Per-kind keys are defined in §7b.3–§7b.5. Readers MUST ignore attachment
keys they do not understand. Validators MUST check the three required keys
against the archive and MUST NOT reject unknown keys.

`sha256` and `size` are the identity of the bytes. A reader that has
verified a run's signature and then confirms a member's digest may trust
the member exactly as much as it trusts the run.

### 7b.3 Embeddings — `embeddings/<name>.safetensors`

**Purpose.** Dense vectors computed from the media by a model, one row per
unit of scope (a shot, a transcript segment, the whole asset), packed so a
consumer can memory-map the archive and use the matrix without copying.

**Name.** `embeddings/<name>.safetensors` where `<name>` matches
`[A-Za-z0-9._-]+` and SHOULD identify the model and version
(`clip-vit-b32-laion2b`, `emb-visual-hash-256-v1`). One file per
(model, scope). Two runs MUST NOT declare the same name.

**Container.** The member is STORED and 64-aligned (§4.4).

**Layout.** The Hugging Face *safetensors* format:

```
<u64 little-endian N> <N bytes UTF-8 JSON header> <byte buffer>
```

- The header is a JSON object. Every key except `__metadata__` names a
  tensor: `{"dtype": …, "shape": [...], "data_offsets": [begin, end]}`,
  offsets relative to the start of the byte buffer.
- `__metadata__` is a string → string object.
- Tensors MUST tile the buffer exactly: no gaps, no overlaps, no trailing
  bytes (the anti-polyglot rule).
- The header MUST be padded with ASCII spaces (0x20) so that `8 + N` is a
  multiple of 64. With the member itself 64-aligned in the archive, the
  buffer — and therefore the first tensor — is 64-aligned in the **file**.
- The header MUST be smaller than 100 000 000 bytes.

**Tensors.**

| Tensor | Req. | dtype | shape | Meaning |
|---|---|---|---|---|
| `vectors` | MUST, first in the buffer | `F16` (default), `F32`, `I8`, `U8` | `[count, dim]` | one embedding per row |
| `frame_spans` | SHOULD when rows are timed | `I64` | `[count, 2]` | `[frame_in, frame_out)` from the head of the media, per row; `-1` for untimed. Frame positions at the media's rational rate (§6A), so the row is exact. |
| `spans` | MAY (fallback) | `I64` | `[count, 2]` | `[start_ms, end_ms]` from the head of the media, per row; `-1` for untimed. Backward-compatible: a producer that holds sub-frame instants and no rate may write this alone. |
| `scale`, `zero_point` | MUST when `vectors` is `I8`/`U8` | `F32` | `[dim]` or `[1]` | affine dequantization: `x = scale · (q − zero_point)` |

**Frame spans are the position (F1).** Frames are what §6A makes
authoritative, so a timed row SHOULD carry `frame_spans` and a reader MUST
prefer it when both tensors are present. `spans` in milliseconds remains for
backward compatibility (a file written before this clarification is still
conformant) and for a producer whose medium has no rate. A reader joins a row
to the media at `frame_spans` when present; the rate to interpret them is the
`media_binding.timecode.rate` of the file that carries the member.

Rows are in **scope order**: when the attachment's `rows` key names a facet
(§7b.2, e.g. `"rows": "shots"`), row *i* corresponds to the *i*-th entry
of that facet array in the **same run**. When `rows` is absent, a timed
member MUST carry `frame_spans` or `spans`, which is then the only join key.

**Required `__metadata__` keys.**

| Key | Value |
|---|---|
| `opi.model` | model identifier, human-readable (`clip-vit-b32`) |
| `opi.model_version` | version / checkpoint / weights hash |
| `opi.dim` | decimal string equal to `shape[1]` of `vectors` |
| `opi.dtype` | equal to the dtype of `vectors` |
| `opi.normalized` | `"l2"` (every row has unit L2 norm) or `"none"` |
| `opi.scope` | `"shot"`, `"segment"`, `"asset"`, or another value the producer documents |

Producers MAY add further keys (`opi.quant`, `producer`, …). Readers MUST
ignore keys they do not know.

**Attachment keys** for an embeddings member: `model`, `model_version`,
`dim`, `count`, `dtype`, `normalized`, `scope`, `rows`, `spans`. When present
they MUST agree with the safetensors header; validators MUST fail a
disagreement. `spans` is `"frame"` when the member carries `frame_spans`,
`"ms"` when it carries only the millisecond fallback, and absent when the
member is untimed. They are conveniences so a reader can decide whether to
open the member without parsing it.

**Egress class.** An embedding is DERIVED data: it does not reproduce the
picture or the sound. (Inversion attacks exist for some models; a producer
that considers a model's vectors sensitive treats them as FRAMES-class.)

### 7b.4 Stills — `keyframes/<id>_<frame:07d>.<ext>`

**Purpose.** The picture a judgment was made on: proof for a reviewer, a
thumbnail for a browser, the input to a re-run without re-reading the
master.

**Egress class — read this first.** A still is a **copy of the picture**.
It is `FRAMES`-class egress, one step below the media itself, and MUST NOT
appear in a `.opi` unless the producer's declared egress permits it. A
still of a person is that person's image travelling in a metadata file.
Validators cannot see egress policy; producers can, and MUST enforce it.

**Name.** `keyframes/<id>_<frame>.webp` or `.jpg`, where `<id>` matches
`[A-Za-z0-9._-]+` and identifies the run, shot or facet entry the still
belongs to, and `<frame>` is the zero-based frame index in the media,
zero-padded to seven digits so a listing sorts in time order. Extension
MUST match `media_type`.

**Encoding.**

| | |
|---|---|
| `media_type` | `image/webp` (RECOMMENDED; lossy VP8 q≈80 or lossless VP8L) or `image/jpeg`. Nothing else. |
| Dimensions | long edge SHOULD be ≤ 512 px; MUST be ≤ 2048 px |
| Colour | sRGB; no embedded ICC profile (`ICCP` chunk / APP2) |
| Metadata | **stripped**: no `EXIF` or `XMP ` chunk (WebP), no APP1 (Exif/XMP) or APP13 (IPTC) segment (JPEG). Camera serials, GPS and timestamps do not belong in a proof still. |
| Animation | none (WebP `ANIM` chunk forbidden) |

**Attachment keys** for a still: `width`, `height` (MUST, integers, MUST
equal the image header), `frame` (integer ≥ 0, MUST equal the name),
`t_s` (float seconds from media head, SHOULD), `shot_id` or `entry_id`
(string, SHOULD — what the still is evidence for).

### 7b.5 Extensions — `extensions/<reverse.dns>/…`

Anything a producer wants to ship that this specification does not model:
a proprietary index, a model's raw output, a sidecar for another tool.

- `<reverse.dns>` is a lower-case reverse domain the writer controls.
  Segments below it follow §4.2.
- Extension members MUST be declared (§7b.2) like any member and carry
  `media_type`.
- Members named `*.bin` or `*.safetensors` under `extensions/` MUST follow
  §4.4 (STORE, 64-aligned).
- Readers MUST ignore extension members they do not understand; a reader
  MUST NOT fail a file because of an unfamiliar extension.
- An extension MUST NOT be required to interpret the manifest. If a facet
  needs a member to be meaningful, the member is an embeddings or keyframes
  member, or the facet belongs in a future version of this specification.

### 7b.6 Validator requirements for members

A conforming validator checks, for a Full file, at least:

1. §4.1 profile: methods ∈ {0, 8}; bits 0, 5, 6 clear; no `0x9901`; no
   archive comment; first bytes `PK\x03\x04`.
2. §4.2 names: charset, segments, length, ASCII case-insensitive
   uniqueness, no directory entries.
3. §4.3 top level: only `manifest.json` and reserved directories;
   `manifest.json` has the lowest local header offset.
4. §4.4 alignment: every `.bin` / `.safetensors` member STORED with
   `data_offset ≡ 0 (mod 64)`, computed from the local header.
5. §4.5 timestamps `1980-01-01 00:00:00` on every entry.
6. §4.6 no ZIP64: no `0x0001` extra, no sentinels, no ZIP64 EOCD, sizes
   under 2 GiB.
7. §4.7 / §7b.2: every member declared exactly once; declared members
   present; `sha256`, `size`, `media_type` present and `sha256`/`size`
   correct.
8. §7b.3 embeddings: parseable safetensors; header padded to 64; buffer
   tiled; `vectors` present, first, 2-D; required `__metadata__` keys
   present and consistent with `vectors`; attachment convenience keys
   consistent; `frame_spans` and `spans` shape `[count, 2]` when present;
   quantization tensors when `I8`/`U8`.
9. §7b.4 stills: header parses as WebP or JPEG; `media_type` and
   extension agree; `width`/`height` equal the header; no metadata chunks
   or segments; long edge ≤ 2048; `frame` equals the name.
10. §7b.5 extensions: nothing beyond 1–7.

Each check is reported by name so a producer can see which rule a file
broke. The reference implementation exposes these as
`openpicture.members.checks(path, manifest)`; `openpicture validate` runs
them.
