# Open Picture Intelligence — `.opi` file format, version 0

<!-- GENERATED from spec/*.md by tools/build_spec.py — edit the chapters, not this file. -->

**Status:** Draft, version 0 (pre-freeze). **Date:** 2026-08-29.
**Reference implementation:** the `openpicture` Python package in this repository.
**Schema:** `schema/opi-0.schema.json`.

A `.opi` file is a per-clip sidecar that carries the *intelligence layer* —
shots, transcript, labels, embeddings, provenance — beside the media it
describes. It is bound to that media by checksum, signed per producer, and
owned by whoever owns the footage. It is readable with a text editor or
`unzip`, forgeable by nobody, and encrypted never.

This document is normative. Where it and the reference implementation
disagree, this document is wrong and MUST be fixed — the implementation is
what shipped. Behaviour that is *recommended but not yet decided* is marked
**[PENDING]** and uses SHOULD/MAY, never MUST. B14 (one physical form) and B15 (key log) were decided on 2026-08-29 and are normative in this revision.

---

## 1. Scope and terminology

This specification defines: the on-disk forms of a `.opi` file, the JSON
manifest it carries, how a manifest is bound to media, how producer runs are
signed and verified, and what conforming writers, readers and validators MUST
do. It does **not** define the meaning of intelligence facets (shot sizes,
transcript segments, embeddings); those are open in version 0 and will be
frozen separately.

The key words MUST, MUST NOT, REQUIRED, SHALL, SHOULD, SHOULD NOT, MAY are to
be interpreted as in RFC 2119 / RFC 8174.

| Term | Meaning |
|---|---|
| **media** | The file(s) the sidecar describes — a camera master, a wildtrack, a proxy. Never modified. |
| **sidecar** | The `.opi` file. |
| **manifest** | The JSON object at the heart of a sidecar. In Core it *is* the file; in Full it is the `manifest.json` member. |
| **profile** | `core` (plain JSON) or `full` (ZIP container). |
| **producer** | Software that computes intelligence about media — a shot detector, an ASR model. |
| **run** | One producer pass over one media asset: a self-contained, individually signed unit in `machine_intelligence`. |
| **machine layer** | `media_binding` + `machine_intelligence`. Signed. |
| **human layer** | `editorial_annotations`. Never signed; freely editable. |
| **member** | A file inside a Full container other than `manifest.json`. |
| **JCS** | RFC 8785 JSON Canonicalization Scheme. |

## 2. File identity and discovery

### 2.1 Naming

A writer MUST name the sidecar by appending `.opi` to the **complete** media
filename, in the same directory:

```
A001_C001.mov   →  A001_C001.mov.opi
A001_C001.wav   →  A001_C001.wav.opi
```

Rationale: a camera master and its separately recorded audio routinely share
a stem; the stem form would give them one sidecar between them. This is the
convention of Blackmagic `.sidecar` and ASC MHL.

A reader MUST also accept the stem form (`A001_C001.opi`) when no two-dot
file exists beside the media. A reconciliation tool SHOULD report both forms
being present as a duplicate and prefer the two-dot form.

### 2.2 Binding

The name is a discovery hint. The **binding** is `media_binding.files[].sha256`
(§6). A reader that locates a sidecar by name MUST confirm the checksum of any
media file it holds before trusting the sidecar's contents against it.

### 2.3 The media is never touched

A writer MUST NOT embed anything in, append to, or rewrite the media file.
A checksum manifest (MHL or otherwise) taken before the sidecar was written
MUST still verify afterwards.

## 3. Physical form, profiles and detection

**Decision B14 (2026-08-29): a `.opi` file is a ZIP.** One extension, one
physical form. The profile — **Core** or **Full** — is a property of the
container's *contents*, not of the bytes at offset 0.

### 3.1 Physical form

A `.opi` file MUST be a ZIP archive (§4) whose first member is
`manifest.json`. A **Core** file contains no other file member. A **Full**
file contains one or more additional members (§4.2).

A bare UTF-8 JSON manifest — the same bytes as `manifest.json`, written to
disk on its own — is the **internal form**: what a producer holds in memory,
what diffs in git, what a debugging session cats. It is not a `.opi`.
Readers SHOULD accept it (§3.2 step 3) and validators MUST report it as
non-canonical without failing it. Writers MUST NOT emit the internal form
as a deliverable.

### 3.2 Detection algorithm

Read the first 64 bytes as `head`.

1. If `head` begins with the four bytes `50 4B 03 04` (`PK\x03\x04`, a ZIP
   local file header) → **ZIP form**; the profile is decided by §3.3.
2. Otherwise, if `head` begins with the UTF-8 byte-order mark `EF BB BF`,
   drop it; strip leading bytes in the set `{0x20, 0x09, 0x0D, 0x0A}`.
3. If the next byte is `7B` (`{`) → **internal form**, read as Core.
4. Otherwise the file is **not a `.opi`**. In particular an empty ZIP
   (`PK\x05\x06`), a spanned-archive marker (`PK\x07\x08`), a ZIP with
   prepended data, or a JSON array are not `.opi` files.

### 3.3 Profile from contents

Let `files` be the set of member names that do not end in `/`. If
`files ⊆ {"manifest.json"}` the profile is **Core**; otherwise **Full**. A
ZIP without `manifest.json` is not a `.opi`.

### 3.4 Writer requirements

A writer MUST place the ZIP local header at byte 0 (no prepended data, no
self-extractor stub) and MUST write `manifest.json` as the first member.
Upgrading a file from Core to Full — adding members — MUST NOT change its
name: a clip described more completely is the same artifact.

### 3.5 Profile declaration

The manifest's `profile` key MUST equal the profile §3.3 derives from the
contents. A validator MUST fail a file whose declared profile disagrees
with its contents.

### 3.6 Why one form

One form means one UTI (`public.zip-archive` conformance), one media type
(`+zip`), one code path in every reader, and `unzip -p clip.mov.opi
manifest.json` working on every file ever written. The cost — no
text-editor path without `unzip -p` — is a one-line git `textconv`. Two
independent reviews of the alternative (dual-form with magic-number
sniffing) reached this conclusion; see the behavior spec §2.

## 4. Container

### 4.1 Base format

A `.opi` file is a ZIP archive as defined by the PKWARE APPNOTE, version
6.3.x, restricted to the **ISO/IEC 21320-1 profile**:

- compression methods **STORE (0)** and **DEFLATE (8)** only;
- **no encryption** of any kind (no traditional PKWARE encryption, no AES
  extra field 0x9901);
- **no multi-volume / spanned archives** (no `PK\x07\x08` spanning
  signature, one disk);
- **no ZIP-level digital signature** record (APPNOTE §4.3.13); signing is
  done inside the manifest (§9);
- **no patched data** (general purpose bit 5 clear);
- **no ZIP64** records anywhere (§4.6).

Archives MUST NOT carry an archive comment (EOCD comment length 0).

Writers SHOULD NOT set general purpose bit 3 (data descriptors): every
member's CRC-32 and sizes MUST be present in the local file header, so a
reader can locate and check `manifest.json` from the first 30 bytes plus
the name. Readers MUST tolerate bit 3 when they encounter it.

The first four bytes of the file MUST be `PK\x03\x04`: no prepended data,
no self-extractor stub. (§3 defines detection.)

### 4.2 Member names

A member name is a UTF-8 string that satisfies all of:

| Rule | |
|---|---|
| Segments | Split on `/`. Every segment MUST match `[A-Za-z0-9._-]+`. |
| Forbidden segments | `.` and `..`; an empty segment (leading `/`, trailing `/`, or `//`). |
| Length | Whole name ≤ 255 bytes; each segment ≤ 128 bytes. |
| Case | Two members whose names differ only in ASCII case are a conflict. Validators MUST fail the file. (Extraction onto a case-insensitive filesystem would otherwise silently drop one.) |
| Top level | Only `manifest.json` and the reserved directories in §4.3 MAY appear at the top level. |

Names are compared byte-for-byte for identity and case-folded (ASCII) for
the uniqueness rule. Directory entries (names ending `/`) MUST NOT be
written; readers MUST ignore them if present.

The rules are deliberately stricter than ZIP requires: a member name is
going to become a path on somebody's disk when the archive is unpacked, on
an operating system the writer never saw.

### 4.3 Reserved directories and members

| Path | Purpose | Chapter |
|---|---|---|
| `manifest.json` | REQUIRED. The manifest. MUST be the **first local file header** in the archive (lowest offset). | §5 |
| `embeddings/` | Vector payloads, one safetensors file per model. | §7b.3 |
| `keyframes/` | Still images the intelligence was judged on. | §7b.4 |
| `extensions/<reverse.dns>/` | Producer- or vendor-specific members. | §7b.5 |

Nothing else MAY appear at the top level. A member that belongs to no
reserved directory goes under `extensions/<reverse.dns>/`, where
`<reverse.dns>` is a domain the writer controls, lower-cased
(`com.example.tool`). Future versions of this specification may reserve
further top-level directories; readers MUST ignore directories they do not
recognise, and validators MUST fail unknown **top-level** entries at
version 0.

### 4.4 Compression and alignment

| Member kind | Method | Alignment |
|---|---|---|
| `manifest.json` | DEFLATE or STORE | none |
| `embeddings/*.safetensors`, `*.bin` (any directory) | **STORE** | data offset ≡ 0 (mod 64) |
| `keyframes/*` | STORE (already compressed) | none |
| `extensions/**` | STORE or DEFLATE; STORE + 64-alignment if the name ends `.bin` or `.safetensors` | as named |

**Alignment mechanism.** The data of an aligned member MUST begin at a file
offset that is a multiple of 64. This is achieved with a padding *extra
field* in the member's **local** file header (the mechanism USDZ uses):

```
extra = <u16 id = 0x4F50> <u16 size = n> <n × 0x00>
```

Given `H`, the offset of the 30-byte local file header, and `L`, the byte
length of the UTF-8 member name:

```
base = H + 30 + L
pad  = (−base) mod 64
if pad < 4: pad += 64          # a record needs its 4-byte header
extra_len   = pad              # 4-byte header + (pad − 4) zero bytes
data_offset = base + pad       # ≡ 0 (mod 64)
```

The padding record MAY be omitted when `base` is already a multiple of 64.
The padding record MUST NOT be the vehicle for any other data. Writers MAY
copy the record into the central directory entry; readers MUST NOT rely on
the central directory to compute data offsets.

**Reading an aligned member.** `data_offset = H + 30 + name_len +
extra_len`, with `name_len` and `extra_len` read from the **local** header.
Readers MUST skip extra-field records with ids they do not recognise and
MUST NOT assume the padding record is the only or the last record. A reader
that has the data offset and the uncompressed size from the local header
can `mmap` the archive and take a slice; that slice is the member.

### 4.5 Timestamps and reproducibility

Every local and central header MUST carry the DOS date/time
`1980-01-01 00:00:00` (`0x0021 0x0000`). Timestamps carry no information in
this format, and a fixed value makes two archives built from the same inputs
byte-identical and keeps a producer's clock out of the file. Readers MUST
ignore member timestamps.

Writers MUST order members `manifest.json` first, then the remaining
members in the order they are declared in the manifest (iterating runs in
array order and each run's `attachments` in key order). Two writers given
the same manifest and member bytes SHOULD therefore produce byte-identical
archives. The reference implementation does.

External file attributes and the "version made by" field carry no meaning
and readers MUST ignore them.

### 4.6 Size limits — no ZIP64

A `.opi` archive MUST NOT use ZIP64 in any form:

- no member with uncompressed or compressed size ≥ 2 147 483 648 bytes
  (2 GiB); writers MUST refuse to emit one;
- no extra-field record with id `0x0001` in any header;
- no `0xFFFFFFFF` / `0xFFFF` sentinel values in size, offset or count
  fields;
- no ZIP64 end-of-central-directory record or locator;
- fewer than 65 535 members; central directory and archive under 4 GiB.

*Why:* the alignment formula in §4.4 does not account for a ZIP64 record,
which common writers append *after* the padding record and would misalign
the data; and a reader that must handle ZIP64 is a materially larger
reader. The payload this format carries is measured in megabytes per hour
of footage (embeddings, stills); the 2 GiB member ceiling is three orders
of magnitude away from normal use. A producer with more than 2 GiB of
vectors for one clip splits them across members.

Validators MUST fail a file that violates any point above.

### 4.7 Declaration and integrity

Every member other than `manifest.json` MUST be declared in exactly one
run's `attachments` (§7b.2) with its SHA-256 and byte size. The ZIP
directory cannot be signed from inside the archive; the *manifest* carries
the digests and each run's signature covers its own declarations.

A validator MUST fail a Full file with an undeclared member, a declared but
absent member, a digest or size mismatch, or a member declared by more than
one run.

### 4.8 Zero-tooling access

`unzip -p clip.mov.opi manifest.json` MUST print the manifest. Any change to
this specification that breaks that command is a defect in the change.

A reader that wants only the manifest reads the first local header, its
name, and (STORE or DEFLATE) its data; it never needs the central
directory. A reader that wants members reads the end-of-central-directory
record and the central directory in one tail read (under 64 KiB for any
archive with fewer than a few hundred members), then one ranged read per
member.

## 5. Manifest envelope

The manifest is one JSON object (RFC 8259) stored as `manifest.json`
(§3, §4). This chapter defines every key of that object except the contents
of the three blocks it carries, which have their own chapters: `media_binding`
(§6), `machine_intelligence` (§7) and `editorial_annotations` (§8).

Conventions used by the key tables in §5, §6 and §8:

- **Req.** — `MUST` (required), `MUST-if` (conditional, condition stated),
  `SHOULD` (recommended), `MAY` (optional). A key marked `MAY` with a
  **default** is read as that default when absent.
- **Signed** — whether the key's value is covered by a run signature (§9.2).
  `runs` means every run signature covers it; `no` means it is informative
  and may change without touching any signature.
- **Writer** — who legitimately writes the key: `producer` (the software
  that generated a run), `human` (an editor, a MAM, the holder), `any`.
- **Check** — the reference validator row that enforces the rule
  (`openpicture validate`), or `schema` when the rule is enforced by
  `schema/opi-0.schema.json` and not (yet) by a validator row. A rule with
  neither is a writer requirement (§11) that a reader cannot observe.

### 5.1 Top-level keys

| Key | Type | Req. | Values / constraints | Default | Signed | Writer | Check |
|---|---|---|---|---|---|---|---|
| `opi` | integer | MUST, **first key** | `0` for files conforming to this document. `≥ 0`. Booleans are not integers. | — | no (§5.4) | producer | `has opi`, `opi version`, `opi is first key` |
| `profile` | string | MUST | `"core"` \| `"full"`. MUST equal the profile §3.3 derives from the members. | — | no | producer | `has profile`, `profile matches contents` |
| `media_binding` | object | MUST | §6. | — | runs | producer | `has media_binding`, §6 rows |
| `machine_intelligence` | array | MAY | Array of run objects (§7). MAY be empty. Absent ≡ empty. | `[]` | each run signs itself | producer | `runs: *` |
| `editorial_annotations` | object | MAY | §8. Absent ≡ `{}`. | `{}` | **never** | human | `editorial_annotations` |
| `generator` | string | SHOULD | Free text naming the writing software and version, e.g. `"latent 0.0.45"` or `"acme-indexer 2.1"`. ≤ 256 characters. | — | no | producer | schema |
| `generated_at` | string | SHOULD | RFC 3339 `date-time`; writers SHOULD use UTC (`Z` or `+00:00`). The moment the manifest was written — not when any run finished (that is `run.generated_at`, §7.2). | — | no | producer | schema |
| `$schema` | string | MAY | A URI. An informative hint for editors and linters; readers MUST NOT fetch it and MUST NOT fail on an unknown value. | — | no | any | schema |

**There is no top-level `signatures` array.** Signatures live on runs
(§7.2, §9.3). A top-level `signatures` key is an unknown key: preserved and
ignored like any other (§5.3). Readers MUST NOT interpret it as a signature.

### 5.2 Key order

`opi` MUST be the first key of the object, so a reader can dispatch on the
version before parsing anything else and a human opening the file sees what
it is on line 2. A validator MUST fail a manifest whose first key is not
`opi`.

The order of every other key is free. Writers SHOULD emit the top-level keys
in the order of the table above and SHOULD preserve the order of keys they
carry forward from an existing file (§8.3). Key order is never significant
to a reader and is not covered by signatures (§9.1 canonicalizes it away).

### 5.3 Version and unknown keys

`opi` is an integer major version. Readers MUST refuse a major they do not
implement. Within a major, readers MUST ignore keys they do not recognise,
at every level of the document, and writers rewriting a file MUST preserve
unknown keys verbatim in the blocks they do not own. Minor evolution is
additive and unversioned; that is what "ignore unknown keys" buys.

Consequently `additionalProperties` is `true` at every level of the envelope
schema. Known keys are typed and constrained; unknown keys are merely
carried.

### 5.4 What the envelope signs

Nothing in §5.1 except `media_binding` is under a signature. `opi`,
`profile`, `generator`, `generated_at` and `$schema` are informative
envelope facts a rewrite may change without invalidating any run. The
consequence a verifier must understand: a signed run proves *what a
producer said about which media*; it does not prove which software
assembled the surrounding file or when. That is by design — the same runs
must survive a regeneration by a different writer (§11).

### 5.5 Serialization

The bytes of `manifest.json` are: UTF-8; the JSON text produced by
`json.dumps(indent=2, ensure_ascii=False, allow_nan=False)` with insertion
key order preserved; followed by exactly one `\n`. Non-ASCII characters are
emitted literally, not escaped. `NaN` and infinities MUST NOT appear. No
byte-order mark.

A validator MUST confirm that a file's `manifest.json` re-serializes to
these exact bytes from its parsed value (`canonical form` row). This is what
makes the Core file and the Full file's manifest one document rather than
two.

### 5.6 Size

`manifest.json` MUST NOT exceed **16 MiB** (16 777 216 bytes) uncompressed.

*Rationale.* A timecoded transcript runs ~150 KB per hour of speech; 16 MiB
holds roughly a hundred hours of dense dialogue plus every other facet, and
a single clip is rarely more than an hour. Anything larger is bulk data —
per-frame series, dense embeddings — and belongs in a member (§7b), where
it is aligned, hashed and never parsed as text. The cap also bounds what a
reader must hold in memory to answer "what is this file about".

A validator MUST NOT parse a `manifest.json` whose uncompressed size exceeds
the cap; it MUST report the file as invalid (`manifest size`) without
loading the JSON. Writers SHOULD keep manifests under 1 MiB and MUST move
any array that would carry more than 65 536 entries into a member.

### 5.7 Numbers

Frame rates are rational `{"num": int, "den": int}` (§6A.1). Positions are
integer frames (§6A.3). Seconds and timecode strings MAY be present as
derived conveniences and MUST agree with the frames when they are. Floats
are permitted where the model calls for them (confidence, seconds,
measurements) and are canonicalized per RFC 8785 when signed; producers
SHOULD prefer integers in signed material so that third-party
canonicalizers stay trivial. Booleans are never accepted where a number is
specified.

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

## 7. `machine_intelligence` — runs

`machine_intelligence` is an array of **run** objects. A run is one producer
pass over one piece of media: one model, one version, one set of results.
Runs are independent of each other — adding, replacing or removing a run
never affects another run's signature — and each run is signed on its own
(§9.3).

*Rationale.* Intelligence is disposable and improves in passes. A shot
detector runs today; a transcription model runs next week; a better camera
motion classifier runs next year. Each pass is made by different software
with a different confidence profile and, often, a different key. Modelling
the file as a list of self-contained runs lets every pass be verified,
replaced and audited separately, and lets a consumer choose which producers
it trusts.

### 7.1 Run identity

Two runs are **the same run** when they have the same `producer`, the same
`model_version` and describe the same media. `run_id` is *derived* from that
identity, never invented:

```
run_id = lowercase_hex( SHA-256( JCS( {"model_version": <model_version>,
                                       "producer":      <producer>,
                                       "sha256":        <media sha256>} ) ) )[0:32]
```

- `JCS` is RFC 8785 (§9.1). The object has exactly those three keys; the
  canonical form sorts them and fixes the escaping, so every implementation
  hashes the same bytes.
- `<media sha256>` is `media_binding.files[]`'s `original` entry's `sha256`,
  lowercase (§6). A run therefore belongs to the *bytes* of the media, not to
  a path or an application-internal asset id.
- The result is truncated to **exactly 32 hexadecimal characters** (the first
  128 bits). No other length is a valid `run_id`.

Requirements:

- `run_id` is REQUIRED on every run and MUST equal the derivation above when
  the manifest carries an original `sha256`. A validator MUST recompute it and
  fail a run whose `run_id` differs.
- Two runs in one manifest MUST NOT share a `run_id`. (Because the id is
  derived, this is the same rule as: one run per `(producer, model_version)`.)
- A `run_id` MUST NOT change when a run is re-executed with the same identity
  (§7.4). It MUST change when either `producer` or `model_version` changes,
  which the derivation guarantees.

*Rationale.* A derived id makes "is this the same work?" answerable by
anyone holding the file, lets a reindex replace a run without a lookup
table, and removes the temptation to mint ids that mean something only to
one application.

### 7.2 Run fields

| Key | Type | Required | Meaning |
|---|---|---|---|
| `run_id` | string | **REQUIRED** | §7.1. 32 lowercase hex characters. |
| `producer` | string | **REQUIRED** | Who ran: `<tool>:<pass>[:<qualifier>…]`, e.g. `shots:scenedetect`, `asr:whisper`, `facet:camera_motion`. Lowercase ASCII letters, digits, `.`, `_`, `-`; segments separated by `:`; at least two segments; each segment 1–64 characters and starting with a letter or digit. Pattern: `^[a-z0-9][a-z0-9._-]{0,63}(:[a-z0-9][a-z0-9._-]{0,63})+$`. |
| `model_version` | string | **REQUIRED** | Opaque, 1–128 characters, names *exactly* what ran (weights, prompt version, tuning). Two runs whose outputs could differ MUST NOT share a `model_version`. |
| `facets` | object | **REQUIRED** | The intelligence, keyed by facet name (§7.5). MAY be empty. |
| `generator` | string | optional | The software that hosted the producer, e.g. `latent 0.0.45`. |
| `generated_at` | string | RECOMMENDED | When the run finished, RFC 3339 date-time. Writers SHOULD use UTC with a `Z` suffix. |
| `host` | object | optional | The **class** of machine the run executed on: `os` (`macos`, `linux`, `windows`, `other`), `arch` (`arm64`, `x86_64`, `other`), and optional `accelerator` (`cpu`, `cuda`, `metal`, `rocm`, `other`). All three are short lowercase tokens from those sets. MUST NOT carry a hostname, user name, IP or MAC address, serial number, or any other identifier of a particular machine or person (§13). |
| `models` | array of object | optional | The model artefacts this run consumed, each `{"name": …, "sha256": …}`: `name` 1–256 characters naming the weights file or checkpoint, `sha256` its 64-lowercase-hex digest. Names a *file*, not a story — prose about what ran belongs in `model_version`. |
| `supersedes` | string | optional | `run_id` of an earlier run by the same `producer` that this run replaces (§7.4). MUST NOT name the run itself. MAY name a run no longer present in the manifest. |
| `depends_on` | array of string | optional | `run_id`s of runs whose output this run consumed (a facet computed over another run's shots, embeddings taken at another run's boundaries). Every entry MUST be present in the manifest. |
| `egress` | string | optional | What left the producer's premises to make this run: `none` (fully local), `derived` (text, numbers, embeddings), `frames` (stills of the picture), `full_media` (the media itself). A consumer uses this to know what a run cost in exposure. |
| `confidence_scale` | string | optional | `unit` (default): confidences are floats in `[0, 1]`. `bp`: confidences are integers in `[0, 10000]` (basis points). Applies to every entry in the run. |
| `attachments` | object | optional | §7.6. Full profile only. |
| `signature` | object | optional | §9.3. |

Any other key MAY be present and MUST be preserved and ignored by readers.
`parent`, used by pre-release writers, is not defined; a reader MAY treat it
as `supersedes`.

*On `host` and `models`.* Both are evidence about a run, not part of its
identity: neither enters the §7.1 derivation, so adding either to a run
changes neither its `run_id` nor any other run. Both fall under the run
signature — §9.3 covers every key of the run object except `signature` — so
a producer that emits them attests to them. Neither is required, and a
reader MUST NOT treat absence as a defect; most producers will not know
their model hashes. They exist so that "what ran, on what" stays answerable
from the file alone years later, which `generator` and `model_version` only
approximate.

`host` is deliberately a class and never an instance. A sidecar travels, and
a hostname or user name inside a signed run cannot be edited out again
without breaking the signature that makes the run worth having (§13).

*Rationale for the two lineage relations.* "Replaces" and "was computed
from" are different facts. A run that replaces another makes the old one
non-current (§7.3); a run that depends on another is invalidated in spirit,
not in signature, when its input is replaced — a consumer may want to know
that. Folding both into one `parent` key made neither answerable.

### 7.3 Which run is current

A manifest MAY carry several runs by the same `producer` (an old and a new
`model_version`, kept for comparison). A reader that wants *one* answer per
producer MUST select it as follows:

1. Discard every run named by another run's `supersedes`.
2. Of the remaining runs sharing a `producer`, take the one with the latest
   `generated_at`.
3. If none carries `generated_at`, or several tie, take the one that appears
   last in the array.

Readers MUST NOT depend on array order for anything else.

### 7.4 Re-running

**Same identity → replace in place.** Running the same `producer` at the same
`model_version` on the same media again yields the same `run_id`. A writer
MUST replace the existing run object (new `facets`, new `generated_at`, new
`signature`) rather than append a second one. Other runs and their signatures
are untouched.

**New `model_version` → a new run.** A writer MUST append a new run with the
new `run_id` and SHOULD set `supersedes` to the run it replaces. The writer
MAY retain the superseded run (so a reader can diff the two) or MAY drop it;
either is conformant.

**Removing a run** never invalidates any other run. Signatures cover one run
and the media binding, nothing else (§9.3).

*Rationale.* A store that re-indexes owes the file a fresh run, not a
growing pile of stale ones; but a producer that keeps history wants to show
what changed. The rule allows both while keeping "current" unambiguous.

### 7.5 Facets

`facets` maps a **facet name** to an **array of entries**.

**Names.** Lowercase, dotted: `shots`, `transcript`, `camera_motion`,
`clearance.faces`. Pattern: `^(x-[a-z0-9]+\.)?[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$` — the vendor
segment is lowercase alphanumeric (`openpicture.runs.FACET_NAME_RE`).
Names without a prefix are reserved for this specification's vocabulary
(Appendix C); anything else MUST be namespaced `x-<vendor>.<name>`, e.g.
`x-acme.color_match`. A validator MUST NOT reject a facet name it does not
recognise; it MUST reject one that does not match the pattern.

**Entries.** Each entry is an object and:

- MUST carry a `confidence` key. Its value is a number in the run's
  `confidence_scale`, or `null` when no confidence was estimated — `null`
  is honest; omitting the key is not. Booleans are never confidences.

  `null` covers two cases, and a reader cannot tell them apart from the
  key alone. One: the producer made an inference but did not estimate how
  sure it is. Two: the value was **measured** by deterministic arithmetic
  over the pixels or samples — exposure statistics, an energy series,
  audio levels — so there is nothing to be unsure about. A measured entry
  SHOULD instead carry `coverage`, a number in [0, 1] saying how much of
  the span the numbers were actually computed from. Which facets are
  measured rather than inferred is vocabulary, so it is Appendix C's to
  say (C.0.1), not this chapter's.
- MAY carry `span` (§6A — the time model). An entry without a `span`
  describes the whole media.
- MAY carry `id`, a string unique within the run, so another run's
  `depends_on` results or a human annotation can point at it.
- MAY carry `evidence`, an object the producer uses to say *why* (a frame,
  a transcript line, a score breakdown). Unconstrained.
- MAY carry any other key; the per-facet vocabulary (Appendix C) says what
  they mean. Appendix C is normative for the facets B12 froze and a set of
  proposals for the rest; C.0.0 says which are which.

A validator MUST check the name pattern, the array shape and the
`confidence` rule. It MUST NOT check per-facet keys in version 0.

*Rationale.* Two things make the layer trustworthy to an editor: every
claim says how sure it is, and every claim can say why. Requiring the first
and making room for the second is the whole of the facet contract; the
vocabulary can evolve underneath it.

### 7.6 Attachments

`attachments` maps a member name (a path inside the Full container, §4)
to an attachment object. **§7b.2 defines that object** — `sha256`, `size`
and `media_type`, all three REQUIRED, plus the per-kind keys of §7b.3–§7b.5.
What this chapter adds is the ownership rule:

- A member MUST be declared by **exactly one** run — the run that produced
  it. Two runs MUST NOT declare the same member name, even with identical
  hashes; a validator MUST fail the second declaration
  (`attachments.single-owner`, §7b.6).
- The declaring run's signature therefore covers the member's content by
  hash (§9.3); the container's own directory is never signed.
- A Core-profile manifest MUST NOT declare attachments.
- Member names follow §4 (relative, no `..`, filesystem-safe characters).

*Rationale.* Ownership answers "who is responsible for these bytes" and
"whose signature covers them" with one rule. Allowing shared declarations
would make both answers ambiguous for no gain — a run that needs another
run's member names it in `depends_on`.

### 7.7 Ordering

A writer MUST order runs by `(producer, model_version)`, bytewise, so that
identical inputs produce identical manifests (§11). A reader MUST NOT infer
anything from order except the §7.3 tie-break.

### 7.8 Conformance summary

| Requirement | Level |
|---|---|
| `run_id`, `producer`, `model_version`, `facets` present | MUST |
| `run_id` equals the §7.1 derivation when the media sha256 is known | MUST |
| `run_id` unique within the manifest | MUST |
| `producer` matches the pattern; `model_version` 1–128 chars | MUST |
| `generated_at` RFC 3339 when present | MUST |
| `supersedes` never names the run itself; `depends_on` entries present | MUST |
| `egress` and `confidence_scale` from their enumerations | MUST |
| `host`, when present, an object whose `os`/`arch`/`accelerator` come from their enumerations and name no instance | MUST |
| `models`, when present, an array of `{name, sha256}` with 64-lowercase-hex digests | MUST |
| facet names match the pattern; entries are objects with a valid `confidence` | MUST |
| a member declared by no more than one run (§7.6, `attachments.single-owner`); §7b.6 requires no fewer | MUST |
| runs ordered by `(producer, model_version)` | MUST (writer) |
| same identity replaces in place; new `model_version` appends | MUST (writer) |
| `supersedes` set on the replacing run | SHOULD |
| `generated_at` present | SHOULD |
| `host` and `models` present when the producer can determine them | SHOULD |

Reference implementation: `openpicture/runs.py` (`run_id`, `new_run`,
`current_runs`, `lineage`, `checks`). Test vectors: `vectors/runs/`.

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

## 8. `editorial_annotations` — the human layer

A JSON object. **Never signed.** It belongs to whoever holds the file — an
editor, a MAM, the client. Readers MUST NOT treat a change here as
tampering, and a run signature MUST NOT be computed over any part of it
(§9.2).

Table conventions are §5's. Nothing in this chapter is under a signature.

### 8.1 Keys

| Key | Type | Req. | Values / constraints | Writer | Check |
|---|---|---|---|---|---|
| `labels` | array | MAY | §8.2. **Reserved:** owned by the producer that maintains the labels (the reference producer writes its live labels here and carries nothing else forward from its own store). Absent ≡ empty. | producer | `editorial_annotations`, schema |
| `notes` | string | MAY | Free text about the medium as a whole, from whoever holds the file. 1–4096 characters. Not a vocabulary term, never machine-read: a validator checks its type and nothing else. | human | schema |
| *any other key* | any JSON | MAY | The holder's. A rating, notes, tags, a MAM's field map, a colourist's LUT name — anything. Writers regenerating the file MUST carry these forward verbatim (§8.3). | human | — |

The object as a whole MUST be an object; an array or scalar is invalid
(`editorial_annotations`). An empty object is the normal state of a freshly
produced file.

Keys beginning with `opi.` are reserved for future versions of this
specification and MUST NOT be used by holders.

### 8.2 `labels[]` entries

A label is one human judgement about the medium or a span of it.

| Key | Type | Req. | Values / constraints | Default |
|---|---|---|---|---|
| `name` | string | MUST | The vocabulary term: `"select"`, `"scene"`, `"take"`, `"note"`. 1–128 characters. Vocabularies are the holder's — this document defines none. | — |
| `value` | string \| number \| boolean \| `null` | MUST | The judgement. `null` means the label is a **bare tag** — a `select` with nothing further said. It is not a retraction; §8.4 retracts by absence. | — |
| `created_by` | string | MUST | Who made it — a person, a tool, or a read-back provenance such as `"opi:<signer>"` (§8.4). 1–256 characters. | — |
| `created_at` | string | SHOULD | RFC 3339 `date-time`. | — |
| `by` | string | MAY | The human who made the judgement, **self-declared**: an opaque account identifier or a chosen handle, 1–256 characters. Distinct from `created_by`, which says where the *record* came from — `by` says who formed the opinion. Never a proof (§8.4, §13). | — |
| `at` | string | MAY | RFC 3339 `date-time`: when the human made the judgement, which MAY predate `created_at` (when the record was written). | — |
| `notes` | string | MAY | Free text about this label. 1–4096 characters. | — |
| `span` | object | MAY | §6A.3. The part of the medium the label applies to. Absent means the whole medium. | whole medium |
| `id` | string | MAY | Stable identifier for this label, 1–128 characters. A writer that emits `id` MUST keep it the same across rewrites for as long as the label is the same label, so that a later import recognises it (§8.4). Opaque — readers MUST NOT parse it, and MUST NOT assume it means anything outside the file that carries it. | — |

Any other key MAY be present and MUST be preserved. Two labels with the same
`name` and `value` over the same `span` are one label; writers SHOULD not
duplicate them, readers MUST tolerate duplicates.

**Identity here is a claim, not a proof.** `by` is written by whoever holds
the file, is covered by no signature, and can be changed by anyone who can
write the file. A reader MUST NOT derive `by` from a run's signer, and MUST
NOT present a label as attributable because the file's runs are signed — the
human layer sits outside every signature by construction (§9.2). Writers
SHOULD fill `by` from an opaque account identifier rather than a legal name,
and MUST NOT fill it from an operating-system user name or an email address
(§13). `openpicture annotate --anonymous` strips `by` and `at` from every
label before a file travels; it does not strip `created_by`, which is record
provenance rather than personal identity and which §8.2 requires.

A tool recording an imported or machine-produced judgement fills `created_by`
(where the record came from) and MUST NOT fill `by`: a machine, a run or a
signature is not a person. On read-back it therefore MUST NOT copy a run's
`signature.signer` into `by`, and MUST NOT otherwise turn a machine signer
into a human attribution (F5, §8.4).

### 8.3 Preservation on rewrite

A writer regenerating a sidecar that already exists at the target MUST read
the existing `editorial_annotations` first and carry forward every key it
does not own, verbatim — including keys it does not understand. The
reference writer owns `labels` only. Without this rule every regeneration
silently destroys the editor's work, which is the failure the human layer
exists to prevent.

A writer MUST NOT reorder, reformat or "clean up" carried-forward values.

A producer that reads the block back into its own store owns `labels` only. It
MUST NOT project any other clause into the store as a label: in particular it
MUST NOT rewrite a non-`labels` key as an `opi.<key>` label, nor write such a
key twice (once as itself and once as a label). Every other clause belongs to
the holder — carry it forward verbatim (§8.4 is about `labels` alone). This is
F4: the human layer's non-label keys are data, not a vocabulary to absorb.

### 8.4 Read-back

Decided 2026-08-29 (B23), refined the same day with the `id` matching rule
below. A producer that maintains its own store MAY read
`editorial_annotations` back. If it does, it MUST:

- record each imported value with provenance naming the file or the signer
  (the reference producer uses `created_by = "opi:<signer|filename>"`);
- never destroy what it already holds: a value that conflicts with one in
  the store is retained **alongside** it, both timestamped. A store MAY
  decide which of the two is *live*; it MUST keep the other;
- never derive a label's `by` from a run signature, and never present an
  imported label as attributable (§8.2);
- never import anything from `machine_intelligence` — the machine layer is
  regenerated by re-running producers, not copied.

**Matching on `id`.** A producer that wrote `id` on the labels it emitted
MAY use it to converge on read-back rather than accumulate duplicates. If it
does, these are the four cases:

| In the file | In the store | Import as |
|---|---|---|
| `id` present, value unchanged | same `id` | nothing |
| `id` present, value changed | same `id` | a new label that supersedes the store's; the store's becomes non-live |
| `id` absent | — | a new label, deduplicated on `(name, value, span)` |
| an `id` this producer wrote | **absent from the file** | a **retraction**: the store's label becomes non-live |

Retraction is by **absence**. It is deliberately not `value: null`, because
`null` already means a bare tag (§8.2) and a file full of bare tags must not
read as a file full of retractions. A store records a retraction as a
superseding event carrying no value, so "was this ever asserted" stays
answerable; the next file that producer writes carries only live labels, so
the file shows one value per `id` while the store keeps the history.

Two files that disagree are imported in arrival order: the last read is
live, and both are in the store's history.

None of this is required *of a file*. It is what a producer that keeps a
store owes its own users, and it is the reason `id` is worth writing at all.

The file itself guarantees only that a rewrite will not lose the human
layer (§8.3); read-back is the producer's contract with its own store.

### 8.5 Size

`editorial_annotations` counts toward the manifest cap (§5.6). It SHOULD
stay under 1 MiB. It is a place for judgements, not for bulk data: a holder
who wants to store a transcript edit or a large structured document beside
the medium SHOULD use an `extensions/` member (§7b) and reference it from
here by name.

### 8.6 Validation

A validator MUST fail a manifest whose `editorial_annotations` is present
and not an object. It MUST NOT fail a manifest for any content of that
object other than a malformed `labels` array (schema: entries lacking
`name`, `value` or `created_by`). The optional keys of §8.2 — `id`, `by`,
`at`, `notes` — are checked for type and length when present and never for
presence: a validator MUST NOT fail a label for lacking them, and MUST NOT
fail one because it does not recognise a `by`, there being no registry of
people. It MUST NOT compare the human layer to anything signed. `openpicture annotate` is the reference tool for editing
this block; it refuses to write if anything outside `editorial_annotations`
would change.

## 9. Canonicalization and signatures

### 9.1 Canonicalization

Signed bytes are the **RFC 8785 (JCS)** canonical form of a JSON value:
object keys sorted by UTF-16 code unit, no insignificant whitespace,
ECMAScript number formatting, minimal string escaping, UTF-8.

`json.dumps(sort_keys=True, separators=(",", ":"))` is **not** JCS — it
sorts by code point, formats `1e+16` where JCS writes
`10000000000000000`, and emits `1.0` where JCS writes `1`. Implementers MUST
use a real RFC 8785 canonicalizer. The reference implementation's
`openpicture/jcs.py` is one, tested against the RFC's Appendix B vectors.

### 9.2 Payload

The payload of a run signature is the JCS canonicalization of:

```json
{"media_binding": <manifest.media_binding>, "run": <the run object with its "signature" key removed>}
```

— exactly two keys, in canonical (sorted) order, with `media_binding` taken
from the manifest as-is (or `null` if absent — though signing without a
binding is an error for writers). Nothing else in the manifest is covered:
not the envelope, not other runs, not `editorial_annotations`.

Consequences: a run signature asserts *this intelligence, about this media*.
Appending a second run does not disturb the first. Editing the human layer
does not disturb anything.

### 9.3 Signature entry

Placed at `run.signature`:

| Key | Type | Value |
|---|---|---|
| `role` | string | Default `"machine_producer"`. Informative. |
| `signer` | string | Who signed — a URN or similar stable identifier. |
| `algorithm` | string | MUST be `"Ed25519"`. |
| `public_key` | string | 64 lowercase hex characters: the raw 32-byte Ed25519 public key (RFC 8032). |
| `signed_at` | string | RFC 3339 timestamp. Informative. |
| `signature` | string | Standard base64 (with padding) of the raw 64-byte Ed25519 signature over the §9.2 payload. |

Keys are raw RFC 8032 encodings — no PEM, no X.509. **The public key hex is
the key id**; there is no separate `key_id` field.

**Key policy (decision B15, 2026-08-29): an append-only key log.** A
producer publishes every public key it has ever signed with, each with the
signer URN, the date added and an optional note, and **never withdraws
one** — a key that is retired is marked, not removed, so every file it
signed stays verifiable forever. Verifiers that hold a producer's log
report a run as `trusted` (key present) or `unknown-signer` (absent) in
addition to `valid`/`invalid`; a valid signature by an unknown key is still
a valid signature. Compromise is handled by marking the key and re-signing
affected files with a new one; it is never handled by deleting history. The
reference implementation's `keys.py` is the log format (JSON Lines, one key
per line).

### 9.4 Verification

For each run `i` in `machine_intelligence`:

1. If the run is not an object → `invalid`.
2. If `signature` is absent → `unsigned`.
3. If `signature` is not an object, or `algorithm ≠ "Ed25519"`, or
   `public_key` is not valid hex, or `signature` is not valid base64 →
   `invalid` with a reason.
4. Compute the §9.2 payload. Verify with Ed25519 (RFC 8032 §5.1.7; the
   reference implementation uses the RFC's own reference algorithm and
   rejects `s ≥ L`). Success → `valid`; failure → `invalid`.

File-level status:

| Status | Condition |
|---|---|
| `signed` | every run `valid` |
| `partial` | at least one `valid`, none `invalid`, some `unsigned` |
| `unsigned` | no run `valid`, none `invalid` (including no runs at all) |
| `invalid` | any run `invalid` |

A verifier MUST report per run — which run, which signer, which reason —
and MUST NOT collapse `partial` into `signed`. **Unsigned is valid**: a
file with no signatures is honest; a file with a bad one is not.

### 9.5 Re-signing

Signing a run replaces that run's `signature`. There is one signer per run
— the producer that made it. Another producer's work is another run.

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

## 11. Writer requirements

- MUST write atomically: temp file in the target directory, `fsync`,
  atomic rename. Never patch in place.
- MUST NOT modify the media (§2.3).
- MUST name per §2.1 unless the caller supplies an explicit destination.
- MUST preserve the human layer on rewrite (§8.3).
- SHOULD be deterministic (§4.5, §7.7): same inputs → same bytes apart from
  `generated_at` and `signed_at`.
- SHOULD emit one run per producer pass (§7.2) and sign each run it is
  entitled to sign.
- MUST NOT emit members over 2 GiB (§4.6).
- Writing a sidecar is an *egress* of derived data. Producers operating
  under a data-egress policy MUST apply that policy at the write, not at
  the in-memory build.
- MUST NOT fill a label's `by` from an operating-system user name or an
  email address, and MUST NOT derive it from any signature, signer or machine
  run (§8.2, §8.4, §13). A writer that offers identity SHOULD also offer a way
  to remove it (`openpicture annotate --anonymous`).
- SHOULD omit `media_binding.files[].path` and `provenance[].original_path`;
  when a location is written it SHOULD be relative and MUST NOT be an absolute
  path, a home directory or a user name — a `.opi` travels and the value is
  never trusted (§6.2, §6.4, F3).
- MUST keep `host` a class and never an instance when it writes one: no
  hostname, user name, address or serial number goes under a signature
  (§7.2, §13).
- SHOULD keep a label's `id` stable across rewrites for as long as the label
  means the same thing, and SHOULD write only live labels — a label the
  writer has retracted is omitted, not written with a `null` value (§8.4).

The consolidated list a writer conforms to, cross-referenced by rule, is the
Producer class in §16.4.

## 12. Reader requirements

A conforming reader:

1. detects the profile by bytes (§3.1), never by extension;
2. refuses an `opi` major it does not implement; ignores unknown keys
   otherwise (§5.3);
3. reads only `manifest.json` when it wants Core semantics from a Full file;
4. confirms `sha256` before trusting a sidecar against media it holds (§2.2);
5. treats `editorial_annotations` as mutable and unsigned (§8);
6. reports signature status per run and never collapses `partial` into
   `signed` (§9.4);
7. computes `.bin` offsets from the local header and tolerates unknown
   extra-field records (§4.4);
8. treats `files[].path` as untrusted text (§13);
9. treats `by` as a self-declared claim: never corroborated by a run
   signature, never rendered as though it were (§8.2, §13).

**Readers that keep a store.** A reader that ingests sidecars into its own
index will meet the same `run_id` twice with different content. It SHOULD
resolve that without asking a human, and SHOULD resolve it deterministically
— the reference producer takes a valid signature over an unsigned run, then
a more trusted key over a less trusted one, then the later `generated_at`,
and on a dead tie keeps what it already holds and reports the collision. The
loser SHOULD be retained as history rather than as a second current run, so
that "did we ever see a different answer" stays answerable while everything
downstream sees one (§7.3, §8.4). None of this is required by the file
format; it is stated here because every store hits it, and a store that
resolves it differently on each run is worse than one that resolves it
wrongly but predictably.

The consolidated list, cross-referenced by rule and including the time,
run-selection and sensitive-facet clauses, is the Reader class in §16.2.

## 13. Security considerations

- **No confidentiality.** A `.opi` is readable by anyone who can read the
  file. Do not put secrets in it. Encryption is deliberately out of scope;
  it would defeat zero-tooling ingestion.
- **Signatures assert origin and integrity of a run, not truth.** A valid
  signature means the named key signed these facets about this media. It
  says nothing about whether the model was right.
- **Key custody is out of scope; key history is not.** Loss or compromise
  of a producer key is handled by the append-only key log (§9.3): mark,
  re-sign, never delete. A verifier with the log can tell a legitimate
  historical signature from one made by a key added after the fact.
- **`files[].path`, `provenance`, `generator` and all human-layer text are
  untrusted input.** Never use `path` to open files without the same
  checks you would apply to any user-supplied path.
- **Unpacking.** Implementations that extract Full containers MUST reject
  member names that escape the target directory (`../`, absolute paths).
- **Resource limits.** Readers SHOULD cap the manifest size they will parse
  and the member sizes they will hash; producers SHOULD move very long
  arrays into members rather than the manifest. Members over 2 GiB are
  forbidden (§4.3).
- **Downgrade.** A reader MUST NOT treat a missing signature as equivalent
  to a valid one. `unsigned` is a distinct, visible status.
- **Human layer.** Because it is unsigned, nothing in it can be attributed.
  Systems that need attributable human annotations should record them as a
  signed run by a human-operated producer key, not in `editorial_annotations`.
- **`host` is a fingerprint if you let it be.** The `host` object (§7.2)
  names a class of machine — os, arch, accelerator — and MUST NOT name an
  instance. A hostname, user name, IP or serial number written there is
  under the run signature and so cannot be removed later without destroying
  the signature: the leak is permanent for the life of the run. Producers
  MUST populate `host` from the platform's coarse identifiers only, and
  validators SHOULD reject values outside the enumerations.
- **Human-layer identity is a claim, never a proof.** `by` (§8.2) is
  self-declared text that anyone holding the file can write or change, and
  a reader MUST NOT derive it from — or corroborate it with — any run
  signature; the two layers are unrelated by construction (§9.2). Tools
  SHOULD default to an opaque account identifier rather than a legal name,
  MUST NOT populate `by` from an OS user name or an email address, and
  SHOULD offer a way to strip `by` and `at` before a file travels
  (`openpicture annotate --anonymous`).

## 14. Media types and UTI (proposed, unregistered)

| | Value |
|---|---|
| `.opi` file (Core and Full — both are ZIP, §3) | `application/vnd.openpicture.opi+zip` (RFC 6839 §3.6 structured suffix) |
| Bare manifest (internal form only, never a `.opi` file) | `application/vnd.openpicture.opi+json` |
| Extension | `.opi` |
| macOS UTI | `org.openpicture.opi`, conforming to `public.zip-archive` |
| Intended canonical reference URL | `https://openpictureintelligence.org/spec/` |

**None of these are registered.** The schema freeze that gated the IANA
vendor-tree registration closed on 2026-08-29 (B12, Appendix C); the filing
now waits on its own reference URL. `https://openpictureintelligence.org/spec/`
is the *intended* canonical reference URL for that filing, and a filing is
not made until that path actually serves this document — a registration
naming a URL that 404s is worse than no registration. Until a registration
is accepted, nothing about the format, this document or the documentation
site may imply that IANA has registered `.opi`. Because a `.opi` file is always a
ZIP (§3), one UTI conforming to `public.zip-archive` describes every file;
see §3.4 for the history of the two-form alternative.

## 15. Versioning and change policy

- `opi` is the only version number in the file. It changes only for
  incompatible changes: a required key removed or retyped, a signature
  payload change, a container rule change.
- Additive changes (new optional keys, new facets, new members) do not bump
  the version. Readers ignore what they do not know.
- `0` means *pre-freeze*: additive changes are expected and even the rules
  above may change with notice. `1` will be the first frozen version.
- The reference implementation's package version (`openpicture.__version__`)
  is independent of the format version.

---

## 16. Conformance

This chapter says what an implementation may claim, and what it must do to
claim it. Three classes exist. An implementation may claim any subset, and
may qualify a claim by profile (§3.3). Every MUST below is a cross-reference
to the rule that defines it; this chapter adds no new rules, it collects
them.

### 16.1 Classes

| Class | Claims to | Proven by |
|---|---|---|
| **Reader** | open a `.opi` and expose its contents correctly | the requirements in §16.2 and the reader clauses of the vector suite (§16.5) |
| **Validator** | decide whether a `.opi` conforms to this specification, and say why | every vector in the suite: valid files accepted, must-fail files rejected for the stated reason |
| **Producer** | write `.opi` files that a conforming validator accepts | the writer requirements in §16.4; its output validated by the reference validator or any conforming validator |

A **Reader** is not required to verify signatures cryptographically, but it
MUST report what it did not verify. A **Validator** is a Reader plus the
checks in §16.3. A **Producer** is not required to be a Reader, but a
Producer that rewrites existing files (§8.3) necessarily reads them.

### 16.2 Reader

A conforming Reader MUST:

| # | Requirement | Rule |
|---|---|---|
| R1 | Detect the physical form from the first bytes, never from the extension; accept the bare-JSON internal form only as documented | §3.2, §3.4 |
| R2 | Read `manifest.json` and derive the profile from the member list (Core = `manifest.json` alone), not from the `profile` key alone | §3.3, §3.5 |
| R3 | Refuse a file whose `opi` major it does not implement; otherwise ignore unknown top-level keys, unknown run keys, unknown facets and — in future majors — unknown reserved directories | §5.3, §4.3 |
| R4 | Bind a sidecar to media by `media_binding.files[].sha256`, never by `path` or by filename alone; treat `path` as untrusted text | §2.2, §6, §13 |
| R5 | Treat `editorial_annotations` as unsigned and mutable; never report a change to it as tampering | §8 |
| R6 | Report signature status **per run** — which run, which signer, which reason — using the vocabulary `valid` / `invalid` / `unsigned`, and the file-level vocabulary `signed` / `partial` / `unsigned` / `invalid`; never collapse `partial` into `signed`; treat an unsigned file as valid | §9.4 |
| R7 | Select the current run per producer by the §7.3 rule (`supersedes`, then latest `generated_at`, then array position) when several runs share a producer | §7.3 |
| R8 | Handle both profiles: read only `manifest.json` for Core semantics from a Full file; compute member data offsets from the local header and tolerate unknown extra-field records | §3.3, §4.4 |
| R9 | Interpret positions as integer frames at the rational rate, treat seconds and timecode strings as derived, and treat a `timecode: null` medium as seconds-only | §6A.2, §6A.3 |
| R10 | Never treat the absence of a sensitive facet as a negative determination | §10.3 |

A Reader that exposes embeddings MUST read them through the `vectors`
tensor and `opi.*` metadata (§7b.3). A Reader that cannot verify signatures
MUST say so rather than reporting `unsigned`.

### 16.3 Validator

A conforming Validator MUST implement every Reader requirement and MUST
evaluate the following checks, reporting each as pass or fail with a reason.
Check names are those of the reference implementation; another validator
MAY name its checks differently but MUST be able to map each of these to
one of its own (the conformance runner, §16.6, matches by substring).

| Group | Checks (reference names) | Rule |
|---|---|---|
| readable | `readable`, `canonical form` | §3.2, §3.4 |
| envelope | `has opi`, `has profile`, `has media_binding`, `opi version`, `opi is first key`, `profile matches contents` | §5 |
| binding | `media_binding`, `media_binding.files`, `media present`, `media sha256` | §6, §2.2 |
| human layer | `editorial_annotations` (must be an object) | §8 |
| time | `time: timecode.rate`, `time: timecode.label`, `time: timecode.start`, `time: duration`, `time: span <path>`, `time: spans` | §6A.7, §6.5 |
| runs | `runs: run[i] required`, `producer`, `model_version`, `run_id form`, `run_id derived`, `run_id unique`, `generated_at`, `egress`, `confidence_scale`, `attachments`, `attachment <name>`, `supersedes`, `depends_on`, `facet <name>` (confidence key on every entry) | §7.8 |
| members | `members: container.*` (readable, methods, no-encryption, no-data-descriptors, no-patched-data, no-zip64, no-comment, timestamps, entry-count, signature), `manifest.present`, `manifest.first`, `names.valid`, `names.case-unique`, `names.no-directory-entries`, `members.aligned`, `attachments.all-declared`, `attachments.all-present`, `attachments.single-owner`, `attachment.<name>`, `embeddings.<name>`, `still.<name>` | §4, §7b.6 |
| facets | `facets: run[i] <facet>` structure for **known** facets only, plus the sensitive-facet rules `review_required` and `accuracy claim` | Appendix C, §10.3 |
| signatures | `run[i] valid` / `invalid` / `unsigned`, per §9.4 | §9.4 |

A Validator MUST NOT reject a file for: unknown top-level keys; unknown run
keys; unknown facets; unknown keys *within* an attachment object (member
names themselves are constrained by §4.2–§4.3); a numeric `confidence` on a
measured facet (read as coverage, C.0.1); the absence of signatures. The
facet checks for unknown facets are "pass, not evaluated".

**Result vocabulary.** The file-level result is exactly one of:

| Result | Meaning | Exit code |
|---|---|---|
| `valid-signed` | every check passed; every run's signature verified | 0 |
| `valid-partial` | every check passed; some runs verified, none failed, some unsigned | 0 |
| `valid-unsigned` | every check passed; no run carries a signature | 0 |
| `invalid` | at least one check failed, or any signature failed to verify | 1 |

A command-line validator MUST exit `0` for the three `valid-*` results and
`1` for `invalid`, and SHOULD offer a machine-readable report with, at
minimum, `status` and a list of `checks` each carrying `name`, `ok` and
`detail`. Usage errors (no such file, bad arguments) SHOULD exit `2`.

### 16.4 Producer

A conforming Producer MUST:

| # | Requirement | Rule |
|---|---|---|
| P1 | Write a ZIP always; `manifest.json` first; Core = `manifest.json` alone | §3.1, §4.3 |
| P2 | Name the sidecar `<media filename>.opi` beside the media unless the caller names an explicit destination | §2.1 |
| P3 | Never modify, append to, or rewrite the media | §2.3 |
| P4 | Serialize the manifest exactly as §5.5 specifies, `opi` first | §5.5, §5.2 |
| P5 | Bind by `sha256` for every file; carry `timecode` as a reduced rational rate or `null` | §6, §6A.1, §6A.2 |
| P6 | Derive `run_id` as §7.1 specifies; give every run `producer`, `model_version`, `facets`; sort runs by (`producer`, `model_version`) | §7.1, §7.2, §7.7 |
| P7 | Give every facet entry a `confidence` key (a number in the run's scale, or `null`) | §7.5, C.0.1 |
| P8 | Express positions as integer frames with exclusive out; when seconds or timecode strings are also written, they agree | §6A.3 |
| P9 | Declare every member in exactly one run's `attachments` with `sha256`, `size` and `media_type`; store `.safetensors` and `.bin` members uncompressed at 64-byte-aligned offsets; write no ZIP64, no comment, fixed timestamps | §4.4–§4.7, §7b.1, §7b.2 |
| P10 | Emit embeddings in the `vectors [count, dim]` layout with the required `opi.*` metadata; emit stills stripped of metadata chunks, only under an egress declaration that permits frames | §7b.3, §7b.4 |
| P11 | Sign each run it is entitled to sign over the §9.2 payload; never sign `editorial_annotations` | §9.2, §9.3, §8 |
| P12 | Write atomically (temp file, `fsync`, rename); preserve the human layer of an existing file on rewrite | §11, §8.3 |
| P13 | Emit sensitive facets only as review flags with `review_required: true` and no accuracy claim | §10.3 |
| P14 | Apply any data-egress policy at the write, and declare `egress` on runs that carry derived data or frames | §11, §7.2 |
| P15 | Be deterministic: the same inputs produce the same bytes apart from `generated_at`, `signed_at` and signatures | §4.5, §7.7, §11 |
| P16 | Keep identity out of what it cannot take back: `host` names a machine class and never an instance; a label's `by` is never taken from an OS user name, an email address, a signature or a machine run's signer | §7.2, §8.2, §8.4, §13 |

A Producer proves conformance by validating its output. Its conformance
statement names the validator used.

### 16.5 The vector suite

The vectors under `vectors/` are the executable half of this specification.
They are versioned with the format: **suite `opi-0 / 2026-08-29`**. A vector
is either a **complete file** (a `.opi` on disk, or a manifest the runner
materialises into one) with an expectation `valid` or `must-fail <check>`,
or a **unit vector**: something that cannot be presented to a validator as
a file. Two things are. One is a function a Validator's internals should
reproduce — a rate label, a drop-frame conversion, a `run_id` derivation.
The other is a rule enforced by `schema/opi-0.schema.json` and by no
validator row (§5's table convention): a file breaking it is well-formed to
a validator, so the suite records the schema verdict instead.

`vectors/README.md` catalogues every directory and its JSON shape. A
conforming Validator MUST accept every complete-file vector marked valid and
MUST reject every must-fail vector; it SHOULD reject each for the stated
reason (matched by substring on its own check names).

### 16.6 The conformance runner and its report

`tools/conformance/run.py` runs any command-line validator against the
suite and writes a report. It is standard-library Python and is a public
artefact of this specification.

```
python tools/conformance/run.py --validator "my-validator --json {file}" \
                                --report report.json
python tools/conformance/run.py --self        # the reference validator; must be all-pass
```

The report is JSON with this shape (stable within a major):

```json
{
  "suite": "opi-0 / 2026-08-29",
  "generated_at": "2026-08-29T21:00:00Z",
  "validator": "my-validator --json {file}",
  "classes": {"validator": {"pass": 40, "fail": 0}},
  "totals": {"pass": 40, "fail": 0, "unit_only": 11, "reason_mismatch": 0},
  "vectors": [
    {
      "id": "members/case-misaligned.opi",
      "class": "validator",
      "kind": "file",
      "expected": "must-fail",
      "expected_check": "members.aligned",
      "exit_code": 1,
      "outcome": "pass",
      "reason_match": true,
      "observed_failures": ["members: members.aligned"]
    }
  ]
}
```

`outcome` is `pass` when the exit code agrees with the expectation, `fail`
otherwise, and `unit-only` for vectors that cannot be materialised.
`reason_match` is `true` when a failing check name contains the expected
check name, `false` when the file was rejected for a different stated
reason, and `null` when no expected check or no machine-readable report was
available. A `reason_match` of `false` does not fail the vector — a
validator may legitimately discover a different violation first — but the
count is reported so an implementer can see where their check granularity
differs from the reference.

### 16.7 Conformance statement

An implementation publishes a statement of this form, and keeps it current:

```
Implementation:  <name> <version>
Classes:         Reader (Core and Full) · Validator · Producer (Core only)
Specification:   .opi major 0, suite opi-0 / 2026-08-29
Validator used:  <name or "reference tools/opi_verify.py">   (Producers)
Runner report:   <URL or path to report.json>                (Validators)
Not claimed:     <e.g. "signature verification — reports 'unverified'">
Date:            <YYYY-MM-DD>
```

Partial conformance is stated by qualifying the class — "Reader, Core
profile only", "Validator, members checks not implemented" — never by
claiming a class and omitting requirements silently. A Reader that does not
verify signatures says so in *Not claimed*. A statement that omits the suite
version is not a conformance statement.

### 16.8 What conformance does not mean

Conformance is a statement about the file, not about the intelligence in it.
A conformant Producer may write facets that are wrong; a conformant
Validator confirms structure, binding and signatures, not truth. No class in
this chapter licenses an implementation to describe its output as accurate,
certified, or cleared (§10.3).

## Appendix A — Annotated example

`examples/A001_C001.mov.opi`, produced end to end on 2026-08-29 from a 6 s
23.976 fps test clip registered into a latent store, one shot-detection run,
one human label. Verbatim, with commentary in the right margin.

```jsonc
{
  "opi": 0,                                  // first key; format major version
  "profile": "core",                         // matches the bytes: this file starts with "{"
  "generator": "latent 0.0.45",              // informative, unsigned
  "generated_at": "2026-08-29T13:30:43+00:00",
  "media_binding": {                         // signed by every run below
    "asset_id": "01a04db6-481c-7255-a87e-b426e1f2c130",
    "duration_s": 6.0,
    "shot_at": null,
    "camera": "Lavf61.7.100",
    "ingested_at": "2026-08-29T13:29:46+00:00",
    "timecode": {
      "start": "01:00:00:00",
      "recorded": "01:00:00:00",
      "rate": { "num": 24000, "den": 1001 }, // rational, never 23.976
      "drop_frame": false,
      "label": "23.976"                      // human-readable, derived
    },
    "files": [
      {
        "role": "original",                  // the sidecar lives beside this one
        "name": "A001_C001.mov",             // discovery hint
        "path": "A001_C001.mov",                 // informative, untrusted; a bare name here
        "size": 610380,
        "sha256": "81214813e87fdbb812a60675a5dc45637d5d40e69f899057bb5c8322abc8c07e", // THE binding
        "container": "mov,mp4,m4a,3gp,3g2,mj2",
        "video_codec": "h264",
        "audio_codec": "aac",
        "width": 640,
        "height": 360,
        "fps": 23.976
      }
    ],
    "provenance": [
      {
        "session_id": "01a04db6-479a-7e7e-adae-b6b2fe13357e",
        "original_path": "A001_C001.mov",
        "source_label": "A001",
        "checksum_verified_at": "2026-08-29T13:29:46+00:00",
        "note": null
      }
    ]
  },
  "machine_intelligence": [                  // one run per producer pass
    {
      "run_id": "d23f5d13c94f0918ab672cda134e80f5", // derived: sha256(JCS({producer, model_version, sha256}))[:32], see §7
      "producer": "shots:scenedetect",
      "model_version": "scenedetect-0.7",
      "generator": "latent 0.0.45",
      "facets": {                            // open in version 0
        "shots": [
          {
            "idx": 0,
            "confidence": null,
            "span": {
              "t_start_s": 0.0,
              "t_end_s": 5.964291666666667,
              "tc_in": "01:00:00:00",
              "tc_out": "01:00:06:00",        // exclusive
              "frames": 144,
              "frame_in": 0,
              "frame_out": 144
            }
          }
        ]
      },
      "signature": {                         // covers {media_binding, this run minus this key}
        "role": "machine_producer",
        "signer": "urn:openpicture:example:producer",
        "algorithm": "Ed25519",
        "public_key": "558273f79c8b304f1ad035f2201c01ceed02b71cb20f0ffbcccfee49c5cdcb15",
        "signed_at": "2026-08-30T01:15:39+00:00",
        "signature": "2XN6F6CXT1IJpGL9NIrLCdv6YyjnzR1VNJnGtbjyqW0+hy6eBbWC8e32Rrd8u/EhcEcc6omHSchRV4EZOZYsCw=="
      }
    }
  ],
  "editorial_annotations": {                 // never signed; the holder's
    "labels": [                              // the writer owns this key and preserves all others
      {
        "name": "select",
        "value": "hero",
        "created_by": "editor",
        "created_at": "2026-08-29T13:30:43+00:00",
        "span": {
          "t_start_s": 0.0, "t_end_s": 2.0,
          "tc_in": "01:00:00:00", "tc_out": "01:00:02:00",
          "frames": 48, "frame_in": 0, "frame_out": 48
        }
      }
    ]
  }
}
```

`examples/A001_C001.mov.full.opi` is the same manifest packed as a Full
container with `keyframes/shot_0000.webp` (7 636 B, STORE) and a 44-byte
`embeddings.bin` STORED at data offset 9152 (= 143 × 64). Both examples
validate `valid-signed` against the public key above; the corresponding
throwaway secret is `examples/example-producer.key`.

## Appendix B — Test vectors

Produced by running the reference implementation. A third-party
implementation that reproduces the payload bytes and the signature is
interoperable at the signing layer.

**Secret key** (RFC 8032 §7.1 TEST 1, hex):

```
9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60
```

**Public key** (hex): `d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a`

**Manifest before signing** (any whitespace; key order irrelevant to the payload):

```json
{
  "opi": 0,
  "profile": "core",
  "media_binding": {
    "files": [
      {"role": "original", "name": "clip.mov", "size": 3,
       "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"}
    ]
  },
  "machine_intelligence": [
    {"run_id": "r1", "producer": "example", "model_version": "1",
     "facets": {"shots": [{"idx": 0, "confidence": 0.5}]}}
  ],
  "editorial_annotations": {"notes": "test"}
}
```

(`ba7816bf…15ad` is SHA-256 of the three bytes `abc`.)

**Canonical payload** for run 0 (§9.2), as text — 255 bytes, no newline:

```
{"media_binding":{"files":[{"name":"clip.mov","role":"original","sha256":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","size":3}]},"run":{"facets":{"shots":[{"confidence":0.5,"idx":0}]},"model_version":"1","producer":"example","run_id":"r1"}}
```

Same payload as hex:

```
7b226d656469615f62696e64696e67223a7b2266696c6573223a5b7b226e616d65223a22636c69702e6d6f76222c22726f6c65223a226f726967696e616c222c22736861323536223a2262613738313662663866303163666561343134313430646535646165323232336230303336316133393631373761396362343130666636316632303031356164222c2273697a65223a337d5d7d2c2272756e223a7b22666163657473223a7b2273686f7473223a5b7b22636f6e666964656e6365223a302e352c22696478223a307d5d7d2c226d6f64656c5f76657273696f6e223a2231222c2270726f6475636572223a226578616d706c65222c2272756e5f6964223a227231227d7d
```

**Signature** (Ed25519 over the payload, base64):

```
9W1V3HZU8ydlimgdjJdjksYcWtmvpq8/TIuU0AmEeWsD0m6fZ0jMzq3kVEif1JryqJq0yoXofCmWKgiv4DmmCw==
```

**Resulting signature entry** (with a fixed `signed_at`; `signed_at`, `role`
and `signer` are not part of the payload and do not affect the signature):

```json
"signature": {
  "role": "machine_producer",
  "signer": "urn:example:producer",
  "algorithm": "Ed25519",
  "public_key": "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
  "signed_at": "2026-08-29T00:00:00+00:00",
  "signature": "9W1V3HZU8ydlimgdjJdjksYcWtmvpq8/TIuU0AmEeWsD0m6fZ0jMzq3kVEif1JryqJq0yoXofCmWKgiv4DmmCw=="
}
```

Verification of the resulting manifest MUST yield status `signed`. Changing
`confidence` to `0.51` MUST yield `invalid` for run 0; changing
`editorial_annotations.notes` MUST leave the status `signed`.

**JCS checks** (RFC 8785 Appendix B, a selection an implementer should pass):
`1e21` → `1e+21`; `1e-7` → `1e-7`; `0.000001` → `0.000001`; `1.0` → `1`;
`333333333.33333329` → `333333333.3333333`; keys `["€", "\U0001f600",
"～"]` sort as `"€"`, `"\U0001f600"`, `"～"` (UTF-16 order, not
code-point order).

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
