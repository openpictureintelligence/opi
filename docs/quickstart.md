# Quickstart

Five minutes, one path: validate a shipped file, inspect it, write a `.opi`
by hand, sign it, break it on purpose, then change the human layer. Every
command and every line of output on this page was produced by running the
page from a clean directory against the current repository (2026-08-29,
`openpicture` 0.0.7).

## 1. Install

The reference implementation is standard-library Python 3.11+ with no
dependencies. It is not on PyPI yet — install from a checkout:

```bash
git clone https://github.com/openpictureintelligence/opi.git
cd opi
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/openpicture --version
```

The rest of this page assumes `openpicture` is on your `PATH` (or prefix
the commands with `.venv/bin/`).

## 2. Look at a real file

The repository ships two files produced from a real clip by the reference
producer. A `.opi` is a ZIP, so ordinary tools work on it:

```bash
unzip -l examples/A001_C001.mov.full.opi
```

```text
Archive:  examples/A001_C001.mov.full.opi
  Length      Date    Time    Name
---------  ---------- -----   ----
     3406  01-01-1980 00:00   manifest.json
     7636  01-01-1980 00:00   keyframes/shot_0000024.webp
      272  01-01-1980 00:00   embeddings/example-hash.safetensors
---------                     -------
    11314                     3 files
```

`inspect` adds what a ZIP listing cannot tell you: each member's data offset
in the file, and the manifest:

```bash
openpicture inspect examples/A001_C001.mov.full.opi | head -4
```

```text
profile: full
  manifest.json                                  3406 B  DEFLATE
  keyframes/shot_0000024.webp                    7636 B  STORE @1430
  embeddings/example-hash.safetensors             272 B  STORE @9152
```

The `embeddings/example-hash.safetensors` member is stored uncompressed at
an offset that is a multiple of 64, so a reader can memory-map the archive
and hand the bytes to a tensor library without copying.

## 3. Make a manifest

Create a stand-in clip and a manifest that binds to it by SHA-256. The
`run_id` is derived from the producer, the model version and the media
hash, so it is the same for anyone who does the same work:

```bash
mkdir demo && cd demo
printf 'hello footage' > clip.mov
SHA=$(shasum -a 256 clip.mov | cut -d' ' -f1)
RID=$(python3 -c "from openpicture import runs; print(runs.run_id('example:shots', '1.0', '$SHA'))")
cat > manifest.json <<EOF
{
  "opi": 0,
  "profile": "core",
  "media_binding": {
    "timecode": {"start": "00:00:00:00", "rate": {"num": 24, "den": 1}, "drop_frame": false},
    "files": [{"role": "original", "name": "clip.mov", "size": 13, "sha256": "$SHA"}]
  },
  "machine_intelligence": [
    {"run_id": "$RID", "producer": "example:shots", "model_version": "1.0",
     "facets": {"shots": [{"idx": 0, "span": {"frame_in": 0, "frame_out": 48}, "confidence": 0.9}]}}
  ],
  "editorial_annotations": {"notes": "first pass"}
}
EOF
```

Time is rational (`24/1`, or `24000/1001` for 23.976) and positions are
integer frames with an exclusive out-point. Seconds and timecode strings
are derived and optional.

## 4. Pack it

A **Core** file is a ZIP whose only member is `manifest.json`. `pack` writes
one when you give it no members:

```bash
openpicture pack manifest.json clip.mov.opi
openpicture validate clip.mov.opi
```

```text
valid-unsigned clip.mov.opi  (profile=core, opi=0, signatures=unsigned)
  ok   readable: profile core, zip
  ok   opi version: 0
  ok   time: timecode.rate: 24/1
  ok   time: timecode.start: 00:00:00:00
  ok   time: spans: 1/1 consistent
  ok   facets: run[0] shots: 1 entry · stable
  ok   run[0] unsigned: example:shots
```

Unsigned is a valid state. The two-dot name — `clip.mov.opi`, not
`clip.opi` — is the convention: a camera master and its lav recording often
share a stem, and each needs its own sidecar.

## 5. Sign it

