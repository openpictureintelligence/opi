"""Structural validation of a `.opi` file — the copyable validator.

This module, with `container.py`, `sign.py`, `jcs.py` and `ed25519.py`,
is the whole validator, and all of it is standard library. Copy the
package next to a script and it runs; nothing to install.

Validation is deliberately *structural*: the envelope, the profile, the
binding, the members and their hashes, the signatures. It does not check
the meaning of intelligence fields — a schema for those comes with the
schema freeze, and a validator that refused a file for an unknown facet
would break the forward-compatibility rule (readers ignore unknown keys).
"""

from __future__ import annotations

import hashlib
import os
import re
import zipfile
from dataclasses import dataclass, field

import importlib

from . import MANIFEST_MEMBER, container, sign

# Domain checkers, one per specification chapter. Each module exposes
# `checks(...) -> list[tuple[name, ok, detail]]`; the validator calls every
# one that is present. Kept as names, not imports, so the validator runs in a
# tree where a chapter's module has not landed yet, and so the single-file
# bundle can list exactly what it carries.
_DOMAIN_CHECKS = (
    ("time", "openpicture.time", "manifest"),          # §6a — rates, spans, timecode agreement
    ("runs", "openpicture.runs", "manifest"),          # §7 — run ids, fields, lineage
    ("members", "openpicture.members", "path+manifest"),  # §4/§7b — member names, alignment, safetensors
    ("facets", "openpicture.facets", "manifest"),      # Appendix C — known-facet structure, sensitive rule
)

__all__ = ["validate", "Report", "Check"]

REQUIRED = ("opi", "profile", "media_binding")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    path: str
    profile: str | None = None
    version: int | None = None
    signature_status: str = "unsigned"
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def status(self) -> str:
        if not self.ok:
            return "invalid"
        return {"signed": "valid-signed", "partial": "valid-partial"}.get(self.signature_status, "valid-unsigned")

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(name, ok, detail))

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "status": self.status,
            "profile": self.profile,
            "opi": self.version,
            "signatures": self.signature_status,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }


def validate(path: str | os.PathLike, *, media_dir: str | os.PathLike | None = None) -> Report:
    """Validate one `.opi`. Never raises for a bad file; the report says why.

    `media_dir` (default: the sidecar's own directory) is where the bound
    media is looked for. A missing master is reported, not failed — the
    sidecar is allowed to travel without its media; a *present* master with
    a different sha256 is a failure.
    """
    report = Report(str(path))
    try:
        manifest, profile = container.read_manifest(path)
    except container.ManifestTooLarge as exc:
        report.add("manifest size", False, str(exc))
        return report
    except (ValueError, OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        report.add("readable", False, str(exc))
        return report
    form = container.detect(path)
    report.add("readable", True, f"profile {profile}, {form}")
    report.profile = profile
    report.add("canonical form", True,
               "" if form == "zip" else "bare JSON internal form; canonical .opi is ZIP")

    _envelope(manifest, profile, report)
    _binding(manifest, path, media_dir, report)
    _annotations(manifest, report)
    attachments = _attachments(manifest, report)
    if profile == "core":
        report.add("attachments", not attachments, "" if not attachments else "Core profile must not declare attachments")

    _domain_checks(manifest, path, form, report)

    vr = sign.verify_manifest(manifest)
    report.signature_status = vr.status
    if vr.reason:
        report.add("machine_intelligence", vr.status != "invalid", vr.reason)
    for r in vr.runs:
        who = f"{r.producer or '?'}" + (f" by {r.signer}" if r.signer else "")
        report.add(f"run[{r.index}] {r.status}", r.status != "invalid", r.reason or who)
    return report


def _attachments(manifest: dict, report: Report) -> dict:
    """Union of every run's declared attachments: member -> declaration.

    Shape only. **Ownership is not decided here** — SPEC §7.6 and §7b.1
    require a member to be declared by exactly one run, and this function
    used to enforce that by failing only when two runs declared the same
    member *differently*, which let an identical duplicate through. §7.6
    forbids the duplicate "even with identical hashes". `members.checks`
    decides it properly, from the archive, as `attachments.single-owner`
    (§7b.6); the union survives only to answer §7.6's other rule, that a
    Core-profile manifest declares no attachments at all.
    """
    out: dict = {}
    for i, run in enumerate(manifest.get("machine_intelligence") or []):
        att = run.get("attachments") if isinstance(run, dict) else None
        if att is None:
            continue
        if not isinstance(att, dict):
            report.add(f"run[{i}].attachments", False, "must be an object")
            continue
        out.update(att)
    return out


def _envelope(manifest: dict, profile: str, report: Report) -> None:
    for key in REQUIRED:
        report.add(f"has {key}", key in manifest, "" if key in manifest else "required")
    version = manifest.get("opi")
    ok = isinstance(version, int) and not isinstance(version, bool) and version >= 0
    report.version = version if ok else None
    report.add("opi version", ok, str(version) if ok else f"expected a non-negative integer, got {version!r}")
    declared = manifest.get("profile")
    report.add("profile matches contents", declared == profile,
               "" if declared == profile else f"declares {declared!r}, contents say {profile!r}")
    first = next(iter(manifest), None)
    report.add("opi is first key", first == "opi", "" if first == "opi" else f"first key is {first!r}")


def _binding(manifest: dict, path, media_dir, report: Report) -> None:
    mb = manifest.get("media_binding")
    if not isinstance(mb, dict):
        report.add("media_binding", False, "must be an object")
        return
    files = mb.get("files")
    if not isinstance(files, list) or not files:
        report.add("media_binding.files", False, "must be a non-empty list")
        return
    ok = all(_file_entry_ok(f) for f in files)
    report.add("media_binding.files", ok, "" if ok else
               "each file needs a basename `name` and a 64-lowercase-hex `sha256`")
    if not ok:
        return
    # SPEC §6.3: exactly one entry is the original — explicitly, or by default
    # because `role` is absent. Zero has nothing to bind to; two would make the
    # sidecar describe two media.
    originals = [f for f in files if f.get("role", "original") == "original"]
    report.add("media_binding.original", len(originals) == 1,
               "" if len(originals) == 1 else
               f"exactly one files[] entry must have role 'original', found {len(originals)}")
    base = os.fspath(media_dir) if media_dir is not None else os.path.dirname(os.fspath(path))
    for f in originals:
        candidate = os.path.join(base, f["name"])
        if not os.path.exists(candidate):
            report.add("media present", True, f"{f['name']} not beside sidecar (allowed)")
            continue
        digest = _sha256_file(candidate)
        match = digest == f["sha256"].lower()
        report.add("media sha256", match, "" if match else f"{f['name']} on disk is {digest[:12]}…, manifest says {f['sha256'][:12]}…")


def _file_entry_ok(f) -> bool:
    """SPEC §6.2: a files[] entry needs a basename `name` and lowercase hex `sha256`."""
    if not isinstance(f, dict):
        return False
    name, digest = f.get("name"), f.get("sha256")
    if not isinstance(digest, str) or not _SHA256_RE.match(digest):
        return False
    if not isinstance(name, str) or not 1 <= len(name.encode("utf-8")) <= 255:
        return False
    return "/" not in name and "\\" not in name


def _annotations(manifest: dict, report: Report) -> None:
    if "editorial_annotations" in manifest:
        ok = isinstance(manifest["editorial_annotations"], dict)
        report.add("editorial_annotations", ok, "" if ok else "must be an object")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _domain_checks(manifest: dict, path, form: str, report: Report) -> None:
    for label, modname, kind in _DOMAIN_CHECKS:
        try:
            mod = importlib.import_module(modname)
        except ImportError:
            continue
        fn = getattr(mod, "checks", None)
        if fn is None:
            continue
        if kind == "path+manifest" and form != "zip":
            continue  # container checks need a container
        try:
            results = fn(path, manifest) if kind == "path+manifest" else fn(manifest)
        except Exception as exc:  # a checker must never take the validator down
            report.add(f"{label} checks", False, f"checker raised {type(exc).__name__}: {exc}")
            continue
        for item in results:
            # a checker may return (name, ok, detail) tuples or objects with
            # those attributes; both are fine.
            if isinstance(item, (tuple, list)):
                name, ok, detail = (list(item) + ["", ""])[:3]
            else:
                name, ok, detail = getattr(item, "name", "?"), getattr(item, "ok", False), getattr(item, "detail", "")
            report.add(f"{label}: {name}", bool(ok), str(detail or ""))
