# Why `.opi`

## The problem

Every serious tool that looks at footage builds an index of it: shot
boundaries, transcripts, faces, objects, sometimes embeddings. Every one of
those indexes lives inside the tool — an application database, a MAM's
schema, a cloud tenant. The footage belongs to the client. The
understanding of the footage belongs to the vendor, and it evaporates when
the subscription ends, the tool is retired, or the archive moves.

That is a strange place for expensive knowledge to live. Analysing video is
the most costly thing a model can do, and the result is stored where it can
be used by exactly one program.

There is also a second gap. Nearly everything a machine says about footage
today is **content-descriptive**: what is in the frame, who is speaking,
what words are on screen. Almost nothing describes **how the shot behaves
as a piece of film** — its size, how the camera moves, its framing, whether
it can cut to the shot before it, whether it is legally usable. That is the
layer an editor works in, and it is the layer an automated assembly needs
to be watchable rather than merely correct.

## This has been tried

Researchers have argued for machine-readable film grammar since the early
1990s (Davenport 1991; Davis, *Media Streams*, 1993; Adams, Dorai and
Venkatesh formalised the energy curve in 2002). ISO standardised much of it:
**MPEG-7** (ISO/IEC 15938-3, 2002) defines a `CameraMotion` descriptor with
the eight verbs — fixed, pan, tilt, roll, zoom, dolly, track, boom — a
`MotionActivity` descriptor, and confidence attributes.

MPEG-7 failed on adoption. It was XML with a punishing schema, it had no
normative per-field confidence, no signatures, no story for how a file
travels with the media it describes, and no working editor ever saw one.
The ideas were right and the delivery was wrong.

`.opi` reuses the vocabulary that survived — MPEG-7's camera-motion verbs
are the base enum — and changes the delivery.

## What an open, signed, media-bound sidecar changes

**The understanding travels with the footage.** Same directory, same
basename, bound by checksum. Copy the drive, hand it to another post house,
archive it to tape: the second layer goes along, and any reader can confirm
it describes the bytes in hand.

**It is portable across tools.** A JSON manifest in a ZIP, with a published
specification and a copyable validator. An NLE, a MAM, a script, or a
language model with filesystem access can all read it. No API, no account,
no vendor.

**Claims are attributable and verifiable.** Every run names its producer and
model version and is signed by that producer. A verifier reports, run by
run, what it could verify — and *unsigned* is an honest, visible state, not
a failure.

**People can still edit it.** The human layer is unsigned by design. Ratings,
notes, scene numbers, a MAM's tags — the owner's, changeable at will,
preserved when the machine layer is regenerated.

**Expensive passes become assets.** Once a clip carries its embeddings and
keyframes, improving retrieval no longer means re-reading terabytes of
video; it means re-reading megabytes of sidecars. A model upgrade is a
re-run over the second layer, not the first.

**It gets more valuable as models improve, not less.** Answering questions
by re-watching an archive every time stays economically absurd as prices
fall, because the indexed alternative falls with them. Per-query models do
not hold the corpus; they see what they are sent. Unreleased and NDA
material cannot be sent to a hosted model at all. And model output cannot
be verified after the fact — a signed, provenance-bound, versioned claim
can. When understanding becomes abundant, the scarce good is understanding
that is durable, verified, portable and cheap to query. That is the file.

## What `.opi` is not

- **Not encryption.** The file is readable by anyone who can read the bytes.
  Signatures give ownership and provenance without lock-in; encryption
  would destroy the plain readability — a ZIP and a JSON file — that makes the format useful.
- **Not a MAM, an NLE, or an index.** It is what those tools read and write.
  A database built from a tree of `.opi` files is a cache, reconstructible
  by walking the tree.
- **Not a model.** The format says nothing about how a facet was computed,
  only who computed it, with what, and how confident they were. Any
  producer can fill it; the specification only constrains the shape of the
  claims and, for sensitive facets, what may be claimed.
- **Not a certification.** Facets about people and rights — minors, faces,
  logos, licensed music — are review flags with mandatory human sign-off,
  never determinations. The format forbids accuracy claims travelling in
  the file for those facets. See the specification, §10.3.
- **Not a vendor format.** The name is descriptive, the specification is
  Apache-2.0, and the reference implementation is standard-library Python.
  The steward today is [named in the governance page](contribute/governance.md); the
  intent is that the format outlives any one producer.
