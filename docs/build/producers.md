# Writing a producer

A **producer** is anything that analyses footage and writes `.opi` files.
The reference producer is `latent`, a footage-intelligence pipeline in the
steward's repository; nothing about the format is specific to it. The
split is deliberate: **OPI is the open interchange layer; Latent is our
first full producer and workflow built on top of it.** Latent's files are
ordinary `.opi` files — any other tool can validate, read and extend them
without Latent, and Latent works without any other tool's consent. This
page is the contract a producer signs up to, and the shortest path to
meeting it with the `openpicture` package.

## The contract

1. **One run per model pass.** Group your facets by `(producer,
   model_version)`; name the model precisely enough that two runs with the
   same name are interchangeable.
2. **Bind by hash.** Compute the SHA-256 of every file you describe and put
   it in `media_binding.files[]` with a `role`. Record the rational frame
   rate and source timecode if the media has them.
3. **Rational time.** Rates as `{num, den}`, positions as integer frames
   (in floors, out ceils, out exclusive). Seconds and timecode strings are
   derived conveniences.
4. **Declare members.** Every binary you attach goes in that run's
   `attachments` with `sha256` and `size`.
5. **Sign your runs**, and publish your keys in an append-only log.
6. **Preserve the human layer** when you rewrite: read the existing file's
   `editorial_annotations` and carry forward every key you do not own.
7. **Write atomically**, beside the media, as `<media>.opi`. Never touch the
   media.
8. **Sensitive facets are review flags.** No determinations, no accuracy
   claims in the file.

## In code

```python
import hashlib
from openpicture import container, embeddings, runs, sign

media = "A001_C001.mov"
sha = hashlib.sha256(open(media, "rb").read()).hexdigest()

manifest = {
    "opi": 0,
    "profile": "core",
    "generator": "myproducer 1.2.0",
    "media_binding": {
        "timecode": {"start": "01:00:00:00", "rate": {"num": 24000, "den": 1001}, "drop_frame": False},
        "files": [{"role": "original", "name": media, "size": 610380, "sha256": sha}],
    },
    "machine_intelligence": [
        {
            "run_id": runs.run_id("myproducer:shots", "transnetv2-1.0", sha),
            "producer": "myproducer:shots",
            "model_version": "transnetv2-1.0",
            "confidence_scale": "bp",
            "facets": {"shots": [{"idx": 0, "span": {"frame_in": 0, "frame_out": 144}, "confidence": 9700}]},
        }
    ],
    "editorial_annotations": {},
}

# Full profile: attach embeddings to the run that made them.
# flat_vectors is your model's output: one row per shot, `dim` floats each
# (12 shots × 768 here, stand-in values).
flat_vectors = [0.13, -0.72, 0.08, 0.44] * (12 * 768 // 4)
data = embeddings.pack_vectors(flat_vectors, 768, model="siglip-so400m", model_version="1")
name = embeddings.member_name("siglip-so400m")
manifest["machine_intelligence"][0]["attachments"] = {name: embeddings.attachment_entry(data)}
manifest["profile"] = "full"

# Preserve the human layer of an existing file
target = media + ".opi"
try:
    previous, _ = container.read_manifest(target)
    carried = {k: v for k, v in previous.get("editorial_annotations", {}).items() if k != "labels"}
    manifest["editorial_annotations"] = {**carried, **manifest["editorial_annotations"]}
except (FileNotFoundError, ValueError):
    pass

# Sign every run, then write atomically
secret = bytes.fromhex(open("producer.key").read().strip())
sign.sign_all(manifest, secret, signer="urn:example:myproducer")
container.write_full(manifest, target, {name: data})
```

Then `openpicture validate A001_C001.mov.opi` should say `valid-signed`.

## Keys

Generate one key per producer identity (`openpicture keygen`), keep the
secret out of the log, and publish the public key in a JSON Lines log you
never delete from (`openpicture keys add`). Rotate by adding; retire by
annotating. Verifiers who hold your log report your runs as `trusted`.

## Egress

Writing a sidecar is an egress of derived data — transcripts, labels,
confidences leave your store. Keyframe stills are frames of the media
itself and belong in a stricter class. If you operate under a data-handling
policy, apply it at the write, not at the in-memory build: building a
manifest is a read.

## Determinism

Same inputs, same bytes (apart from `generated_at` and `signed_at`). Sort
runs by `(producer, model_version)`, derive `run_id` from stable inputs,
fix ZIP timestamps (the reference implementation does). Deterministic
files diff, and `openpicture diff` becomes an evaluation tool: model A
against model B on the same clip, as a text diff.