Generate a producer key and sign every run in the file. The signature covers
the run and the media binding — *this intelligence, about this media* — and
nothing else:

```bash
openpicture keygen producer.key
openpicture sign clip.mov.opi --key producer.key --signer urn:example:producer
openpicture validate clip.mov.opi
```

```text
secret: producer.key
public: 98f912919e1b028234e8a097dcb27dad9932d28c9d5d1d2403fc8d430a0f4c21
signed 1 run(s) as urn:example:producer
valid-signed   clip.mov.opi  (profile=core, opi=0, signatures=signed)
  ok   readable: profile core, zip
  ok   opi version: 0
  ok   time: timecode.rate: 24/1
  ok   time: timecode.start: 00:00:00:00
  ok   time: spans: 1/1 consistent
  ok   facets: run[0] shots: 1 entry · stable
  ok   run[0] valid: example:shots by urn:example:producer
```

`producer.key` is written with mode `0600`. Keep it out of the repository.

## 6. Read it without any of this software

```bash
unzip -p clip.mov.opi manifest.json | head -14
```

```json
{
  "opi": 0,
  "profile": "core",
  "media_binding": {
    "timecode": {
      "start": "00:00:00:00",
      "rate": {
        "num": 24,
        "den": 1
      },
      "drop_frame": false
    },
    "files": [
      {
```

That is the entire format contract for a reader: open the ZIP, parse the
JSON, ignore what you do not understand.

## 7. Break it on purpose

Change one machine-layer value behind the producer's back and validate
again. The rewrite below keeps the container rule that ZIP entries carry
the fixed 1980 timestamp, so the only thing it breaks is the signature —
and the run that was tampered with is named:

```bash
python3 - <<'EOF'
import zipfile, json
with zipfile.ZipFile("clip.mov.opi") as z:
    m = json.loads(z.read("manifest.json"))
m["machine_intelligence"][0]["facets"]["shots"][0]["confidence"] = 0.99
with zipfile.ZipFile("tampered.mov.opi", "w") as z:
    info = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
    z.writestr(info, json.dumps(m, indent=2) + "\n")
EOF
openpicture validate tampered.mov.opi; echo "exit=$?"
```

```text
invalid        tampered.mov.opi  (profile=core, opi=0, signatures=invalid)
  ok   readable: profile core, zip
  ok   opi version: 0
  ok   time: timecode.rate: 24/1
  ok   time: timecode.start: 00:00:00:00
  ok   time: spans: 1/1 consistent
  ok   facets: run[0] shots: 1 entry · stable
  FAIL run[0] invalid: signature does not verify
exit=1
```

## 8. Change the human layer

`editorial_annotations` is never signed. Add a rating and a label; the
signature on the machine layer is untouched:

```bash
openpicture annotate clip.mov.opi --set rating=5 --label scene=42B
openpicture validate clip.mov.opi | head -1
```

```text
{
  "notes": "first pass",
  "rating": 5,
  "labels": [
    {
      "name": "scene",
      "value": "42B",
      "created_by": "editor",
      "created_at": "2026-08-29T19:22:21+00:00",
      "span": null
    }
  ]
}
valid-signed   clip.mov.opi  (profile=core, opi=0, signatures=signed)
```

`annotate` refuses any edit that would reach outside the human layer.

## 9. Keep a tree healthy

`doctor` pairs every media file under a directory with its sidecar and
reports the state of each pair. Copy the two example files in — they ship
without their media, so they are `orphan` — and `clip.mov` is `paired`:

```bash
cp ../examples/A001_C001.mov.opi ../examples/A001_C001.mov.full.opi .
openpicture doctor . --verify-media
```

```text
.: 4 pairing(s)
  orphan             3
  paired             1
  orphan             A001_C001.mov.full.opi  no media by name
  orphan             A001_C001.mov.opi  no media by name
  orphan             tampered.mov.opi  no media by name
```

## Where next

- [Concepts](concepts/file-and-profiles.md) explain what each step did and why.
- [Producer workflow](build/producers.md) is the same path from code, with binary members.
- [The standalone validator](reference/validator.md) is one file you can hand to anyone who needs to check a `.opi` without installing anything.
