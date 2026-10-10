"""Discovery and reconciliation — the doctor states of spec §9.

A tree holds media and sidecars. This module walks it and says, per pair,
which of the states in the behavior spec it is in:

    paired             two-dot sidecar present, media sha256 matches
    paired-unverified  sidecar present, media not hashed (default: hashing is opt-in)
    missing            media without a sidecar
    orphan             sidecar without media by name
    mismatch           sidecar present, media sha256 differs — do not trust
    duplicate          stem-form and two-dot sidecars both present for one media
    newer-schema       manifest `opi` major above this reader's
    tampered           a run's signature does not verify
    unreadable         not a .opi we can parse

Pairing is by the two-dot name first (`clip.mov.opi`), the stem form
(`clip.opi`) only when no two-dot file exists. Hashing 50,000 masters is
not free, so `verify_media` is off by default and the state says so.

`repair` re-pairs orphans by sha256 across the tree and *proposes* renames;
it moves nothing unless told to. Nothing here writes into a media file.
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import EXTENSION, SPEC_VERSION, container, sign

__all__ = ["MEDIA_EXTENSIONS", "Pairing", "Rename", "scan", "repair", "summarize"]

MEDIA_EXTENSIONS = frozenset({
    ".mov", ".mp4", ".mxf", ".braw", ".r3d", ".ari", ".wav", ".aif", ".aiff",
    ".mp3", ".m4a", ".avi", ".mkv",
})
BAD_STATES = frozenset({"mismatch", "tampered", "unreadable"})


@dataclass
class Pairing:
    state: str
    media: Path | None = None
    sidecar: Path | None = None
    detail: str = ""
    extras: list[Path] = field(default_factory=list)  # duplicate sidecars

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "media": str(self.media) if self.media else None,
            "sidecar": str(self.sidecar) if self.sidecar else None,
            "detail": self.detail,
            "extras": [str(p) for p in self.extras],
        }


@dataclass
class Rename:
    sidecar: Path
    target: Path
    media: Path
    applied: bool = False

    def as_dict(self) -> dict:
        return {"sidecar": str(self.sidecar), "target": str(self.target),
                "media": str(self.media), "applied": self.applied}


def scan(root: str | os.PathLike, *, verify_media: bool = False) -> list[Pairing]:
    """Every media file and sidecar under `root`, paired and classified."""
    root = Path(root)
    media_by_dir: dict[Path, list[Path]] = {}
    sidecars_by_dir: dict[Path, list[Path]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        d = Path(dirpath)
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            p = d / name
            if name.lower().endswith(EXTENSION):
                sidecars_by_dir.setdefault(d, []).append(p)
            elif p.suffix.lower() in MEDIA_EXTENSIONS:
                media_by_dir.setdefault(d, []).append(p)

    out: list[Pairing] = []
    for d in sorted(set(media_by_dir) | set(sidecars_by_dir)):
        media = media_by_dir.get(d, [])
        sidecars = sidecars_by_dir.get(d, [])
        claimed: set[Path] = set()
        by_stem: dict[str, list[Path]] = {}
        for s in sidecars:
            by_stem.setdefault(s.name[: -len(EXTENSION)], []).append(s)
        for m in media:
            two_dot = [s for s in by_stem.get(m.name, [])]
            stem = [s for s in by_stem.get(m.stem, []) if s.name != m.name + EXTENSION]
            candidates = two_dot or stem
            if not candidates:
                out.append(Pairing("missing", media=m, detail="no sidecar"))
                continue
            primary = candidates[0]
            extras = [s for s in two_dot[1:] + (stem if two_dot else stem[1:])]
            claimed.add(primary)
            claimed.update(extras)
            pairing = _classify(m, primary, verify_media)
            if extras:
                pairing.extras = extras
                if pairing.state.startswith("paired"):
                    pairing.state = "duplicate"
                    pairing.detail = f"also {', '.join(e.name for e in extras)}"
            out.append(pairing)
        for s in sidecars:
            if s not in claimed:
                out.append(_orphan(s))
    return out


def _classify(media: Path, sidecar: Path, verify_media: bool) -> Pairing:
    try:
        manifest, _profile = container.read_manifest(sidecar)
    except (ValueError, OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        return Pairing("unreadable", media, sidecar, str(exc))
    version = manifest.get("opi")
    if isinstance(version, int) and not isinstance(version, bool) and version > SPEC_VERSION:
        return Pairing("newer-schema", media, sidecar, f"opi {version} > reader {SPEC_VERSION}")
    vr = sign.verify_manifest(manifest)
    if vr.status == "invalid":
        bad = [f"run[{r.index}] {r.signer or '?'}: {r.reason}" for r in vr.runs if r.status == "invalid"]
        return Pairing("tampered", media, sidecar, "; ".join(bad) or vr.reason)
    expected = _original_sha(manifest, media.name)
    if not verify_media:
        return Pairing("paired-unverified", media, sidecar, f"signatures {vr.status}")
    if expected is None:
        return Pairing("paired-unverified", media, sidecar, "manifest has no sha256 for this file")
    actual = sha256_file(media)
    if actual != expected.lower():
        return Pairing("mismatch", media, sidecar,
                       f"media {actual[:12]}… manifest {expected[:12]}…")
    return Pairing("paired", media, sidecar, f"sha256 ok; signatures {vr.status}")


def _orphan(sidecar: Path) -> Pairing:
    try:
        container.read_manifest(sidecar)
    except (ValueError, OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        return Pairing("unreadable", None, sidecar, str(exc))
    return Pairing("orphan", None, sidecar, "no media by name")


def _original_sha(manifest: dict, media_name: str | None = None) -> str | None:
    files = (manifest.get("media_binding") or {}).get("files") or []
    originals = [f for f in files if isinstance(f, dict) and f.get("role", "original") == "original"]
    if media_name:
        named = [f for f in originals if f.get("name") == media_name]
        if named:
            originals = named
    for f in originals:
        sha = f.get("sha256")
        if isinstance(sha, str) and len(sha) == 64:
            return sha
    return None


def sha256_file(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _HashCache:
    """sha256 per media file, keyed by (path, size, mtime) so a re-run after
    an untouched file costs nothing."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, int], str] = {}

    def get(self, path: Path) -> str:
        st = path.stat()
        key = (str(path), st.st_size, st.st_mtime_ns)
        if key not in self._cache:
            self._cache[key] = sha256_file(path)
        return self._cache[key]


