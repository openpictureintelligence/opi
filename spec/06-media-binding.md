## 6. `media_binding`

Describes the media the sidecar is about: which bytes, in which file(s), at
what rate. Every run signature covers this object (§9.2), so every
signature also asserts *which media* it describes — a run cannot be lifted
onto a different clip without breaking.

Table conventions are §5's. Every key in this chapter is written by the
producer and is under every run signature unless marked otherwise.

### 6.1 Keys

| Key | Type | Req. | Values / constraints | Default | Check |
|---|---|---|---|---|---|
| `files` | array | MUST | Non-empty. One entry per file that carries this asset (§6.2). Exactly one entry MUST be the `original` (§6.3). | — | `media_binding.files`, `media_binding.original` |
| `timecode` | object \| `null` | SHOULD | §6A.2. An object when the medium has a frame rate; `null` when it does not (a wildtrack WAV, a still). Absent is read as `null` but writers SHOULD write `null` explicitly. | `null` | `time: timecode*` |
| `duration_s` | number \| `null` | SHOULD | Seconds, `≥ 0`, as probed from the original. Informative once `duration_frames` is present. | `null` | schema |
| `duration_frames` | integer | MAY | Frames of the original at `timecode.rate`, `≥ 0`. MUST-if `timecode` is `null`: absent. When both `duration_frames` and `duration_s` are present they MUST agree within one frame: `abs(duration_frames × den/num − duration_s) < den/num`. | — | schema, `time: duration` |
| `asset_id` | string | MAY | Opaque identifier from the producer's catalog (the reference producer writes a UUIDv7). 1–128 characters. Readers MUST NOT use it to pair a sidecar with media; `sha256` is the binding. | — | schema |
| `shot_at` | string \| `null` | MAY | RFC 3339 `date-time` when the medium was recorded, as the camera or the operator asserted it. | `null` | schema |
| `camera` | string \| `null` | MAY | Camera or encoder identification as probed (`"ALEXA35"`, `"Lavf61.7.100"`). ≤ 256 characters. Informative. | `null` | schema |
| `ingested_at` | string \| `null` | MAY | RFC 3339 `date-time` when the producer first registered the medium. | `null` | schema |
| `provenance` | array | MAY | §6.4. Absent ≡ empty. | `[]` | schema |

### 6.2 `files[]` entries

| Key | Type | Req. | Values / constraints | Default | Check |
|---|---|---|---|---|---|
| `sha256` | string | MUST | **The binding.** 64 lowercase hex characters: the SHA-256 of the entire file. Uppercase is invalid. | — | `media_binding.files`, `media sha256` |
| `name` | string | MUST | The file's basename — no directory separators, 1–255 bytes UTF-8. A discovery hint (§2): where a sidecar sits beside media, the media's basename SHOULD equal the sidecar's two-dot prefix. A mismatch is not a validation failure (the media may have been renamed; the hash still binds); `openpicture doctor` reports it. | — | `media_binding.files`, schema |
| `role` | string | MAY | `original` — the camera master or delivered file the sidecar describes and sits beside; `proxy` — a lower-fidelity transcode for editing; `transcode` — a same-fidelity re-encode; `audio` — a separately recorded audio file bound to this asset (a lav or wildtrack recording); `other`. | `"original"` | `media_binding.original`, schema |
| `size` | integer | SHOULD | Bytes, `≥ 0`. A cheap pre-check before hashing. | — | schema |
| `path` | string | MAY | Where the writer saw the file, in the writer's own path syntax. **Informative and untrusted:** never portable, never a failure condition, never used for pairing. Writers SHOULD **omit it**; when a location is genuinely useful it SHOULD be relative to the sidecar's own directory, and it MUST NOT be an absolute path or name a user, volume or mount, because a `.opi` travels and the value is never trusted (F3). A mismatch is never a validation failure. | — | — |
| `xxh64be` | string | MAY | 16 lowercase hex characters: the XXH64 of the file, big-endian, as ASC MHL, Silverstack and Hedge record it. Lets a set's MHL cross-check the binding without re-hashing. `sha256` remains authoritative. | — | schema |
| `container` | string \| `null` | MAY | Container format as probed (`"mov,mp4,m4a,3gp,3g2,mj2"`). Informative. | `null` | schema |
| `video_codec` | string \| `null` | MAY | As probed (`"prores"`, `"h264"`). Informative. `null` for audio-only files. | `null` | schema |
| `audio_codec` | string \| `null` | MAY | As probed (`"pcm_s24le"`). Informative. `null` for silent files. | `null` | schema |
| `width`, `height` | integer \| `null` | MAY | Coded picture size in pixels, `≥ 1`. `null` for audio-only files. | `null` | schema |
| `fps` | number \| `null` | MAY | The probed frame rate as a float, `> 0`. **Informative only.** The rate is `timecode.rate` (§6A.1); readers MUST NOT derive positions from `fps`. | `null` | schema |

Any other key MAY be present and MUST be preserved and ignored.

### 6.3 Exactly one original

Every manifest MUST have exactly one `files[]` entry whose `role` is
`original` (explicitly, or by default because `role` is absent). That entry
is *the* medium: its `sha256` is the value `run_id` derivation uses (§7.1),
its `name` is the two-dot prefix the sidecar takes (§2), and it is the file
the media-presence check hashes.

Zero originals is invalid (there is nothing to bind to). Two originals is
invalid (a sidecar describes one medium; a multi-camera event is several
sidecars, one per medium, related through facets). Proxies, transcodes and
bound audio files MAY appear in any number.

*Why the original and not every file is the binding.* A proxy is a
different set of bytes with the same content; its hash is useful to detect
which proxy a reader is holding, but a sidecar's claims are about the
picture and sound the original carries. Binding every file would make the
signature depend on which proxies happened to exist when the file was
written.

### 6.4 `provenance[]` entries

How the original reached the producer. Every key is optional and
informative; the array exists so a reader can answer "where did this come
from" without the producer's database.

| Key | Type | Values / constraints |
|---|---|---|
| `session_id` | string | Opaque identifier of the ingest or offload session in the producer's catalog. |
| `original_path` | string | Where the medium was read from at ingest (a card, a drive, a volume). Untrusted, like `files[].path`; writers SHOULD omit it or reduce it to a portable label and MUST NOT write an absolute local path, a home directory or a user name (F3). |
| `source_label` | string | Human label of the source — a card or reel name (`"A001"`). |
| `checksum_verified_at` | string \| `null` | RFC 3339 `date-time` when the medium's hash was verified against its source, or `null` if it never was. |
| `note` | string \| `null` | Free text. |

Any other key MAY be present. Entries SHOULD be ordered oldest first.

### 6.5 Validation

A validator MUST fail a manifest when:

- `files` is missing, not an array, or empty;
- any entry lacks a string `name` or a 64-lowercase-hex `sha256`;
- the number of entries with role `original` (explicit or default) is not
  exactly one;
- `timecode` is present and neither an object nor `null`, or an object that
  fails §6A.2;
- `duration_frames` is present at `timecode: null`, or disagrees with
  `duration_s` by a frame or more.

A validator MUST check the original's `sha256` against the file on disk
when a file with that `name` exists in the directory it is told to look in
(by default, the sidecar's own). A mismatch is **invalid** (`media sha256`).
An absent file is **allowed** and reported (`media present`) — a sidecar
may travel without its media. Non-original entries are never hashed by the
validator.

A validator MUST NOT fail a manifest for any `path`, `original_path`,
`fps`, `camera` or other informative value, however unlikely it looks.
