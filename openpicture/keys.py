"""An append-only key log — the B15 recommendation, as an optional trust anchor.

**Status: recommendation, not ratified.** `DECISIONS.md` B15 is open. This
module implements the recommended shape so it can be evaluated, and nothing
in `sign.py` or `validate.py` depends on it: a `.opi` verifies without any
key log. What the log adds is *trust*: a signature can be valid (the math
checks) and still come from a key nobody vouches for. The log is where
someone vouches.

Shape: one JSON object per line, `{public_key, signer, added_at, note}`.
Lines are only ever appended. A key is never withdrawn, so a file signed
years ago stays verifiable *and* attributable; if a key is compromised, a
later line says so (`note`) rather than deleting history. Revocation
semantics beyond that are B15's to decide.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from . import ed25519, sign

__all__ = ["KeyEntry", "add", "load", "lookup", "trust_report", "TrustResult"]


@dataclass(frozen=True)
class KeyEntry:
    public_key: str
    signer: str
    added_at: str
    note: str = ""

    def as_dict(self) -> dict:
        return {"public_key": self.public_key, "signer": self.signer,
                "added_at": self.added_at, "note": self.note}


def _public_hex(key: str | bytes) -> str:
    """Accept a 32-byte public key or a 32-byte secret (derives the public)."""
    raw = bytes.fromhex(key) if isinstance(key, str) else bytes(key)
    if len(raw) != 32:
        raise ValueError("Ed25519 keys are 32 bytes")
    return raw.hex()


def add(log_path: str | os.PathLike, key: str | bytes, signer: str, *,
        note: str = "", from_secret: bool = False) -> KeyEntry:
    """Append one key. `from_secret=True` derives the public key from a secret
    so the secret itself never lands in the log."""
    public = ed25519.public_key(bytes.fromhex(key) if isinstance(key, str) else key).hex() \
        if from_secret else _public_hex(key)
    entry = KeyEntry(public, signer, datetime.now(timezone.utc).isoformat(timespec="seconds"), note)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.as_dict(), ensure_ascii=False) + "\n")
    return entry


def load(log_path: str | os.PathLike) -> list[KeyEntry]:
    entries: list[KeyEntry] = []
    if not os.path.exists(log_path):
        return entries
    with open(log_path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                entries.append(KeyEntry(d["public_key"], d["signer"], d["added_at"], d.get("note", "")))
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"{log_path}:{n}: malformed key log line: {exc}") from None
    return entries


def lookup(entries: list[KeyEntry], public_key: str) -> list[KeyEntry]:
    """Every line for a key, oldest first — later lines annotate earlier ones."""
    return [e for e in entries if e.public_key == public_key.lower()]


@dataclass
class TrustResult:
    index: int
    status: str          # valid | invalid | unsigned  (from sign.verify_manifest)
    trust: str           # trusted | unknown-signer | signer-mismatch | n/a
    signer: str | None = None
    public_key: str | None = None
    note: str = ""


def trust_report(manifest: Mapping, entries: list[KeyEntry]) -> list[TrustResult]:
    """Layer key-log trust over signature verification, per run.

    `trusted`: signature valid and the key is in the log under the same
    signer. `signer-mismatch`: key is in the log but under another signer
    (the file claims to be from someone the log says it is not). `unknown-
    signer`: valid signature, key not in the log. Unsigned or invalid runs
    get `n/a` — trust is a question about a valid signature.
    """
    vr = sign.verify_manifest(manifest)
    out: list[TrustResult] = []
    for r in vr.runs:
        if r.status != "valid":
            out.append(TrustResult(r.index, r.status, "n/a", r.signer, r.public_key))
            continue
        matches = lookup(entries, r.public_key or "")
        if not matches:
            out.append(TrustResult(r.index, r.status, "unknown-signer", r.signer, r.public_key))
        elif any(m.signer == r.signer for m in matches):
            note = "; ".join(m.note for m in matches if m.note)
            out.append(TrustResult(r.index, r.status, "trusted", r.signer, r.public_key, note))
        else:
            out.append(TrustResult(r.index, r.status, "signer-mismatch", r.signer, r.public_key,
                                   f"log says {', '.join(sorted({m.signer for m in matches}))}"))
    return out