def repair(root: str | os.PathLike, pairings: list[Pairing], *, apply: bool = False) -> list[Rename]:
    """Re-pair orphan sidecars to media anywhere under `root` by sha256.

    Proposes `orphan.opi → <media>.opi` beside the media it matches. Only
    media that currently lack a sidecar are candidates, so a repair never
    displaces a sidecar that already pairs. Renames happen only with
    `apply=True`, and never over an existing file.
    """
    root = Path(root)
    orphans = [p.sidecar for p in pairings if p.state == "orphan" and p.sidecar]
    if not orphans:
        return []
    unpaired = [p.media for p in pairings if p.state == "missing" and p.media]
    cache = _HashCache()
    by_sha: dict[str, list[Path]] = {}
    for m in unpaired:
        by_sha.setdefault(cache.get(m), []).append(m)

    renames: list[Rename] = []
    taken: set[Path] = set()
    for sidecar in orphans:
        try:
            manifest, _ = container.read_manifest(sidecar)
        except (ValueError, OSError, zipfile.BadZipFile):
            continue
        sha = _original_sha(manifest)
        if sha is None:
            continue
        for media in by_sha.get(sha.lower(), []):
            target = media.with_name(media.name + EXTENSION)
            if target in taken or target.exists():
                continue
            taken.add(target)
            r = Rename(sidecar, target, media)
            if apply:
                os.replace(sidecar, target)
                r.applied = True
            renames.append(r)
            break
    return renames


def summarize(pairings: list[Pairing]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in pairings:
        counts[p.state] = counts.get(p.state, 0) + 1
    return dict(sorted(counts.items()))
