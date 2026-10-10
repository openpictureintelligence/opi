# Interoperability

`.opi` is the native form; everything else is a projection. The
specification anchors its names to existing standards wherever one has a
slot, so that egress is a rename rather than a mapping, and it claims
novelty only where no standard models the field.

## IPTC Video Metadata Hub

The IPTC Video Metadata Hub (VMH 1.7, "PVMD JSON") is the only JSON-native
neighbour with an official JSON Schema, and the natural egress target for
Tier 0 and Tier 1. Where VMH has a property, `.opi` uses its name:

| `.opi` | VMH |
|---|---|
| `files[].video_codec` | `videoCoding` |
| `timecode.rate` (rational) | `videoFrameRate` (number) |
| `duration_s` | `fileDuration` |
| `files[].width` / `height` | `frameSize` |
| transcript signals | `transcript`, `transcriptLinks` |
| OCR signals | `dataOnScreen` |
| person clusters | `personsShown` (unnamed until labelled) |
| diarization | `personsHeard` |
| `camera` | `recordingDevice` |
| clearance `face` flag → egress | `modelReleaseStatus` (a controlled term, never a boolean) |
| clearance `artwork` / `signage` → egress | `propertyReleaseStatus` |
| run `producer` / `model_version` → egress | `aISystemUsed`, `digitalSourceType` |

Shot size has a *slot* in VMH but no vocabulary; `.opi` keeps its own
ordered CV and maps to IPTC Scene NewsCodes on egress.

## MPEG-7

ISO/IEC 15938-3 (2002) is the vocabulary source for kinematics: the eight
`CameraMotion` verbs are `.opi`'s base enum, and `MotionActivity` is the
lineage of the energy curve. MPEG-7 is XML and saw no adoption in working
post-production; `.opi` reuses the words and changes the delivery.

## EBUCore and PBCore

Both are XML-only schemas with no official JSON serialization. Egress to
either is an XML (or RDF) document built from the manifest, not a rename.
Tier 0 maps cleanly; Tier 1 mostly; Tier 2 has no equivalent elements.

## C2PA

C2PA is an **export bridge, never a requirement.** C2PA 2.x requires X.509
certificates and a certificate authority — a burden on every solo editor
and small post house that `.opi`'s raw Ed25519 keys deliberately avoid.
For clients who contractually need it, a producer can emit C2PA assertions
from `.opi` runs and a BMFF hash binding from the media; C2PA also defines
`.c2pa` sidecar discovery, which sits beside a `.opi` without conflict.
`.opi`'s differentiator is the intelligence layer, the mutable human layer
and provenance without a CA — not video provenance as such.

## SMPTE

Camera and lens telemetry in MXF (RDD 18, RDD 55, RIS-OSVP) records what
the *sensor* did — gyro rates, focal length. `.opi` records editorial
semantics — a slow push-in. Different abstraction layers, not competing
ones.

## ASC MHL and checksum tools

`.opi` binds by SHA-256, which every OS can compute. Offload tools (Hedge,
Silverstack) emit XXH64BE in their MHL manifests; a producer may add an
`xxh64be` field to `files[]` so the binding cross-checks the set's MHL for
free. The media is never touched, so an MHL taken before the producer ran
still verifies after.

## Media types and UTI

Proposed and unregistered, pending the schema freeze:
`application/vnd.openpicture.opi+zip` (RFC 6839 structured suffix) for the
file, `application/vnd.openpicture.opi+json` for the internal form, macOS
UTI `org.openpicture.opi` conforming to `public.zip-archive`.
