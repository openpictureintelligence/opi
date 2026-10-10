"""Intelligence becomes diffable (`sidecar-as-product.md` §11.4).

Two manifests for the same clip — yesterday's and today's, ours and a
partner's — compared block by block: which binding facts changed, which
producer runs were added, removed or changed (by `run_id`), what the human
layer did, and whether signature status moved. The result is structured;
`cli.py` renders it. Machine-layer equality is the exit code the CLI uses,
because that is the question "did the intelligence change" asks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from . import jcs, sign

__all__ = ["diff", "DiffResult", "RunDiff", "LabelDiff"]


@dataclass
class LabelDiff:
    """Human labels compared by stable identity (W17).

    A label carrying §8.2's `id` is matched on it across the two files:
    present only in *a* is removed, only in *b* is added, in both but
    different is changed. A label without an `id` is matched on the identity
    §8.2 gives it — the same `name`, `value` and `span` are one label — so a
    changed field on an un-`id`ed label reads as a removal plus an addition,
    which is the honest answer when nothing stable identifies it.
    """

    added: list[dict] = field(default_factory=list)
    changed: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.added or self.changed or self.removed)

    def as_dict(self) -> dict:
        return {"added": self.added, "changed": self.changed, "removed": self.removed}


@dataclass
class RunDiff:
    run_id: str
    change: str                      # added | removed | changed
    producer: str | None = None
    model_version: str | None = None
    facets: dict[str, tuple[int, int]] = field(default_factory=dict)   # facet -> (count a, count b)
    changed_facets: list[str] = field(default_factory=list)
    signature: tuple[str | None, str | None] = (None, None)          # signer a, signer b

    def as_dict(self) -> dict:
        return {"run_id": self.run_id, "change": self.change, "producer": self.producer,
                "model_version": self.model_version,
                "facets": {k: list(v) for k, v in self.facets.items()},
                "changed_facets": self.changed_facets, "signature": list(self.signature)}


@dataclass
class DiffResult:
    binding: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    runs: list[RunDiff] = field(default_factory=list)
    human: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    labels: LabelDiff = field(default_factory=LabelDiff)
    signature_status: tuple[str, str] = ("", "")
    envelope: dict[str, tuple[Any, Any]] = field(default_factory=dict)

    @property
    def machine_identical(self) -> bool:
        return not self.binding and not self.runs

    @property
    def identical(self) -> bool:
        return self.machine_identical and not self.human and not self.envelope

    def as_dict(self) -> dict:
        return {
            "machine_identical": self.machine_identical,
            "identical": self.identical,
            "envelope": {k: list(v) for k, v in self.envelope.items()},
            "media_binding": {k: list(v) for k, v in self.binding.items()},
            "runs": [r.as_dict() for r in self.runs],
            "editorial_annotations": {k: list(v) for k, v in self.human.items()},
            "labels": self.labels.as_dict(),
            "signature_status": list(self.signature_status),
        }


def _same(a: Any, b: Any) -> bool:
    try:
        return jcs.canonicalize(a) == jcs.canonicalize(b)
    except (TypeError, ValueError):
        return a == b


def _dict_changes(a: Mapping | None, b: Mapping | None, *, skip=()) -> dict[str, tuple[Any, Any]]:
    a = a if isinstance(a, Mapping) else {}
    b = b if isinstance(b, Mapping) else {}
    out: dict[str, tuple[Any, Any]] = {}
    for k in sorted(set(a) | set(b)):
        if k in skip:
            continue
        va, vb = a.get(k, _MISSING), b.get(k, _MISSING)
        if va is _MISSING or vb is _MISSING or not _same(va, vb):
            out[k] = (None if va is _MISSING else va, None if vb is _MISSING else vb)
    return out


_MISSING = object()


def _runs_by_id(manifest: Mapping) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i, r in enumerate(manifest.get("machine_intelligence") or []):
        if isinstance(r, dict):
            out[str(r.get("run_id") or f"#{i}")] = r
    return out


def _facet_counts(run: Mapping) -> dict[str, int]:
    facets = run.get("facets") or {}
    return {k: (len(v) if isinstance(v, (list, dict)) else 1) for k, v in facets.items()} if isinstance(facets, Mapping) else {}


def diff(a: Mapping, b: Mapping) -> DiffResult:
    res = DiffResult()
    res.envelope = _dict_changes(
        {k: a.get(k) for k in ("opi", "profile")}, {k: b.get(k) for k in ("opi", "profile")})
    res.binding = _dict_changes(a.get("media_binding"), b.get("media_binding"))

    ra, rb = _runs_by_id(a), _runs_by_id(b)
    for rid in sorted(set(ra) | set(rb)):
        if rid not in rb:
            r = ra[rid]
            res.runs.append(RunDiff(rid, "removed", r.get("producer"), r.get("model_version"),
                                    {k: (n, 0) for k, n in _facet_counts(r).items()},
                                    signature=(_signer(r), None)))
        elif rid not in ra:
            r = rb[rid]
            res.runs.append(RunDiff(rid, "added", r.get("producer"), r.get("model_version"),
                                    {k: (0, n) for k, n in _facet_counts(r).items()},
                                    signature=(None, _signer(r))))
        else:
            x, y = ra[rid], rb[rid]
            body_x = {k: v for k, v in x.items() if k != "signature"}
            body_y = {k: v for k, v in y.items() if k != "signature"}
            if _same(body_x, body_y) and _signer(x) == _signer(y):
                continue
            fa, fb = _facet_counts(x), _facet_counts(y)
            facets = {k: (fa.get(k, 0), fb.get(k, 0)) for k in sorted(set(fa) | set(fb))}
            changed = [k for k in facets if not _same((x.get("facets") or {}).get(k), (y.get("facets") or {}).get(k))]
            res.runs.append(RunDiff(rid, "changed", y.get("producer", x.get("producer")),
                                    y.get("model_version", x.get("model_version")),
                                    facets, changed, (_signer(x), _signer(y))))

    res.human = _dict_changes(a.get("editorial_annotations"), b.get("editorial_annotations"))
    res.labels = _label_diff(a, b)
    res.signature_status = (sign.verify_manifest(a).status, sign.verify_manifest(b).status)
    return res


def _labels(manifest: Mapping) -> list[dict]:
    ann = manifest.get("editorial_annotations")
    if not isinstance(ann, Mapping):
        return []
    labels = ann.get("labels")
    return [l for l in labels if isinstance(l, dict)] if isinstance(labels, list) else []


def _label_id(label: Mapping) -> str | None:
    lid = label.get("id")
    return lid if isinstance(lid, str) and lid else None


def _label_same(a: Mapping, b: Mapping) -> bool:
    """§8.2's identity for a label: same `name`, `value` and `span`."""
    return all(_same(a.get(k), b.get(k)) for k in ("name", "value", "span"))


