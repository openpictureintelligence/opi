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
