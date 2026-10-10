# JSON Schemas

Two JSON Schema 2020-12 documents ship in `schema/`. Both are additive —
`additionalProperties: true` wherever the format promises forward
compatibility — so a file with keys they do not know still passes.

## `schema/opi-0.schema.json` — the envelope

Normative shape of a version-0 manifest:

- `opi` — integer, constant `0`
- `profile` — `"core"` or `"full"`
- `media_binding` — object; `files[]` required, each with `name` and a
  64-hex `sha256`; `timecode` a rational-rate object or `null`
- `machine_intelligence` — array of run objects: `run_id`, `producer`,
  `model_version` strings; `facets` an open object; `attachments`
  pattern-keyed on member names (which may not be absolute); `signature`
  with its fixed fields
- `editorial_annotations` — open object

Use it in CI or an editor to catch shape errors before a file is written.
The [standalone validator](validator.md) checks the same things and more
(hashes, alignment, signatures) without a schema library.

## `schema/facets-0.schema.json` — the proposed facet vocabulary

Non-normative until the schema freeze (register item B12). Definitions for
`span`, `confidence`, `shot`, `signal`, `shot_size`, `camera_motion`,
`composition`, `exposure_color`, `focus`, `continuity`, `take`,
`audio_usability`, `energy_curve`, `clearance` and `embedding_ref`. It
exists so producers converge on one vocabulary before it becomes
required; a validator must not reject a file for disagreeing with it.

## Using them

Any 2020-12 validator works. With the Python `jsonschema` package:

```python
import json, zipfile, jsonschema
schema = json.load(open("schema/opi-0.schema.json"))
with zipfile.ZipFile("clip.mov.opi") as zf:
    manifest = json.loads(zf.read("manifest.json"))
jsonschema.validate(manifest, schema)
```

The repository's own tests use a small stdlib checker so the package keeps
its no-dependency rule; the schemas are also cross-checked against
`jsonschema` when it is installed.

## Stability

The envelope schema changes only with the format's `opi` major. The facets
schema is expected to change until the freeze; changes are recorded in the
[changelog](../status.md#changelog).
