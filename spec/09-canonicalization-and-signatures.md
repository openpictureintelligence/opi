## 9. Canonicalization and signatures

### 9.1 Canonicalization

Signed bytes are the **RFC 8785 (JCS)** canonical form of a JSON value:
object keys sorted by UTF-16 code unit, no insignificant whitespace,
ECMAScript number formatting, minimal string escaping, UTF-8.

`json.dumps(sort_keys=True, separators=(",", ":"))` is **not** JCS — it
sorts by code point, formats `1e+16` where JCS writes
`10000000000000000`, and emits `1.0` where JCS writes `1`. Implementers MUST
use a real RFC 8785 canonicalizer. The reference implementation's
`openpicture/jcs.py` is one, tested against the RFC's Appendix B vectors.

### 9.2 Payload

The payload of a run signature is the JCS canonicalization of:

```json
{"media_binding": <manifest.media_binding>, "run": <the run object with its "signature" key removed>}
```

— exactly two keys, in canonical (sorted) order, with `media_binding` taken
from the manifest as-is (or `null` if absent — though signing without a
binding is an error for writers). Nothing else in the manifest is covered:
not the envelope, not other runs, not `editorial_annotations`.

Consequences: a run signature asserts *this intelligence, about this media*.
Appending a second run does not disturb the first. Editing the human layer
does not disturb anything.

### 9.3 Signature entry

Placed at `run.signature`:

| Key | Type | Value |
|---|---|---|
| `role` | string | Default `"machine_producer"`. Informative. |
| `signer` | string | Who signed — a URN or similar stable identifier. |
| `algorithm` | string | MUST be `"Ed25519"`. |
| `public_key` | string | 64 lowercase hex characters: the raw 32-byte Ed25519 public key (RFC 8032). |
| `signed_at` | string | RFC 3339 timestamp. Informative. |
| `signature` | string | Standard base64 (with padding) of the raw 64-byte Ed25519 signature over the §9.2 payload. |

Keys are raw RFC 8032 encodings — no PEM, no X.509. **The public key hex is
the key id**; there is no separate `key_id` field.

**Key policy (decision B15, 2026-08-29): an append-only key log.** A
producer publishes every public key it has ever signed with, each with the
signer URN, the date added and an optional note, and **never withdraws
one** — a key that is retired is marked, not removed, so every file it
signed stays verifiable forever. Verifiers that hold a producer's log
report a run as `trusted` (key present) or `unknown-signer` (absent) in
addition to `valid`/`invalid`; a valid signature by an unknown key is still
a valid signature. Compromise is handled by marking the key and re-signing
affected files with a new one; it is never handled by deleting history. The
reference implementation's `keys.py` is the log format (JSON Lines, one key
per line).

### 9.4 Verification

For each run `i` in `machine_intelligence`:

1. If the run is not an object → `invalid`.
2. If `signature` is absent → `unsigned`.
3. If `signature` is not an object, or `algorithm ≠ "Ed25519"`, or
   `public_key` is not valid hex, or `signature` is not valid base64 →
   `invalid` with a reason.
4. Compute the §9.2 payload. Verify with Ed25519 (RFC 8032 §5.1.7; the
   reference implementation uses the RFC's own reference algorithm and
   rejects `s ≥ L`). Success → `valid`; failure → `invalid`.

File-level status:

| Status | Condition |
|---|---|
| `signed` | every run `valid` |
| `partial` | at least one `valid`, none `invalid`, some `unsigned` |
| `unsigned` | no run `valid`, none `invalid` (including no runs at all) |
| `invalid` | any run `invalid` |

A verifier MUST report per run — which run, which signer, which reason —
and MUST NOT collapse `partial` into `signed`. **Unsigned is valid**: a
file with no signatures is honest; a file with a bad one is not.

### 9.5 Re-signing

Signing a run replaces that run's `signature`. There is one signer per run
— the producer that made it. Another producer's work is another run.
