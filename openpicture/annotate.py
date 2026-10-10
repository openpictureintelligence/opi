"""Editing the human layer — and only the human layer.

`editorial_annotations` is unsigned and belongs to whoever holds the file
(spec §8). These helpers let a tool change it without ever touching
`media_binding` or `machine_intelligence`; every write re-verifies the
signatures afterwards and refuses to leave a file behind if they changed,
which by construction they cannot — the check is there to make the
guarantee visible rather than assumed.

Full-profile files are rewritten with their members carried over byte for
byte; alignment is recomputed by `container.write_full`.
"""

from __future__ import annotations

import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from . import MANIFEST_MEMBER, container, sign

__all__ = ["set_fields", "remove_fields", "add_label", "anonymize", "edit"]

BLOCK = "editorial_annotations"


class AnnotationRefused(RuntimeError):
    """The edit would have touched something other than the human layer."""


def edit(path: str | os.PathLike, mutate: Callable[[dict], None]) -> dict:
    """Apply `mutate(annotations)` to the file's human layer and rewrite it.

    Returns the new manifest. The machine blocks are compared before and
    after by their signature payloads; any difference raises and nothing is
    written.
    """
    path = Path(path)
    manifest, profile = container.read_manifest(path)
    before_status = sign.verify_manifest(manifest).status
    before = _machine_snapshot(manifest)

    annotations = manifest.get(BLOCK)
    if annotations is None:
        annotations = {}
    if not isinstance(annotations, dict):
        raise AnnotationRefused(f"{BLOCK} is not an object; refusing to guess")
    mutate(annotations)
    manifest[BLOCK] = annotations

    if _machine_snapshot(manifest) != before:
        raise AnnotationRefused("edit reached outside the human layer; nothing written")
    after_status = sign.verify_manifest(manifest).status
    if after_status != before_status:
        raise AnnotationRefused(f"signature status changed {before_status} → {after_status}; nothing written")

    container.rewrite(path, manifest)
    return manifest


def _machine_snapshot(manifest: Mapping) -> tuple:
    runs = manifest.get("machine_intelligence") or []
    return (
        container.manifest_bytes({"media_binding": manifest.get("media_binding")}),
        tuple(sign.run_payload(manifest, r) for r in runs if isinstance(r, dict)),
        tuple(container.manifest_bytes(r.get("signature", {})) for r in runs if isinstance(r, dict)),
        manifest.get("opi"), manifest.get("profile"),
    )


def set_fields(path: str | os.PathLike, fields: Mapping[str, Any]) -> dict:
    if "labels" in fields and not isinstance(fields["labels"], list):
        raise AnnotationRefused("labels must be a list; use add_label")
    return edit(path, lambda ann: ann.update(fields))


def remove_fields(path: str | os.PathLike, keys) -> dict:
    def _rm(ann: dict) -> None:
        for k in keys:
            ann.pop(k, None)
    return edit(path, _rm)


def add_label(path: str | os.PathLike, name: str, value: Any, *, created_by: str,
              span: Mapping | None = None, by: str | None = None,
              at: str | None = None, notes: str | None = None,
              id: str | None = None) -> dict:
    """Append a label in the shape §8.2 defines for labels.

    `created_by` says where the record came from — a tool, a file, a signer.
    `by` says which human formed the judgement, and is self-declared: §8.2
    forbids deriving it from a signature, and §13 forbids filling it from an
    OS user name or an email address, so nothing here guesses it.

    Optional keys are omitted rather than written as `null`: §8.2 gives an
    absent `span` the meaning "the whole medium", which `null` does not have,
    and the published schema types `span` as an object.
    """
    def _add(ann: dict) -> None:
        labels = ann.setdefault("labels", [])
        if not isinstance(labels, list):
            raise AnnotationRefused("labels is not a list")
        entry = {
            "name": name, "value": value, "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        for key, val in (("span", dict(span) if span else None), ("id", id),
                         ("by", by), ("at", at), ("notes", notes)):
            if val is not None:
                entry[key] = val
        labels.append(entry)
    return edit(path, _add)


def anonymize(path: str | os.PathLike) -> dict:
    """Strip the self-declared human identity from every label (§8.2).

    Removes `by` and `at`. `created_by` stays: it is record provenance, not
    personal identity, and §8.2 requires it — a label without it is invalid,
    so stripping it would trade a privacy fix for a malformed file.
    """
    def _strip(ann: dict) -> None:
        labels = ann.get("labels")
        if labels is None:
            return
        if not isinstance(labels, list):
            raise AnnotationRefused("labels is not a list")
        for entry in labels:
            if isinstance(entry, dict):
                entry.pop("by", None)
                entry.pop("at", None)
    return edit(path, _strip)
