# Examples

Two real files, produced end to end on 2026-08-29 by the reference producer
(Latent — Lunar Park's footage-intelligence pipeline, not yet public) and
re-signed here as the specification evolved: a 6 s 23.976 fps test clip (`ffmpeg testsrc2`, TC
01:00:00:00) registered into a latent store, shots detected by
`shots:scenedetect`, one human label added, egress opted in, written by
`latent export opi`, then sanitized for publication.

| File | Profile | Members | `openpicture validate` |
|---|---|---|---|
| `A001_C001.mov.opi` | Core | `manifest.json` only | `valid-signed` |
| `A001_C001.mov.full.opi` | Full | `keyframes/shot_0000024.webp` (512×288 WebP still at frame 24), `embeddings/example-hash.safetensors` (2×4 F16, 64-byte aligned) | `valid-signed` |

`example-producer.key` is the throwaway Ed25519 secret that signed both
(public `558273f7…cb15`). Test material only; never a real producer key.

## What was sanitized

- `media_binding.files[].path`, `provenance[].original_path` and
  `provenance[].source_label` were absolute paths on the machine that wrote
  the file. They are informative, untrusted and never part of the binding;
  here they are the bare name `A001_C001.mov` and the reel label `A001`.
- `run_id` was regenerated to the derived form the specification now
  requires (§7): `sha256(JCS({producer, model_version, sha256}))[:32]`.
- Every facet entry carries a `confidence` key (`null` = not estimated).
- The Full file's members were renamed and re-declared to the §7b rules
  (reserved directories, zero-padded frame in the still's name, required
  safetensors metadata). The embedding vectors are a hand-written stand-in;
  the still is the real frame.

The media itself is not shipped. The validator reports `not beside sidecar
(allowed)`; `openpicture doctor examples/` reports both files as `orphan`.

## Regenerating

```python
from openpicture import container, sign, runs
m, _ = container.read_manifest("examples/A001_C001.mov.opi")
# edit m, pop each run["signature"], then:
sign.sign_all(m, bytes.fromhex(open("examples/example-producer.key").read().strip()),
              signer="urn:openpicture:example:producer")
container.rewrite("examples/A001_C001.mov.opi", m)
```

Keep `SPEC.md` Appendix A (generated from `spec/appendix-a-annotated-example.md`)
in step with the Core file.
