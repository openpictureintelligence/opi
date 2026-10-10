# The file and its profiles

## One physical form: a ZIP

A `.opi` file is a ZIP archive whose first member is `manifest.json`. That
is the whole physical contract. It means one media type, one macOS UTI
(conforming to `public.zip-archive`), one code path in every reader, and
`unzip -p clip.mov.opi manifest.json` working on every file ever written.

Two profiles share the extension and are decided by **contents**, not by a
flag:

| Profile | Contents | Use |
|---|---|---|
| **Core** | `manifest.json` only | The intelligence as text: shots, transcript, facets, labels. Small, diffable, complete for most consumers. |
| **Full** | `manifest.json` plus members | Adds binary payloads — embeddings, keyframe stills, vendor extensions — for consumers that want zero-copy access to them. |

The manifest also declares `"profile"`, and a validator fails a file whose
declaration disagrees with its contents. Upgrading a clip from Core to Full
adds members and **does not change the name**: a clip described more
completely is the same artifact.

!!! info "Why not a bare JSON file for Core?"
    The bare manifest — the same bytes as `manifest.json`, on disk alone —
    is the **internal form**: what a producer holds in memory and what
    diffs in git. Readers accept it and validators flag it as non-canonical
    without failing it, but writers do not emit it as a deliverable. Two
    independent reviews reached the same conclusion: a dual-form format
    costs a magic-number branch in every reader, two media-type
    registrations, and a UTI that cannot honestly be both text and archive.
    A one-line git `textconv` (`unzip -p`) recovers the diffability.

## Detection

Readers never trust the extension. They read the first 64 bytes:

1. `PK\x03\x04` at byte 0 → a `.opi` in ZIP form; the profile comes from the
   member list.
2. Otherwise strip an optional UTF-8 BOM and leading whitespace; `{` → the
   internal form, read as Core.
3. Anything else — an empty ZIP, a spanned-archive marker, prepended data, a
   JSON array — is not a `.opi`.

## Naming: two dots

The sidecar for `A001_C001.mov` is `A001_C001.mov.opi`, in the same
directory. The full media filename plus `.opi`, not the stem: a camera
master and its lav recording routinely share a stem (`A001_C001.mov`,
`A001_C001.wav`) and each needs its own sidecar. Readers also accept the
stem form when no two-dot file exists; writers use the two-dot form. This
follows the BRAW `.sidecar` and ASC MHL conventions.

## Binding: the hash, not the name

The name is how a sidecar is *found*. The **SHA-256** in
`media_binding.files[]` is how it is *trusted*. A reader that locates a
sidecar by name confirms the hash before believing anything in it about the
bytes in hand. Paths recorded in the manifest are informative — what the
producer saw when it wrote the file — and are never used to open anything
without ordinary caution.

Consequences:

- Rename or move the media and the sidecar is an **orphan**, not a lie; a
  tool can re-pair it by hashing the tree (`openpicture doctor --repair`).
- Replace the media with different bytes and the sidecar is a **mismatch**;
  the validator fails it when the media is present.
- A sidecar travelling without its media is allowed and reported as such.

## The media is never touched

No embedding, no XMP, no rewrite of the master. A checksum manifest (MHL)
taken before a producer ran still verifies after. This is why the format is
a sidecar and not a metadata track.

## Writes are atomic

A writer produces the file in a temporary path beside the target, flushes,
and renames. A half-written sidecar next to a client's master is worse than
none; the format forbids in-place patching.

*Normative text: specification §2–§4.*
