# The smallest useful integration

You do not have to implement the whole format to get something out of it.
Three integrations, in increasing order of effort, each useful on its own.

## 1. Read a shot list (an afternoon)

If a producer has already written `.opi` files beside a tree of media, a
consumer can use the shot boundaries without any library:

```bash
unzip -p A001_C001.mov.opi manifest.json \
  | jq '.machine_intelligence[] | select(.producer | startswith("shots:")) | .facets.shots[] | .span'
```

```json
{
  "t_start_s": 0.0,
  "t_end_s": 5.964291666666667,
  "tc_in": "01:00:00:00",
  "tc_out": "01:00:06:00",
  "frames": 144,
  "frame_in": 0,
  "frame_out": 144
}
```

Positions are integer frames at the rate in `media_binding.timecode.rate`;
the seconds and timecode strings are derived conveniences you may use or
ignore. In Python:

```python
import openpicture
sc = openpicture.load("A001_C001.mov.opi")
for run, shots in sc.facets("shots"):
    print(run.producer, [(s["span"]["frame_in"], s["span"]["frame_out"]) for s in shots])
```

What you get: a shot list any tool can consume, with its producer named.
What you do not need: the producer's software, a database, or an account.

## 2. Validate before you import (a day)

A pipeline that ingests `.opi` files should refuse ones it cannot trust.
Drop `tools/opi_verify.py` — a single standard-library file — next to your
ingest script and gate on its exit code:

```bash
python3 opi_verify.py --media-dir /vol/footage A001_C001.mov.opi || exit 1
```

It checks the media binding against the master on disk, every member's hash
and alignment, and every run's signature, and it reports per run. Add a key
log (`openpicture keys`) to distinguish *signed by someone* from *signed by a
producer you know*.

What you get: a hard guarantee that what you imported describes the bytes
you hold and was not altered since its producer signed it.

## 3. Write one run (a week)

If your tool computes something about footage, write it as a run. The
contract is short — see the [producer workflow](producers.md) — and the
payoff is that your result now travels with the media and can be read by
anything on this page.

```python
import hashlib
from openpicture import container, sign, runs

sha = hashlib.sha256(open("A001_C001.mov", "rb").read()).hexdigest()
manifest = {
    "opi": 0, "profile": "core",
    "media_binding": {"files": [{"role": "original", "name": "A001_C001.mov", "size": 610380, "sha256": sha}]},
    "machine_intelligence": [{
        "run_id": runs.run_id("mytool:loudness", "1.0", sha),
        "producer": "mytool:loudness", "model_version": "1.0",
        "facets": {"loudness": [{"span": {"frame_in": 0, "frame_out": 143}, "lufs": -23.1}]},
    }],
    "editorial_annotations": {},
}
sign.sign_all(manifest, bytes.fromhex(open("producer.key").read().strip()), signer="urn:example:mytool")
container.write_core(manifest, "A001_C001.mov.opi")
```

A facet the specification does not know about — `loudness` here — is
allowed. Readers ignore what they do not understand; a validator does not
reject it. If the facet turns out to be generally useful, [propose it for
the shared vocabulary](../contribute/propose.md).

If a `.opi` already exists beside the media, read it first and add your run
to `machine_intelligence` rather than replacing the file: other producers'
runs and their signatures are untouched by yours, and the human layer must
be carried forward. `openpicture.container.rewrite` keeps existing members
intact.
