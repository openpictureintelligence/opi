# Adopt `.opi`

The smallest useful adoption path is deliberately local: keep the media where
it is, put the sidecar beside it, validate before importing it, and read only
the fields your tool understands. No account, service, or vendor application
is required.

## Start with a shipped example

The repository includes a signed Core file and a Full file with member data.
The media is not included, so both examples are safe to download and inspect.

```bash
python3 tools/opi_verify.py examples/A001_C001.mov.opi
```

The expected result is an exit code of `0` and a line like:

```text
valid-signed   examples/A001_C001.mov.opi  (profile=core, opi=0, signatures=signed)
```

The validator reports that the bound media is absent as an allowed condition.
When the original media is available, pass its directory explicitly so the
SHA-256 binding is checked against the bytes on disk:

```bash
python3 tools/opi_verify.py --media-dir /path/to/media examples/A001_C001.mov.opi
```

`valid-signed` means the structure and signatures verify. It does not mean
that a facet is factually correct; signatures identify what a producer wrote,
not whether a model's interpretation is right.

## Add a validation gate

Copy [`tools/opi_verify.py`](https://github.com/openpictureintelligence/opi/blob/main/tools/opi_verify.py)
into a small ingest or indexing job. It uses only the Python standard library
and has a simple contract:

```bash
python3 opi_verify.py --json clip.mov.opi > validation.json
test "$(python3 -c 'import json,sys; print(json.load(open("validation.json"))["status"])')" != invalid
```

For a production pipeline, fail closed on exit code `1`, retain the JSON
report with the ingest record, and decide separately how trusted signer keys
are managed. A missing master is valid and reported; a present master with a
different SHA-256 is invalid.

## Read the fields you need

Every `.opi` is a ZIP with a `manifest.json`. A basic reader can start with
ordinary tools:

```bash
unzip -p clip.mov.opi manifest.json
```

Or use the reference package:

```python
import openpicture

sidecar = openpicture.load("clip.mov.opi")
for run in sidecar.runs:
    print(run.producer, run.model_version, run.status)
print(sidecar.trusted_facets("shots"))
print(sidecar.annotations)
```

Readers should ignore fields they do not understand, preserve the unsigned
`editorial_annotations` block when rewriting, and validate before trusting
machine-produced claims.

## Write one producer run

If your tool generates intelligence about footage, write one run rather than
inventing a second sidecar format. The reference implementation provides the
identity, container, and signing helpers:

```python
import hashlib
from openpicture import container, runs, sign

media = "clip.mov"
sha256 = hashlib.sha256(open(media, "rb").read()).hexdigest()
manifest = {
    "opi": 0,
    "profile": "core",
    "media_binding": {"files": [{"name": media, "sha256": sha256}]},
    "machine_intelligence": [{
        "run_id": runs.run_id("example:shots", "1.0", sha256),
        "producer": "example:shots",
        "model_version": "1.0",
        "facets": {"shots": []},
    }],
    "editorial_annotations": {},
}
sign.sign_all(manifest, bytes.fromhex(open("producer.key").read().strip()),
              signer="urn:example:producer")
container.write_core(manifest, media + ".opi")
```

Then validate the result:

```bash
python3 tools/opi_verify.py --media-dir . clip.mov.opi
```

If the file already has runs from another producer, carry them forward and
append your own run. Do not replace another producer's signed work, and do
not sign `editorial_annotations`.

## A practical first integration

For an early integration, claim only what you have exercised:

1. **Reader:** discover `.opi` files beside media and expose the fields your
   application can use.
2. **Validator:** gate imports with the standalone validator and retain its
   report.
3. **Producer:** write one run, include a model or tool version, bind the
   original by SHA-256, and sign it if you control the producer key.

The format is version 0 and pre-freeze. Publish the exact OPI version, profile,
validator command, and fields your integration supports. Do not describe an
integration as certified, accurate, or broadly compatible without evidence.

For the complete rules, use the [normative specification](spec/index.md),
[test vectors](https://github.com/openpictureintelligence/opi/tree/main/vectors), and the
[conformance runner](https://github.com/openpictureintelligence/opi/blob/main/tools/conformance/run.py).
