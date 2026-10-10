---
title: Open Picture Intelligence
body_class: opi-home
hide:
  - toc
---

# Open Picture Intelligence

<div class="opi-band" markdown>
<div class="opi-hero" markdown>
<div markdown>

<p class="opi-kicker">OPI · Open Picture Intelligence · format version 0</p>

<h1 class="opi-title">An open, signed sidecar <span>for intelligence about media.</span></h1>

<p class="opi-lede">A <code>.opi</code> file travels beside the footage it describes. It carries what a machine found — shots, transcript, camera motion, embeddings — and what a person added, in a form anyone can read and verify.</p>

<p class="opi-files">footage.mov <span class="opi-plus">+</span> footage.mov<span class="opi-ext">.opi</span></p>

<p class="opi-actions" markdown>
[Read the spec](spec/index.md){ .md-button .md-button--primary }
[Run the quickstart](quickstart.md){ .md-button }
</p>

</div>
<div markdown>

```json
{
  "opi": 0,
  "profile": "core",
  "media_binding": {
    "timecode": {"start": "01:00:00:00",
                 "rate": {"num": 24000, "den": 1001}},
    "files": [{"role": "original", "name": "A001_C001.mov",
               "sha256": "81214813e87fdbb8…8322abc8c07e"}]
  },
  "machine_intelligence": [{
    "producer": "shots:scenedetect",
    "model_version": "scenedetect-0.7",
    "facets": {"shots": [{"idx": 0,
      "span": {"frame_in": 0, "frame_out": 144}}]},
    "signature": {"algorithm": "Ed25519",
      "signer": "urn:openpicture:example:producer"}
  }],
  "editorial_annotations": {
    "labels": [{"name": "select", "value": "hero"}]
  }
}
```

<p class="opi-hero-caption">Excerpt from <code>examples/A001_C001.mov.opi</code> in the repository — a real file, abridged. <code>unzip -p A001_C001.mov.opi manifest.json</code> prints the whole thing.</p>

</div>
</div>
</div>

<div class="opi-section" markdown>

## One file. Three guarantees.

<div class="opi-guarantees" markdown>
<div markdown>

### Open

A published format under a permissive licence. Physically, a ZIP with a JSON manifest: readable with the tools already on the machine, outside any one vendor's application. Readers ignore fields they do not understand, so the file can grow without breaking anyone.

</div>
<div markdown>

### Signed

Each producer run inside the file carries its own Ed25519 signature over the run and the media binding. A verifier reports, run by run, what it could attribute to whom. Nothing is encrypted; unsigned is a visible state, not an error.

</div>
<div markdown>

### Bound

The manifest records the media by SHA-256, size and name. The master is never modified. Rename or move the clip and the sidecar still knows which bytes it describes — and a reader can check before trusting a claim.

</div>
</div>

</div>

<div class="opi-band opi-band--workflow" markdown>
<div class="opi-steps" markdown>

## From footage to a useful sidecar

1.  ### Produce

    A **producer** — any tool that analyses footage — writes `footage.mov.opi` beside the media. Its claims go under `machine_intelligence` as one **run** per model pass; binaries such as embeddings become **members** declared on that run; the run is signed with the producer's key.

2.  ### Verify

    A **validator** checks the file, the **media binding**, every declared member's hash and alignment, and every run's **signature**. `openpicture validate` and the single-file `opi_verify.py` are the reference; the specification says exactly what a conforming validator must check.

3.  ### Consume

    A person or a pipeline reads the fields it understands — a shot list, a transcript, a rating in `editorial_annotations` — and skips the rest. No editor, asset manager or hosted service is required to read the file. Validate before trusting its claims.

<details class="opi-reveal" markdown>
<summary>footage.mov.opi</summary>
<div class="opi-stage" markdown>
<span class="opi-label">manifest</span>
<pre>unzip -p footage.mov.opi manifest.json
{ "opi": 0, "media_binding": { "files": [ { "name": "footage.mov", "sha256": "…" } ] },
  "machine_intelligence": [ { "producer": "shots:scenedetect", "facets": { "shots": [ … ] } } ],
  "editorial_annotations": { } }</pre>
</div>
<div class="opi-stage" markdown>
<span class="opi-label">validation</span>
<pre>openpicture validate footage.mov.opi
<span class="opi-valid">valid-signed</span>   footage.mov.opi  (profile=core, opi=0, signatures=signed)
  ok   media sha256
  ok   run[0] valid: shots:scenedetect by urn:example:producer</pre>
</div>
<div class="opi-stage" markdown>
<span class="opi-label">consumption</span>
<pre>sc = openpicture.load("footage.mov.opi")
sc.trusted_facets("shots")      # only from runs whose signature verified
sc.annotations["labels"]        # the human layer, yours to change</pre>
</div>
</details>

</div>
</div>

<div class="opi-section" markdown>

## Build on the format

<div class="opi-paths" markdown>
<div markdown>

### Using .opi

Validate a file, read its fields, add a note to the human layer, keep a tree of sidecars healthy.

- [Quickstart](quickstart.md) — five minutes, every command tested
- [Adopt `.opi`](adoption.md) — the smallest path from one file to an ingest gate
- [Examples](https://github.com/openpictureintelligence/opi/tree/main/examples) — real files, signed
- [Consumer workflow](build/consumers.md)

</div>
<div markdown>

### Implementing .opi

Write a producer, or a reader in another language, against the normative text.

- [Specification](spec/index.md) — version 0
- [JSON Schemas](reference/schema.md) and the [standalone validator](reference/validator.md)
- [Producer workflow](build/producers.md) · [Contribute](contribute/index.md)

</div>
</div>

</div>

<p class="opi-final" markdown>
OPI is the open interchange layer. Latent is our first full producer and workflow built on top of it — not a requirement for reading the files. The format is at version 0 and pre-freeze; the [status page](status.md) says what is implemented, what is provisional and what is not promised yet. The [specification](spec/index.md) is the canonical reference on this site. The schemas, reference implementation and examples are on GitHub at [openpictureintelligence/opi](https://github.com/openpictureintelligence/opi) — read the repository, try an example, or [open an issue](https://github.com/openpictureintelligence/opi/issues).
</p>
