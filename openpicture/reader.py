"""The consumer's view of a `.opi`: one object, the manifest behind it.

`container`, `sign` and `validate` are the building blocks; this is the
door most readers walk through. `load(path)` gives a `Sidecar` that knows
its profile, its media binding, its runs (each with a verification status)
and its human layer, and hands out member bytes on request — as a zero-copy
`memoryview` over an `mmap` for the aligned binaries when asked.

Nothing here writes. Nothing here trusts: `Sidecar.runs` carry their
signature status and `Sidecar.trusted_facets()` returns only what verified.
"""

from __future__ import annotations

import mmap
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from . import MANIFEST_MEMBER, SPEC_VERSION, container, sign

__all__ = ["load", "Sidecar", "Run", "UnsupportedVersion"]


class UnsupportedVersion(ValueError):
    """The file's `opi` major is newer than this reader implements."""


@dataclass
class Run:
    index: int
    data: dict
    status: str  # valid | invalid | unsigned
    signer: str | None = None
    reason: str = ""

    @property
    def run_id(self) -> str | None:
        return self.data.get("run_id")

    @property
    def producer(self) -> str | None:
        return self.data.get("producer")

    @property
    def model_version(self) -> str | None:
        return self.data.get("model_version")

    @property
    def facets(self) -> dict:
        f = self.data.get("facets")
        return f if isinstance(f, dict) else {}

    @property
    def attachments(self) -> dict:
        a = self.data.get("attachments")
        return a if isinstance(a, dict) else {}

    @property
    def verified(self) -> bool:
        return self.status == "valid"


@dataclass
class Sidecar:
    path: Path
    profile: str
    manifest: dict
    runs: list[Run] = field(default_factory=list)
    signature_status: str = "unsigned"

    # ── envelope ───────────────────────────────────────────────────────

    @property
    def version(self) -> int:
        return self.manifest.get("opi")

    @property
    def media_binding(self) -> dict:
        return self.manifest.get("media_binding") or {}

    @property
    def original(self) -> dict | None:
        """The `files[]` entry with role `original`, if any."""
        for f in self.media_binding.get("files") or []:
            if isinstance(f, dict) and f.get("role", "original") == "original":
                return f
        return None

    @property
    def sha256(self) -> str | None:
        o = self.original
        return o.get("sha256") if o else None

    @property
    def annotations(self) -> dict:
        a = self.manifest.get("editorial_annotations")
        return a if isinstance(a, dict) else {}

    # ── intelligence ───────────────────────────────────────────────────

    def facets(self, name: str, *, verified_only: bool = False) -> Iterator[tuple[Run, Any]]:
        """Every run's `facets[name]`, as (run, value) pairs."""
        for run in self.runs:
            if verified_only and not run.verified:
                continue
            if name in run.facets:
                yield run, run.facets[name]

    def trusted_facets(self, name: str) -> list[Any]:
        return [value for _, value in self.facets(name, verified_only=True)]

    # ── members ────────────────────────────────────────────────────────

    def members(self) -> list[str]:
        if self.profile != "full":
            return []
        with zipfile.ZipFile(self.path) as zf:
            return [n for n in zf.namelist() if n != MANIFEST_MEMBER]

    def read_member(self, name: str) -> bytes:
        if self.profile != "full":
            raise KeyError(f"{name}: Core profile has no members")
        with zipfile.ZipFile(self.path) as zf:
            return zf.read(name)

    def map_member(self, name: str) -> memoryview:
        """A zero-copy view of a STORED member's bytes over an `mmap`.

        Only meaningful for aligned, uncompressed members (`*.bin`,
        `*.safetensors`); a DEFLATED member raises. The caller owns the
        view; release it before the file is rewritten.
        """
        with zipfile.ZipFile(self.path) as zf:
            info = zf.getinfo(name)
            if info.compress_type != zipfile.ZIP_STORED:
                raise ValueError(f"{name} is compressed; use read_member")
            size = info.file_size
        offset = container.member_data_offset(self.path, name)
        fd = os.open(self.path, os.O_RDONLY)
        try:
            mm = mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
        finally:
            os.close(fd)
        return memoryview(mm)[offset:offset + size]


def load(path: str | os.PathLike, *, max_version: int = SPEC_VERSION) -> Sidecar:
    """Open a `.opi`, verify every run, and return a `Sidecar`.

    Raises `ValueError` for a file that is not a `.opi` and
    `UnsupportedVersion` when its `opi` major exceeds `max_version`
    (spec Rule 3.1: readers refuse a major they do not implement).
    """
    path = Path(path)
    manifest, profile = container.read_manifest(path)
    version = manifest.get("opi")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError(f"{path}: `opi` must be an integer version, got {version!r}")
    if version > max_version:
        raise UnsupportedVersion(f"{path}: opi {version} > supported {max_version}")
    report = sign.verify_manifest(manifest)
    by_index = {r.index: r for r in report.runs}
    runs = []
    for i, data in enumerate(manifest.get("machine_intelligence") or []):
        r = by_index.get(i)
        runs.append(Run(i, data if isinstance(data, dict) else {},
                        r.status if r else "invalid", r.signer if r else None, r.reason if r else ""))
    return Sidecar(path, profile, manifest, runs, report.status)
