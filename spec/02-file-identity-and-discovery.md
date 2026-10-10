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
