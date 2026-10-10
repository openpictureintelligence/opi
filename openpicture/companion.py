"""Companion files — the lossy projections a MAM will actually pick up.

No MAM ingests an unknown extension (research pass B5, 2026-08-28): iconik's
storage gateway pairs same-basename `.json`/`.xml`/`.csv` against a
configured metadata view, CatDV Worker takes `.xml`, and everything else
needs an adapter. So the `.opi` stays authoritative and a **companion** is
written beside it in a shape the target already reads — same basename,
different extension, derived from the manifest and regenerable from it.

Two shapes here:

- `iconik_json` — iconik's documented sidecar shape:
  `{"metadata_values": {<field>: {"field_values": [{"value": …}, …]}},
  "segments": [{"start_milliseconds", "end_milliseconds", "text",
  "segment_type"}]}`. Field names are the keys an admin maps in the
  Sidecar Metadata View; ours are stable and prefixed `opi_`.
- `flat_json` — a generic one-level object for anything that maps JSON
  paths (Dalet Flex asset maps, scripts, spreadsheets).

Both are *projections*: they carry summaries and human labels, never the
signatures — a companion is not verifiable and does not claim to be.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from . import container

__all__ = ["KINDS", "iconik_json", "flat_json", "companion_path", "write_companion"]

KINDS = ("iconik", "flat")


# ── shared extraction ─────────────────────────────────────────────────


def _runs(manifest: Mapping) -> list[dict]:
    runs = manifest.get("machine_intelligence") or []
    return [r for r in runs if isinstance(r, dict)]


def _facet_entries(manifest: Mapping, name: str) -> list[dict]:
    out: list[dict] = []
    for run in _runs(manifest):
        facets = run.get("facets") or {}
        entries = facets.get(name) if isinstance(facets, dict) else None
        if isinstance(entries, list):
            out.extend(e for e in entries if isinstance(e, dict))
    return out


def _span_ms(entry: Mapping) -> tuple[int | None, int | None]:
    span = entry.get("span") or {}
    if not isinstance(span, dict):
        return None, None
    start, end = span.get("t_start_s"), span.get("t_end_s")
    to_ms = lambda v: int(round(v * 1000)) if isinstance(v, (int, float)) else None  # noqa: E731
    return to_ms(start), to_ms(end)


def _transcript_segments(manifest: Mapping) -> list[dict]:
    segs = []
    for sig in _facet_entries(manifest, "signals"):
        if sig.get("kind") not in ("transcript", "asr", "speech"):
            continue
        text = sig.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        start, end = _span_ms(sig)
        segs.append({"start_ms": start, "end_ms": end, "text": text.strip()})
    return segs


def _labels(manifest: Mapping) -> list[dict]:
    ann = manifest.get("editorial_annotations") or {}
    labels = ann.get("labels") if isinstance(ann, dict) else None
    return [l for l in (labels or []) if isinstance(l, dict)]


def _summary(manifest: Mapping) -> dict[str, Any]:
    """The fields every companion carries, flat and stable."""
    mb = manifest.get("media_binding") or {}
    original = next((f for f in mb.get("files") or [] if isinstance(f, dict)
                     and f.get("role", "original") == "original"), None)
    tc = mb.get("timecode") if isinstance(mb.get("timecode"), dict) else None
    shots = _facet_entries(manifest, "shots")
    transcript = _transcript_segments(manifest)
    runs = _runs(manifest)
    out: dict[str, Any] = {
        "opi_version": manifest.get("opi"),
        "opi_profile": manifest.get("profile"),
        "opi_asset_id": mb.get("asset_id"),
        "opi_media_name": original.get("name") if original else None,
        "opi_media_sha256": original.get("sha256") if original else None,
        "opi_duration_s": mb.get("duration_s"),
        "opi_camera": mb.get("camera"),
        "opi_shot_at": mb.get("shot_at"),
        "opi_timecode_start": tc.get("start") if tc else None,
        "opi_frame_rate": tc.get("label") if tc else None,
        "opi_drop_frame": tc.get("drop_frame") if tc else None,
        "opi_shot_count": len(shots),
        "opi_producers": sorted({f"{r.get('producer')}@{r.get('model_version')}" for r in runs
                                 if r.get("producer")}),
        "opi_transcript": " ".join(s["text"] for s in transcript) or None,
        "opi_labels": [f"{l.get('name')}={l.get('value')}" if l.get("value") is not None else str(l.get("name"))
                       for l in _labels(manifest)],
        "opi_generator": manifest.get("generator"),
        "opi_generated_at": manifest.get("generated_at"),
    }
    # Tier 2 facet summaries where present: the most frequent value per facet.
    for facet in ("shot_size", "camera_motion"):
        values = [e.get("value") or e.get("base") for e in _facet_entries(manifest, facet)]
        values = [v for v in values if isinstance(v, str)]
        if values:
            out[f"opi_{facet}"] = sorted(set(values), key=values.count, reverse=True)
    return out


# ── shapes ────────────────────────────────────────────────────────────


def iconik_json(manifest: Mapping) -> dict:
    """iconik Storage Gateway sidecar shape (B5 §2.1).

    Every summary field becomes `metadata_values[<field>].field_values`;
    lists become several `{"value"}` entries; `None` is omitted so an
    unmapped field never blanks a view. Transcript segments go to
    `segments` with `segment_type: "transcript"`.
    """
    values: dict[str, dict] = {}
    for key, val in _summary(manifest).items():
        if val is None or val == []:
            continue
        items = val if isinstance(val, list) else [val]
        values[key] = {"field_values": [{"value": v if isinstance(v, str) else json.dumps(v)} for v in items]}
    segments = [
        {"start_milliseconds": s["start_ms"], "end_milliseconds": s["end_ms"],
         "text": s["text"], "segment_type": "transcript"}
        for s in _transcript_segments(manifest) if s["start_ms"] is not None
    ]
    doc: dict = {"metadata_values": values}
    if segments:
        doc["segments"] = segments
    return doc


def flat_json(manifest: Mapping) -> dict:
    """One level deep: scalars and lists of scalars, nothing nested.

    Plus `opi_transcript_segments` as a list of `{start_ms, end_ms, text}`
    — the one structured value a path-mapping ingester still wants whole.
    """
    out = {k: v for k, v in _summary(manifest).items() if v is not None}
    segs = _transcript_segments(manifest)
    if segs:
        out["opi_transcript_segments"] = segs
    return out


_BUILDERS = {"iconik": iconik_json, "flat": flat_json}


# ── writing ───────────────────────────────────────────────────────────


def companion_path(opi_path: str | os.PathLike, dest: str | os.PathLike | None = None) -> Path:
    """`A001_C001.mov.opi` → `A001_C001.mov.json` beside it (or in `dest`).

    The media's own name plus `.json` — the same-basename pairing every MAM
    honours. A stem-form `A001_C001.opi` yields `A001_C001.json`.
    """
    opi = Path(opi_path)
    stem = opi.name[:-len(".opi")] if opi.name.endswith(".opi") else opi.stem
    name = stem + ".json"
    return opi.with_name(name) if dest is None else Path(dest) / name


def write_companion(opi_path: str | os.PathLike, kind: str = "iconik",
                    dest: str | os.PathLike | None = None) -> Path:
    """Write the `kind` companion for `opi_path`. Returns the path written.

    Derived egress: whoever calls this has already decided the layer may
    leave the store — the `.opi` beside it did. Atomic write, like every
    writer here.
    """
    if kind not in _BUILDERS:
        raise ValueError(f"unknown companion kind {kind!r}; one of {KINDS}")
    manifest, _ = container.read_manifest(opi_path)
    doc = _BUILDERS[kind](manifest)
    target = companion_path(opi_path, dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return container.atomic_write(target, data)
