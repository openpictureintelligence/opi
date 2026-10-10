# Members — embeddings and stills

A **Full** file carries binary payloads as ZIP members beside
`manifest.json`. Three rules make them useful rather than merely present.

## Every member is declared, hashed and owned by a run

A member other than the manifest must appear in some run's `attachments`
with its SHA-256, size and media type:

```json
"attachments": {
  "embeddings/siglip-so400m.safetensors": {"sha256": "e3b0…", "size": 8388672,
                                            "media_type": "application/x-safetensors"},
  "keyframes/shot_0000012.webp": {"sha256": "8f43…", "size": 7636, "media_type": "image/webp",
                                  "width": 512, "height": 288, "frame": 12}
}
```

A ZIP cannot sign its own directory from inside itself. Declaring members
in the signed run is how bytes outside the manifest get under a signature:
an undeclared member, a declared-but-absent member, or a hash mismatch all
make the file invalid. Two runs declaring the same member must agree on it.

## Aligned, uncompressed, mappable

Members named `*.bin` or `*.safetensors` are STORED (not deflated) with
their data start padded to a **64-byte boundary** using a ZIP extra field
in the local header — the mechanism USDZ uses. A reader computes the offset
from the local header and hands a `memoryview` over an `mmap` to a tensor
library with no copy.

```python
sc = openpicture.load("clip.mov.opi")
view = sc.map_member("embeddings/siglip-so400m.safetensors")   # zero-copy
```

Members over 2 GiB are forbidden: Python's ZIP64 record would land after
the padding and break the alignment, and nothing that large belongs in a
sidecar.

## Embeddings: safetensors layout

One file per embedding model, at `embeddings/<model-id>.safetensors`,
in the safetensors layout: an 8-byte little-endian header length, a JSON
header with `dtype`/`shape`/`data_offsets` per tensor and `__metadata__`
strings, then a contiguous buffer. The reference implementation pads the
header with spaces so the buffer — and the first tensor — is 64-byte aligned
*in the file*, not only within the member.

Default dtype F16, L2-normalized; F32, I8/U8 permitted with scale and
zero-point tensors recorded beside `vectors`. The required `__metadata__`
keys are `opi.model`, `opi.model_version`, `opi.dim`, `opi.dtype`,
`opi.normalized` (`l2` or `none`) and `opi.scope`. A `facets.embeddings`
entry in the run says what the tensors are: model, dimension, dtype,
whether per shot, segment or asset.

```python
from openpicture import embeddings
data = embeddings.pack_vectors(vectors, 768, model="siglip-so400m",
                               model_version="1")
```

## Keyframe stills

`keyframes/<prefix>_<frame:07d>.webp` — WebP, lossy q≈80, 512 px on the
long edge, sRGB, metadata stripped. JPEG and PNG are accepted where a
consumer requires them. `openpicture.keyframes.describe()` reads dimensions
and media type from the bytes so the declaration can be trusted.

!!! warning "Keyframes are frames of the media"
    A still is a low-resolution copy of the picture itself, not derived
    metadata. Producers operating under a data-egress policy treat
    embedding keyframes as a distinct egress class above transcripts and
    labels — the reference producer calls it `FRAMES`, default off — and a
    sidecar carrying stills should never leave the premises without the
    footage owner's explicit consent. The format permits keyframes; policy
    decides when they travel.

## Extensions

`extensions/<reverse.dns>/…` holds namespaced vendor members under the
same declare-and-hash rule. Readers ignore extensions they do not know.

*Normative text: specification §4 and §7.5.*