def _label_diff(a: Mapping, b: Mapping) -> LabelDiff:
    out = LabelDiff()
    la, lb = _labels(a), _labels(b)
    a_by_id = {_label_id(l): l for l in la if _label_id(l)}
    b_by_id = {_label_id(l): l for l in lb if _label_id(l)}
    for lid in sorted(set(a_by_id) | set(b_by_id)):
        x, y = a_by_id.get(lid), b_by_id.get(lid)
        if x is None:
            out.added.append({"id": lid, "label": y})
        elif y is None:
            out.removed.append({"id": lid, "label": x})
        elif not _same(x, y):
            out.changed.append({"id": lid, "from": x, "to": y})
    # Labels with no stable id: match on (name, value, span), §8.2.
    rest_a = [l for l in la if not _label_id(l)]
    rest_b = [l for l in lb if not _label_id(l)]
    taken = [False] * len(rest_b)
    for x in rest_a:
        match = next((i for i, y in enumerate(rest_b) if not taken[i] and _label_same(x, y)), None)
        if match is None:
            out.removed.append({"id": None, "label": x})
        else:
            taken[match] = True
    for i, y in enumerate(rest_b):
        if not taken[i]:
            out.added.append({"id": None, "label": y})
    return out


def _signer(run: Mapping) -> str | None:
    sig = run.get("signature")
    return sig.get("signer") if isinstance(sig, dict) else None
