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
