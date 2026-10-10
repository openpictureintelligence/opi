## Appendix B — Test vectors

Produced by running the reference implementation. A third-party
implementation that reproduces the payload bytes and the signature is
interoperable at the signing layer.

**Secret key** (RFC 8032 §7.1 TEST 1, hex):

```
9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60
```

**Public key** (hex): `d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a`

**Manifest before signing** (any whitespace; key order irrelevant to the payload):

```json
{
  "opi": 0,
  "profile": "core",
  "media_binding": {
    "files": [
      {"role": "original", "name": "clip.mov", "size": 3,
       "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"}
    ]
  },
  "machine_intelligence": [
    {"run_id": "r1", "producer": "example", "model_version": "1",
     "facets": {"shots": [{"idx": 0, "confidence": 0.5}]}}
  ],
  "editorial_annotations": {"notes": "test"}
}
```

(`ba7816bf…15ad` is SHA-256 of the three bytes `abc`.)

**Canonical payload** for run 0 (§9.2), as text — 255 bytes, no newline:

```
{"media_binding":{"files":[{"name":"clip.mov","role":"original","sha256":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","size":3}]},"run":{"facets":{"shots":[{"confidence":0.5,"idx":0}]},"model_version":"1","producer":"example","run_id":"r1"}}
```

Same payload as hex:

```
7b226d656469615f62696e64696e67223a7b2266696c6573223a5b7b226e616d65223a22636c69702e6d6f76222c22726f6c65223a226f726967696e616c222c22736861323536223a2262613738313662663866303163666561343134313430646535646165323232336230303336316133393631373761396362343130666636316632303031356164222c2273697a65223a337d5d7d2c2272756e223a7b22666163657473223a7b2273686f7473223a5b7b22636f6e666964656e6365223a302e352c22696478223a307d5d7d2c226d6f64656c5f76657273696f6e223a2231222c2270726f6475636572223a226578616d706c65222c2272756e5f6964223a227231227d7d
```

**Signature** (Ed25519 over the payload, base64):

```
9W1V3HZU8ydlimgdjJdjksYcWtmvpq8/TIuU0AmEeWsD0m6fZ0jMzq3kVEif1JryqJq0yoXofCmWKgiv4DmmCw==
```

**Resulting signature entry** (with a fixed `signed_at`; `signed_at`, `role`
and `signer` are not part of the payload and do not affect the signature):

```json
"signature": {
  "role": "machine_producer",
  "signer": "urn:example:producer",
  "algorithm": "Ed25519",
  "public_key": "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
  "signed_at": "2026-08-29T00:00:00+00:00",
  "signature": "9W1V3HZU8ydlimgdjJdjksYcWtmvpq8/TIuU0AmEeWsD0m6fZ0jMzq3kVEif1JryqJq0yoXofCmWKgiv4DmmCw=="
}
```

Verification of the resulting manifest MUST yield status `signed`. Changing
`confidence` to `0.51` MUST yield `invalid` for run 0; changing
`editorial_annotations.notes` MUST leave the status `signed`.

**JCS checks** (RFC 8785 Appendix B, a selection an implementer should pass):
`1e21` → `1e+21`; `1e-7` → `1e-7`; `0.000001` → `0.000001`; `1.0` → `1`;
`333333333.33333329` → `333333333.3333333`; keys `["€", "\U0001f600",
"～"]` sort as `"€"`, `"\U0001f600"`, `"～"` (UTF-16 order, not
code-point order).
