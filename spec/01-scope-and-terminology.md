## 1. Scope and terminology

This specification defines: the on-disk forms of a `.opi` file, the JSON
manifest it carries, how a manifest is bound to media, how producer runs are
signed and verified, and what conforming writers, readers and validators MUST
do. It does **not** define the meaning of intelligence facets (shot sizes,
transcript segments, embeddings); those are open in version 0 and will be
frozen separately.

The key words MUST, MUST NOT, REQUIRED, SHALL, SHOULD, SHOULD NOT, MAY are to
be interpreted as in RFC 2119 / RFC 8174.

| Term | Meaning |
|---|---|
| **media** | The file(s) the sidecar describes — a camera master, a wildtrack, a proxy. Never modified. |
| **sidecar** | The `.opi` file. |
| **manifest** | The JSON object at the heart of a sidecar. In Core it *is* the file; in Full it is the `manifest.json` member. |
| **profile** | `core` (plain JSON) or `full` (ZIP container). |
| **producer** | Software that computes intelligence about media — a shot detector, an ASR model. |
| **run** | One producer pass over one media asset: a self-contained, individually signed unit in `machine_intelligence`. |
| **machine layer** | `media_binding` + `machine_intelligence`. Signed. |
| **human layer** | `editorial_annotations`. Never signed; freely editable. |
| **member** | A file inside a Full container other than `manifest.json`. |
| **JCS** | RFC 8785 JSON Canonicalization Scheme. |
