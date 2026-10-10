"""Signing: per producer run, binding each run to the media it describes.

A `.opi` manifest is partitioned. `machine_intelligence` is a **list of
producer runs** — one model pass each — and every run carries its own
signature. `editorial_annotations` is a human's block and is never signed,
so an editor can change a tag without "corrupting" the file. Signatures
live *inside* the manifest, so the Core file and a Full container's
`manifest.json` stay identical and `unzip -p` shows them.

Why per run and not one signature over the whole machine block: a second
model pass three weeks later appends a run. If one signature covered the
list, that append would void the first producer's signature — the exact
failure the partition exists to prevent. Per-run signatures let a verifier
say "run 0 by producer A verified; run 1 by producer B verified" after any
number of passes, and a run can name its `parent` to record lineage.

The payload of a run signature is the RFC 8785 canonical form of
`{"media_binding": <manifest.media_binding>, "run": <run without its
signature>}`. Including `media_binding` means every run signature also
asserts *which media* the intelligence describes. An unsigned run is
*valid*; the verifier reports `unsigned`, never `invalid`.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping

from . import ed25519, jcs

__all__ = [
    "ALGORITHM",
    "UNSIGNED_BLOCKS",
    "run_payload",
    "sign_run",
    "verify_manifest",
    "RunResult",
    "VerifyReport",
]

ALGORITHM = "Ed25519"
UNSIGNED_BLOCKS = ("editorial_annotations",)
_SIG_KEY = "signature"


def run_payload(manifest: Mapping, run: Mapping) -> bytes:
    """The bytes a run's signature is computed over."""
    body = {k: v for k, v in run.items() if k != _SIG_KEY}
    return jcs.canonicalize({"media_binding": manifest.get("media_binding"), "run": body})


def sign_run(
    manifest: dict,
    index: int,
    secret: bytes,
    *,
    signer: str,
    role: str = "machine_producer",
    signed_at: str | None = None,
) -> dict:
    """Sign `manifest["machine_intelligence"][index]` in place; return the entry.

    Re-signing replaces that run's signature — there is one signer per run,
    the producer that made it. A different producer's work is a different
    run.
    """
    runs = manifest.get("machine_intelligence")
    if not isinstance(runs, list) or not (0 <= index < len(runs)):
        raise IndexError(f"no run at machine_intelligence[{index}]")
    if "media_binding" not in manifest:
        raise ValueError("cannot sign a run without media_binding: nothing to bind to")
    run = runs[index]
    run.pop(_SIG_KEY, None)
    entry = {
        "role": role,
        "signer": signer,
        "algorithm": ALGORITHM,
        "public_key": ed25519.public_key(secret).hex(),
        "signed_at": signed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "signature": base64.b64encode(ed25519.sign(secret, run_payload(manifest, run))).decode("ascii"),
    }
    run[_SIG_KEY] = entry
    return entry


def sign_all(manifest: dict, secret: bytes, *, signer: str, role: str = "machine_producer") -> int:
    """Sign every unsigned run with one key. Returns how many were signed."""
    n = 0
    for i, run in enumerate(manifest.get("machine_intelligence") or []):
        if _SIG_KEY not in run:
            sign_run(manifest, i, secret, signer=signer, role=role)
            n += 1
    return n


@dataclass
class RunResult:
    index: int
    run_id: str | None
    producer: str | None
    status: str          # "valid" | "invalid" | "unsigned"
    signer: str | None = None
    public_key: str | None = None
    reason: str = ""


@dataclass
class VerifyReport:
    """`status`: `signed` (every run valid), `unsigned` (no run signed),
    `partial` (some signed and all of those valid), `invalid` (any fails)."""
    status: str
    runs: list[RunResult] = field(default_factory=list)
    reason: str = ""


def verify_manifest(manifest: Mapping) -> VerifyReport:
    runs = manifest.get("machine_intelligence")
    if runs is None:
        return VerifyReport("unsigned", reason="no machine_intelligence")
    if not isinstance(runs, list):
        return VerifyReport("invalid", reason="machine_intelligence must be a list of runs")
    results = [_check(manifest, i, r) for i, r in enumerate(runs)]
    statuses = {r.status for r in results}
    if "invalid" in statuses:
        status = "invalid"
    elif statuses == {"valid"}:
        status = "signed"
    elif "valid" in statuses:
        status = "partial"
    else:
        status = "unsigned"
    return VerifyReport(status, results)


def _check(manifest: Mapping, i: int, run) -> RunResult:
    if not isinstance(run, dict):
        return RunResult(i, None, None, "invalid", reason="run is not an object")
    rid, producer = run.get("run_id"), run.get("producer")
    entry = run.get(_SIG_KEY)
    if entry is None:
        return RunResult(i, rid, producer, "unsigned")
    if not isinstance(entry, dict):
        return RunResult(i, rid, producer, "invalid", reason="signature is not an object")
    signer = entry.get("signer")
    if entry.get("algorithm") != ALGORITHM:
        return RunResult(i, rid, producer, "invalid", signer, reason=f"unsupported algorithm {entry.get('algorithm')!r}")
    try:
        public = bytes.fromhex(entry["public_key"])
        sig = base64.b64decode(entry["signature"], validate=True)
    except (KeyError, ValueError, TypeError) as exc:
        return RunResult(i, rid, producer, "invalid", signer, reason=f"malformed key or signature: {exc}")
    ok = ed25519.verify(public, run_payload(manifest, run), sig)
    return RunResult(i, rid, producer, "valid" if ok else "invalid", signer, entry.get("public_key"),
                     "" if ok else "signature does not verify")
