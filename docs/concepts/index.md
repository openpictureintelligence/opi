# Concepts

`.opi` is a small file format with a deliberately clear boundary: the media
stays where it is, while the intelligence about that media travels beside it.
These pages explain the pieces that make that boundary useful.

## Read in this order

| If you want to understand | Start here |
|---|---|
| What a `.opi` file is and how a reader finds it | [The file and its profiles](file-and-profiles.md) |
| How machine claims are grouped and verified | [Runs and signatures](runs-and-signatures.md) |
| What a person may change without invalidating machine work | [The human layer](human-layer.md) |
| How embeddings, stills and other binary data travel | [Members — embeddings and stills](members.md) |
| How shared and application-specific claims are represented | [Facets](facets.md) |

## The contract in one minute

1. A sidecar is named `<media>.opi` and sits beside the media it describes.
2. Its canonical physical form is a ZIP whose first member is
   `manifest.json`.
3. The manifest binds the sidecar to media with SHA-256, not with a filename
   alone.
4. Machine work is recorded as one run per producer and model pass.
5. Each run may be signed independently; unsigned is a valid, visible state.
6. `editorial_annotations` is a mutable human layer and is never signed.
7. Readers ignore fields they do not understand, but validate before trusting
   claims they will act on.

The [specification](../spec/index.md) is normative. These pages are the
explanation around it.
