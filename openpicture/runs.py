"""The run model — spec chapter 7.

A **run** is one producer pass over one piece of media. Its identity is the
tuple `(producer, model_version, media sha256)`, and `run_id` is *derived*
from that tuple so every producer computes the same id for the same work
and a validator can check it. Everything else in this module follows from
that: replacement in place, lineage, "which run is current", and the
structural checks a validator applies to the `machine_intelligence` array.

Nothing here signs or verifies; `sign.py` does that. Nothing here touches
the container; `validate.py` composes these checks with the rest.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from . import jcs

__all__ = [
    "RUN_ID_LENGTH",
    "PRODUCER_RE",
    "FACET_NAME_RE",
    "EGRESS_CLASSES",
    "CONFIDENCE_SCALES",
    "HOST_FIELDS",
    "run_id",
    "new_run",
    "media_sha256",
    "current_runs",
    "lineage",
    "checks",
]

RUN_ID_LENGTH = 32  # hex chars: the first 128 bits of the digest, always
PRODUCER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}(:[a-z0-9][a-z0-9._-]{0,63})+$")
FACET_NAME_RE = re.compile(r"^(x-[a-z0-9]+\.)?[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
EGRESS_CLASSES = ("none", "derived", "frames", "full_media")
CONFIDENCE_SCALES = ("unit", "bp")
# SPEC §7.2: `host` is a class of machine, never an instance. The vocabularies
# are deliberately coarse — anything finer would identify a person's laptop
# inside a signature that cannot afterwards be edited (§13).
HOST_OS = ("macos", "linux", "windows", "other")
HOST_ARCH = ("arm64", "x86_64", "other")
HOST_ACCELERATOR = ("cpu", "cuda", "metal", "rocm", "other")
HOST_FIELDS = {"os": HOST_OS, "arch": HOST_ARCH, "accelerator": HOST_ACCELERATOR}
_MAX_MODEL_NAME = 256
REQUIRED = ("run_id", "producer", "model_version", "facets")
_MAX_MODEL_VERSION = 128


# ── identity ───────────────────────────────────────────────────────────


def run_id(producer: str, model_version: str, sha256: str) -> str:
    """The derived run identifier.

    `lowercase_hex(SHA-256(JCS({"model_version": …, "producer": …,
    "sha256": …})))[:32]`. The three inputs are the run's identity; the JCS
    encoding fixes key order and escaping so the digest is the same in
    every language. Exactly 32 hex characters — never longer, never shorter.
    """
    if not isinstance(sha256, str) or not _SHA256_RE.match(sha256):
        raise ValueError("sha256 must be 64 lowercase hex characters")
    payload = jcs.canonicalize(
        {"producer": producer, "model_version": model_version, "sha256": sha256}
    )
    return hashlib.sha256(payload).hexdigest()[:RUN_ID_LENGTH]


def media_sha256(manifest: Mapping) -> str | None:
    """The sha256 of the `original` file in `media_binding`, if present.

    The first `files[]` entry with role `original` (role defaults to
    `original`) is the media a run is identified against.
    """
    mb = manifest.get("media_binding")
    if not isinstance(mb, dict):
        return None
    for f in mb.get("files") or []:
        if isinstance(f, dict) and f.get("role", "original") == "original":
            sha = f.get("sha256")
            return sha.lower() if isinstance(sha, str) else None
    return None


def new_run(
    producer: str,
    model_version: str,
    sha256: str,
    *,
    facets: Mapping[str, Any] | None = None,
    generator: str | None = None,
    generated_at: str | None = None,
    supersedes: str | None = None,
    depends_on: Iterable[str] | None = None,
    egress: str | None = None,
    confidence_scale: str = "unit",
    attachments: Mapping[str, Any] | None = None,
) -> dict:
    """A run object with a correctly derived `run_id`."""
    if not PRODUCER_RE.match(producer):
        raise ValueError(f"producer {producer!r} does not match {PRODUCER_RE.pattern}")
    if not model_version or len(model_version) > _MAX_MODEL_VERSION:
        raise ValueError("model_version must be 1–128 characters")
    if egress is not None and egress not in EGRESS_CLASSES:
        raise ValueError(f"egress must be one of {EGRESS_CLASSES}")
    if confidence_scale not in CONFIDENCE_SCALES:
        raise ValueError(f"confidence_scale must be one of {CONFIDENCE_SCALES}")
    run: dict[str, Any] = {
        "run_id": run_id(producer, model_version, sha256),
        "producer": producer,
        "model_version": model_version,
    }
    if generator is not None:
        run["generator"] = generator
    run["generated_at"] = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if supersedes is not None:
        run["supersedes"] = supersedes
    if depends_on:
        run["depends_on"] = list(depends_on)
    if egress is not None:
        run["egress"] = egress
    if confidence_scale != "unit":
        run["confidence_scale"] = confidence_scale
    run["facets"] = dict(facets or {})
    if attachments:
        run["attachments"] = dict(attachments)
    return run


# ── which run is current ───────────────────────────────────────────────


def _runs(manifest: Mapping) -> list[dict]:
    runs = manifest.get("machine_intelligence")
    return [r for r in runs if isinstance(r, dict)] if isinstance(runs, list) else []


def current_runs(manifest: Mapping) -> list[dict]:
    """One run per producer: the one nothing else supersedes.

    When several runs share a `producer`, a run named by another run's
    `supersedes` is not current. If more than one candidate remains, the
    latest `generated_at` wins; with no timestamps, the last one in the
    array does. Order of the result follows the manifest.
    """
    runs = _runs(manifest)
    superseded = {r.get("supersedes") for r in runs if isinstance(r.get("supersedes"), str)}
    by_producer: dict[str, list[tuple[int, dict]]] = {}
    for i, r in enumerate(runs):
        if r.get("run_id") in superseded:
            continue
        by_producer.setdefault(str(r.get("producer")), []).append((i, r))
    chosen: list[tuple[int, dict]] = []
    for candidates in by_producer.values():
        best = max(candidates, key=lambda ir: (_ts(ir[1].get("generated_at")), ir[0]))
        chosen.append(best)
    chosen.sort(key=lambda ir: ir[0])
    return [r for _, r in chosen]


def _ts(value: Any) -> float:
    if not isinstance(value, str):
        return float("-inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def lineage(manifest: Mapping, rid: str) -> list[dict]:
    """The chain a run replaces: the run, then what it supersedes, and so on.

    Stops at a missing target or a cycle. The first element is the run
    named by `rid`; an unknown `rid` yields an empty list.
    """
    by_id = {r.get("run_id"): r for r in _runs(manifest) if isinstance(r.get("run_id"), str)}
    chain: list[dict] = []
    seen: set[str] = set()
    cur = rid
    while isinstance(cur, str) and cur in by_id and cur not in seen:
        seen.add(cur)
        chain.append(by_id[cur])
        cur = by_id[cur].get("supersedes")
    return chain


# ── validator checks ───────────────────────────────────────────────────


def _host_checks(tag: str, host: Any) -> list[tuple[str, bool, str]]:
    """SPEC §7.2/§7.8: `host` names a class of machine, from fixed vocabularies.

    Rejecting the unknown value is the whole point: an implementation that
    puts a hostname in `arch` should hear about it before the run is signed,
    because afterwards the only way to remove it is to destroy the signature.
    """
    if host is None:
        return []
    if not isinstance(host, dict):
        return [(f"{tag} host", False, "must be an object")]
    bad = []
    for key, value in host.items():
        allowed = HOST_FIELDS.get(key)
        if allowed is None:
            bad.append(f"unknown key {key!r}")
        elif value not in allowed:
            bad.append(f"{key}={value!r} not one of {allowed}")
    return [(f"{tag} host", not bad, "" if not bad else "; ".join(bad))]


def _model_checks(tag: str, models: Any) -> list[tuple[str, bool, str]]:
    """SPEC §7.2/§7.8: `models` is a list of {name, sha256} naming real files."""
    if models is None:
        return []
    if not isinstance(models, list):
        return [(f"{tag} models", False, "must be an array")]
    bad = []
    for j, entry in enumerate(models):
        if not isinstance(entry, dict):
            bad.append(f"[{j}] is not an object")
            continue
        name, digest = entry.get("name"), entry.get("sha256")
        if not isinstance(name, str) or not 0 < len(name) <= _MAX_MODEL_NAME:
            bad.append(f"[{j}] name must be 1-{_MAX_MODEL_NAME} characters")
        if not isinstance(digest, str) or not _SHA256_RE.match(digest):
            bad.append(f"[{j}] sha256 must be 64 lowercase hex characters")
    return [(f"{tag} models", not bad, "" if not bad else "; ".join(bad))]


def checks(manifest: Mapping) -> list[tuple[str, bool, str]]:
    """Structural checks for `machine_intelligence`, as (name, ok, detail).

    Composable into `validate.Report`; each tuple is one row. A manifest
    with no `machine_intelligence` passes with a single informational row.
    """
    out: list[tuple[str, bool, str]] = []
    raw = manifest.get("machine_intelligence")
    if raw is None:
        return [("runs", True, "no machine_intelligence")]
    if not isinstance(raw, list):
        return [("runs", False, "machine_intelligence must be an array")]
    sha = media_sha256(manifest)
    ids: dict[str, int] = {}
    members: dict[str, int] = {}
    for i, run in enumerate(raw):
        tag = f"run[{i}]"
        if not isinstance(run, dict):
            out.append((tag, False, "run is not an object"))
            continue
        missing = [k for k in REQUIRED if k not in run]
        out.append((f"{tag} required", not missing, "" if not missing else f"missing {missing}"))
        producer = run.get("producer")
        ok = isinstance(producer, str) and bool(PRODUCER_RE.match(producer))
        out.append((f"{tag} producer", ok, "" if ok else f"{producer!r} must match {PRODUCER_RE.pattern}"))
        mv = run.get("model_version")
        ok = isinstance(mv, str) and 0 < len(mv) <= _MAX_MODEL_VERSION
        out.append((f"{tag} model_version", ok, "" if ok else "non-empty string, at most 128 chars"))
        rid = run.get("run_id")
        if isinstance(rid, str):
            if rid in ids:
                out.append((f"{tag} run_id unique", False, f"duplicate of run[{ids[rid]}]"))
            else:
                ids[rid] = i
            if isinstance(producer, str) and isinstance(mv, str) and sha:
                expected = run_id(producer, mv, sha)
                ok = rid == expected
                out.append((f"{tag} run_id derived", ok, "" if ok else f"expected {expected}"))
            else:
                ok = len(rid) == RUN_ID_LENGTH and all(c in "0123456789abcdef" for c in rid)
                out.append((f"{tag} run_id form", ok, "" if ok else "32 lowercase hex chars"))
        else:
            out.append((f"{tag} run_id", False, "missing or not a string"))
        ga = run.get("generated_at")
        if ga is not None:
            ok = isinstance(ga, str) and bool(_RFC3339_RE.match(ga))
            out.append((f"{tag} generated_at", ok, "" if ok else "RFC 3339 date-time"))
        eg = run.get("egress")
        if eg is not None:
            out.append((f"{tag} egress", eg in EGRESS_CLASSES, "" if eg in EGRESS_CLASSES else f"one of {EGRESS_CLASSES}"))
        cs = run.get("confidence_scale", "unit")
        out.append((f"{tag} confidence_scale", cs in CONFIDENCE_SCALES, "" if cs in CONFIDENCE_SCALES else f"one of {CONFIDENCE_SCALES}"))
        out.extend(_host_checks(tag, run.get("host")))
        out.extend(_model_checks(tag, run.get("models")))
        out.extend(_facet_checks(tag, run.get("facets"), cs))
        att = run.get("attachments")
        if att is not None:
            if not isinstance(att, dict):
                out.append((f"{tag} attachments", False, "must be an object"))
            else:
                for name in att:
                    if name in members:
                        out.append((f"{tag} attachment {name}", False, f"already declared by run[{members[name]}]"))
                    else:
                        members[name] = i
        dep = run.get("depends_on")
        if dep is not None and not (isinstance(dep, list) and all(isinstance(d, str) for d in dep)):
            out.append((f"{tag} depends_on", False, "array of run_id strings"))
    # references resolve — after all ids are known
    for i, run in enumerate(raw):
        if not isinstance(run, dict):
            continue
        sup = run.get("supersedes")
        if sup is not None:
            ok = isinstance(sup, str) and (sup in ids or sup != run.get("run_id"))
            if sup == run.get("run_id"):
                ok = False
            out.append((f"run[{i}] supersedes", ok, "" if ok else "must name another run_id (may be absent from this manifest, never itself)"))
        for d in run.get("depends_on") or []:
            if isinstance(d, str) and d not in ids:
                out.append((f"run[{i}] depends_on {d[:8]}…", False, "not present in this manifest"))
    return out


def _facet_checks(tag: str, facets: Any, scale: str) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    if facets is None:
        return out
    if not isinstance(facets, dict):
        return [(f"{tag} facets", False, "must be an object")]
    for name, entries in facets.items():
        fname = f"{tag} facet {name}"
        if not FACET_NAME_RE.match(name):
            out.append((fname, False, f"name must match {FACET_NAME_RE.pattern}"))
            continue
        if not isinstance(entries, list):
            out.append((fname, False, "must be an array of entries"))
            continue
        bad = 0
        for e in entries:
            if not isinstance(e, dict) or "confidence" not in e or not _confidence_ok(e["confidence"], scale):
                bad += 1
        out.append((fname, bad == 0, "" if bad == 0 else f"{bad} entr{'y' if bad == 1 else 'ies'} without a valid confidence ({scale})"))
    return out


def _confidence_ok(value: Any, scale: str) -> bool:
    if value is None:  # present but not estimated — honest, and allowed
        return True
    if isinstance(value, bool):
        return False
    if scale == "bp":
        return isinstance(value, int) and 0 <= value <= 10000
    return isinstance(value, (int, float)) and 0.0 <= value <= 1.0
