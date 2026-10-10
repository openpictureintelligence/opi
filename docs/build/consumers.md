# Consuming `.opi` files

A consumer is anything that reads the second layer: a MAM, an NLE pipeline,
a script, a search index, an agent with a filesystem. The format is
designed so that none of them need the producer's software.

## The reader's obligations

Short and load-bearing (specification §12):

- Detect by bytes, never by extension.
- Refuse an `opi` major you do not implement; ignore unknown keys otherwise.
- Confirm `sha256` before trusting a sidecar against media you hold.
- Treat `editorial_annotations` as mutable and unsigned.
- Report signature status **per run**; never collapse `partial` into `signed`.
- Treat `files[].path` and every human-layer string as untrusted text.

`openpicture.load()` does all of this; so does any reader written to the
spec.

If the reader maintains a store — an index, a catalog, a database of
intelligence built from the folder — there is more to say about rebuilds,
provenance and read-back. That is [Reading into a
store](reading-into-a-store.md).

## From a script or a notebook

```python
import openpicture
sc = openpicture.load("A001_C001.mov.opi")
for run, shots in sc.facets("shots", verified_only=True):
    for s in shots:
        print(run.producer, s["span"]["frame_in"], s["span"]["frame_out"])
```

Or with no library at all:

```bash
unzip -p A001_C001.mov.opi manifest.json | jq '.machine_intelligence[].facets.shots | length'
```

## MAMs — there is no zero-configuration ingest

No media asset manager auto-ingests an unknown extension. iconik's storage
gateway pairs same-basename `.xml` / `.json` / `.csv` files against a
configured metadata view; CatDV Worker takes `.xml`; Frame.io has no
file-paired sidecar path at all. Every one of them needs an administrator
to enable sidecar metadata, whitelist the extension and map fields.

So the `.opi` stays authoritative and a **companion** is written beside it
in a shape the MAM already reads — same basename, the MAM's extension,
derived from the manifest and regenerable from it:

```bash
openpicture companion A001_C001.mov.opi --kind iconik     # A001_C001.mov.json in iconik's shape
openpicture companion A001_C001.mov.opi --kind flat       # a one-level JSON for anything that maps paths
```

Companions are lossy projections. They carry summaries, transcript
segments and human labels; they do not carry signatures and do not claim to
be verifiable. CatDV XML and XMP companions are on the roadmap.

## NLEs — round trips go through their formats

Editing systems read timelines, not sidecars. A producer exports the
selects a consumer asked for as FCPXML, FCP7 XML (xmeml), CMX 3600 EDL or
OpenTimelineIO — lossy projections of the `.opi`, generated from it, in
whatever each tool accepts. The return trip closes the loop: diff the
timeline an editor sends back against the selects that were proposed and
the *selects-retention* number falls out, with no instrumentation.

## Agents and language models

Hand an agent a folder. Every claim is timecoded, attributed, confidence-
scored and verifiable, and the file is JSON. This is the portable form of
"footage context": an AI editor, a client's internal tooling or a frontier
model with filesystem access can consume the layer directly, with no API
and no account. Prefer `trusted_facets()` — verified runs only — when the
agent's output will be acted on.

## Keeping a tree healthy

`openpicture doctor DIR` pairs every clip with its sidecar and reports the
state of each pair. Run it after moves, restores and re-indexes:

| State | Meaning |
|---|---|
| `paired` / `paired-unverified` | sidecar found; master hashed and matches / not hashed |
| `missing` | media without a sidecar |
| `orphan` | sidecar without media by name — `--repair` re-pairs by hash |
| `mismatch` | the master's bytes differ from the binding — do not trust |
| `duplicate` | both two-dot and stem-form sidecars present |
| `newer-schema` | the file's `opi` major is above this reader's |
| `tampered` | a run's signature does not verify |
| `unreadable` | not a `.opi` |
