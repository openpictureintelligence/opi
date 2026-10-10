"""Embeddings as safetensors members — `embeddings/<model-id>.safetensors`.

The layout is Hugging Face's safetensors, chosen (A8 §3) because it is
self-describing, mmap-friendly, and parseable with `struct` + `json` +
`memoryview` alone:

    [u64 LE header length N][N bytes JSON header][byte buffer]

Two rules stricter than the reference writer, both allowed by the spec:
the header is padded with spaces to a multiple of **64**, so the buffer —
and therefore the first tensor — starts 64-byte aligned inside the member;
and the member itself is STORED at a 64-aligned archive offset by
`container.write_full(..., aligned={name})`. Together they let a reader
`mmap` the `.opi` and hand a tensor library an aligned, zero-copy slice.

The spec forbids holes in the buffer, so tensors after the first are
contiguous and aligned only when the preceding sizes happen to be multiples
of 64. That is why A8 says **one file per model**: put the big `[N, D]`
matrix first, the small index vector after it.

Convention for a run's embeddings (A8): tensor `<model-id>/frames` `[N, D]`
F16 L2-normalized by default (F32 when the producer says so), optional
`<model-id>/frame_index` `[N]` I64, optional `<model-id>/frames_binary`
`[N, D/8]` U8 packbits. `__metadata__` carries `model`, `dim`,
`normalized`, `quant` as strings — the spec allows string→string only.
"""

from __future__ import annotations

import re

import array
import hashlib
import json
import struct
import sys
from typing import Mapping, Sequence

__all__ = [
    "DTYPES",
    "MEDIA_TYPE",
    "member_name",
    "pack",
    "unpack",
    "f32",
    "f16",
    "i64",
    "attachment_entry",
    "REQUIRED_METADATA",
    "VECTORS",
    "SPANS",
    "FRAME_SPANS",
    "spans",
    "pack_vectors",
    "problems",
]

MEDIA_TYPE = "application/x-safetensors"
ALIGNMENT = 64
VECTORS = "vectors"          # the required first tensor, shape [count, dim]
SPANS = "spans"              # optional [count, 2] I64 milliseconds, -1 untimed
# F1 (creator spec §7.5): frames are the authoritative position (§6A), so a
# member MAY carry `frame_spans` [count, 2] I64 `[frame_in, frame_out)` per
# row, exactly as the media's rate counts. `spans` (milliseconds) stays as the
# backward-compatible fallback for producers that hold sub-frame instants.
FRAME_SPANS = "frame_spans"  # optional [count, 2] I64 frames, -1 untimed
REQUIRED_METADATA = ("opi.model", "opi.model_version", "opi.dim", "opi.dtype",
                     "opi.normalized", "opi.scope")
NORMALIZED = ("l2", "none")
VECTOR_DTYPES = ("F16", "F32", "I8", "U8")
QUANTIZED = ("I8", "U8")
_HEADER_CAP = 100_000_000  # the reference implementation's ceiling

# dtype name -> bytes per element (the dtypes safetensors defines).
DTYPES: dict[str, int] = {
    "BOOL": 1, "U8": 1, "I8": 1, "F8_E4M3": 1, "F8_E5M2": 1,
    "I16": 2, "U16": 2, "F16": 2, "BF16": 2,
    "I32": 4, "U32": 4, "F32": 4,
    "I64": 8, "U64": 8, "F64": 8,
}


def member_name(model_id: str) -> str:
    """`embeddings/<model-id>.safetensors`, filesystem-safe.

    Only `[A-Za-z0-9._-]` survive: a slash would create a directory inside
    the archive, a colon (`emb:visual`) is refused by NTFS when the member
    is extracted, and anything else is a surprise waiting for a reader.
    Colons become `-`, slashes `_`, everything else `-`.
    """
    safe = model_id.strip().replace(":", "-").replace("/", "_").replace("\\", "_")
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", safe).strip("-.")
    if not safe or safe in (".", ".."):
        raise ValueError(f"unusable model id {model_id!r}")
    return f"embeddings/{safe}.safetensors"


# ── element encoders ────────────────────────────────────────────────────


def f32(values: Sequence[float]) -> bytes:
    a = array.array("f", values)
    if sys.byteorder != "little":
        a.byteswap()
    return a.tobytes()


def f16(values: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(values)}e", *values)


def i64(values: Sequence[int]) -> bytes:
    a = array.array("q", values)
    if sys.byteorder != "little":
        a.byteswap()
    return a.tobytes()


_ENCODERS = {"F32": f32, "F16": f16, "I64": i64}


# ── pack / unpack ───────────────────────────────────────────────────────


def pack(
    tensors: Mapping[str, tuple[Sequence[int], str, bytes | Sequence[float] | Sequence[int]]],
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    """A safetensors file. `tensors` maps name -> (shape, dtype, data).

    `data` is raw little-endian bytes, or a flat sequence of numbers for
    F32 / F16 / I64 which are encoded here. Insertion order is preserved
    and decides the buffer layout; put the large matrix first.
    """
    if not tensors:
        raise ValueError("no tensors to pack")
    header: dict = {}
    meta = dict(metadata or {})
    for k, v in meta.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("__metadata__ must be string -> string")
    if meta:
        header["__metadata__"] = meta

    chunks: list[bytes] = []
    offset = 0
    for name, (shape, dtype, data) in tensors.items():
        if name == "__metadata__":
            raise ValueError("'__metadata__' is a reserved tensor name")
        if dtype not in DTYPES:
            raise ValueError(f"unknown dtype {dtype!r}")
        shape = [int(d) for d in shape]
        if any(d < 0 for d in shape):
            raise ValueError(f"negative dimension in {name}: {shape}")
        count = 1
        for d in shape:
            count *= d
        if not isinstance(data, (bytes, bytearray, memoryview)):
            enc = _ENCODERS.get(dtype)
            if enc is None:
                raise ValueError(f"pass raw bytes for dtype {dtype}")
            data = enc(data)
        data = bytes(data)
        if len(data) != count * DTYPES[dtype]:
            raise ValueError(
                f"{name}: {len(data)} bytes does not match shape {shape} of {dtype}"
                f" ({count * DTYPES[dtype]} expected)")
        header[name] = {"dtype": dtype, "shape": shape, "data_offsets": [offset, offset + len(data)]}
        chunks.append(data)
        offset += len(data)

    body = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    pad = (-(8 + len(body))) % ALIGNMENT
    body += b" " * pad
    return struct.pack("<Q", len(body)) + body + b"".join(chunks)


def unpack(data: bytes | bytearray | memoryview) -> tuple[dict[str, str], dict[str, tuple[str, list[int], memoryview]]]:
    """`(metadata, {name: (dtype, shape, view)})` — views are zero-copy
    slices into `data`. Raises `ValueError` for anything malformed."""
    mv = memoryview(data)
    if len(mv) < 8:
        raise ValueError("safetensors: shorter than the 8-byte header length")
    (n,) = struct.unpack("<Q", mv[:8])
    if n > _HEADER_CAP or 8 + n > len(mv):
        raise ValueError(f"safetensors: header length {n} exceeds the file")
    raw = bytes(mv[8:8 + n])
    if not raw.startswith(b"{"):
        raise ValueError("safetensors: header does not begin with '{'")
    try:
        header = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"safetensors: bad header JSON: {exc}") from None
    if not isinstance(header, dict):
        raise ValueError("safetensors: header is not an object")
    metadata = header.pop("__metadata__", {}) or {}
    if not isinstance(metadata, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()):
        raise ValueError("safetensors: __metadata__ must be string -> string")

    buffer = mv[8 + n:]
    tensors: dict[str, tuple[str, list[int], memoryview]] = {}
    spans: list[tuple[int, int]] = []
    for name, info in header.items():
        if not isinstance(info, dict):
            raise ValueError(f"safetensors: {name}: entry is not an object")
        dtype, shape, offs = info.get("dtype"), info.get("shape"), info.get("data_offsets")
        if dtype not in DTYPES:
            raise ValueError(f"safetensors: {name}: unknown dtype {dtype!r}")
        if not isinstance(shape, list) or not all(isinstance(d, int) and d >= 0 for d in shape):
            raise ValueError(f"safetensors: {name}: bad shape {shape!r}")
        if (not isinstance(offs, list) or len(offs) != 2
                or not all(isinstance(o, int) for o in offs) or offs[0] > offs[1] or offs[1] > len(buffer)):
            raise ValueError(f"safetensors: {name}: bad data_offsets {offs!r}")
        count = 1
        for d in shape:
            count *= d
        if offs[1] - offs[0] != count * DTYPES[dtype]:
            raise ValueError(f"safetensors: {name}: data_offsets do not match shape/dtype")
        spans.append((offs[0], offs[1]))
        tensors[name] = (dtype, shape, buffer[offs[0]:offs[1]])
    # No holes, no overlap, whole buffer indexed — the anti-polyglot rule.
    spans.sort()
    cursor = 0
    for begin, end in spans:
        if begin != cursor:
            raise ValueError("safetensors: buffer has a hole or overlap")
        cursor = end
    if cursor != len(buffer):
        raise ValueError("safetensors: trailing bytes after the last tensor")
    return metadata, tensors


# ── attachment glue ─────────────────────────────────────────────────────


def spans(tensors: Mapping[str, tuple[str, list[int], memoryview]]) -> tuple[str | None, list[tuple[int, int]]]:
    """The timed rows of a §7b.3 member as `(unit, pairs)`.

    `unit` is `"frame"` when the producer wrote the frame-exact `frame_spans`
    tensor (F1 — frames are the position, §6A), `"ms"` when only the
    backward-compatible millisecond `spans` fallback is present, and `None`
    when the member is untimed. Each pair is `(start, end)` in that unit, with
    `-1` marking an untimed row. Accepts the `tensors` mapping `unpack()`
    returns; a caller can then decide whether frame precision is available.
    """
    for tensor, unit in ((FRAME_SPANS, "frame"), (SPANS, "ms")):
        if tensor in tensors:
            dtype, shape, view = tensors[tensor]
            if dtype != "I64" or len(shape) != 2 or shape[1] != 2:
                raise ValueError(f"{tensor} must be I64 [count, 2], got {dtype} {shape}")
            values = array.array("q")
            values.frombytes(bytes(view))
            if sys.byteorder != "little":
                values.byteswap()
            flat = values.tolist()
            return unit, [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
    return None, []


# ── the normative embeddings member (spec §7b.3) ─────────────────────────


def pack_vectors(
    vectors: Sequence[Sequence[float]] | Sequence[float],
    dim: int,
    *,
    model: str,
    model_version: str,
    dtype: str = "F16",
    normalized: str = "l2",
    scope: str = "shot",
    spans_ms: Sequence[tuple[int, int]] | None = None,
    frame_spans: Sequence[tuple[int, int]] | None = None,
    scale: Sequence[float] | None = None,
    zero_point: Sequence[float] | None = None,
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    """A §7b.3 embeddings member: `vectors` [count, dim] first, optional
    `spans` [count, 2] I64 milliseconds and `frame_spans` [count, 2] I64
    frames (F1 — prefer the latter; frames are the position, §6A),
    quantization tensors for I8/U8, and the six required `opi.*` metadata
    keys. `vectors` may be flat or nested."""
    if dtype not in VECTOR_DTYPES:
        raise ValueError(f"vectors dtype must be one of {VECTOR_DTYPES}, got {dtype!r}")
    if normalized not in NORMALIZED:
        raise ValueError(f"normalized must be one of {NORMALIZED}")
    flat: list = []
    if vectors and isinstance(vectors[0], (list, tuple, array.array, memoryview)):
        for row in vectors:
            if len(row) != dim:
                raise ValueError(f"row has {len(row)} values, dim is {dim}")
            flat.extend(row)
    else:
        flat = list(vectors)
    if dim <= 0 or len(flat) % dim:
        raise ValueError(f"{len(flat)} values do not form rows of dim {dim}")
    count = len(flat) // dim
    if dtype in QUANTIZED:
        data = bytes(int(v) & 0xFF for v in flat) if dtype == "U8" else struct.pack(f"<{len(flat)}b", *[int(v) for v in flat])
    else:
        data = _ENCODERS[dtype](flat)
    tensors: dict = {VECTORS: ([count, dim], dtype, data)}
    if spans_ms is not None:
        if len(spans_ms) != count:
            raise ValueError("spans_ms must have one pair per row")
        tensors[SPANS] = ([count, 2], "I64", [int(v) for pair in spans_ms for v in pair])
    if frame_spans is not None:
        if len(frame_spans) != count:
            raise ValueError("frame_spans must have one pair per row")
        flat_spans = [int(v) for pair in frame_spans for v in pair]
        tensors[FRAME_SPANS] = ([count, 2], "I64", flat_spans)
    if dtype in QUANTIZED:
        if scale is None or zero_point is None:
            raise ValueError("I8/U8 vectors need scale and zero_point")
        if len(scale) not in (1, dim) or len(zero_point) not in (1, dim):
            raise ValueError("scale and zero_point must have length 1 or dim")
        tensors["scale"] = ([len(scale)], "F32", list(scale))
        tensors["zero_point"] = ([len(zero_point)], "F32", list(zero_point))
    meta = {
        "opi.model": model, "opi.model_version": model_version, "opi.dim": str(dim),
        "opi.dtype": dtype, "opi.normalized": normalized, "opi.scope": scope,
    }
    meta.update({k: str(v) for k, v in (metadata or {}).items()})
    return pack(tensors, meta)


def problems(data: bytes | bytearray | memoryview, declared: Mapping | None = None) -> list[str]:
    """Every way `data` fails §7b.3, as messages; empty means conformant.

    `declared` is the attachment object; its convenience keys (`dim`,
    `count`, `dtype`, `normalized`, `model`, `model_version`, `scope`) are
    checked against the header when present.
    """
    out: list[str] = []
    try:
        meta, tensors = unpack(data)
    except ValueError as exc:
        return [f"safetensors: {exc}"]
    (n,) = struct.unpack("<Q", bytes(memoryview(data)[:8]))
    if (8 + n) % ALIGNMENT:
        out.append(f"header not padded to 64 (8 + {n} = {8 + n})")
    if VECTORS not in tensors:
        out.append("tensor 'vectors' missing")
        return out
    dtype, shape, view = tensors[VECTORS]
    if len(shape) != 2:
        out.append(f"'vectors' must be 2-D, shape is {shape}")
        return out
    count, dim = shape
    header = json.loads(bytes(memoryview(data)[8:8 + n]).decode("utf-8"))
    first = min((v for k, v in header.items() if k != "__metadata__"), key=lambda v: v["data_offsets"][0], default=None)
    if first is not None and first is not header[VECTORS] and first["data_offsets"][0] < header[VECTORS]["data_offsets"][0]:
        out.append("'vectors' is not the first tensor in the buffer")
    if dtype not in VECTOR_DTYPES:
        out.append(f"'vectors' dtype {dtype} not permitted")
    for key in REQUIRED_METADATA:
        if key not in meta:
            out.append(f"__metadata__ missing {key}")
    if meta.get("opi.dim") not in (None, str(dim)):
        out.append(f"opi.dim {meta.get('opi.dim')!r} != vectors dim {dim}")
    if meta.get("opi.dtype") not in (None, dtype):
        out.append(f"opi.dtype {meta.get('opi.dtype')!r} != vectors dtype {dtype}")
    if meta.get("opi.normalized") not in (None, *NORMALIZED):
        out.append(f"opi.normalized must be l2|none, got {meta.get('opi.normalized')!r}")
    if SPANS in tensors:
        sd, ss, _ = tensors[SPANS]
        if sd != "I64" or ss != [count, 2]:
            out.append(f"'spans' must be I64 [{count}, 2], got {sd} {ss}")
    if FRAME_SPANS in tensors:
        fd, fs, _ = tensors[FRAME_SPANS]
        if fd != "I64" or fs != [count, 2]:
            out.append(f"'frame_spans' must be I64 [{count}, 2], got {fd} {fs}")
    if dtype in QUANTIZED:
        for name in ("scale", "zero_point"):
            if name not in tensors:
                out.append(f"quantized vectors need tensor '{name}'")
            else:
                qd, qs, _ = tensors[name]
                if qd != "F32" or qs not in ([1], [dim]):
                    out.append(f"'{name}' must be F32 [1] or [{dim}], got {qd} {qs}")
    if declared:
        span_units = "frame" if FRAME_SPANS in tensors else ("ms" if SPANS in tensors else None)
        expect = {"dim": dim, "count": count, "dtype": dtype,
                  "normalized": meta.get("opi.normalized"), "model": meta.get("opi.model"),
                  "model_version": meta.get("opi.model_version"), "scope": meta.get("opi.scope"),
                  "spans": span_units}
        for k, v in expect.items():
            if k in declared and declared[k] != v:
                out.append(f"attachment {k}={declared[k]!r} disagrees with member ({v!r})")
    return out


def attachment_entry(data: bytes, *, rows: str | None = None) -> dict:
    """The value for a run's `attachments[<member>]`: `{sha256, size,
    media_type}` plus the §7b.3 convenience keys read from the header when
    the member has them. `rows` names the facet whose entries the rows
    correspond to (e.g. `"shots"`)."""
    entry = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "media_type": MEDIA_TYPE}
    try:
        meta, tensors = unpack(data)
    except ValueError:
        return entry
    if VECTORS in tensors and len(tensors[VECTORS][1]) == 2:
        dtype, (count, dim), _ = tensors[VECTORS]
        entry.update({"dim": dim, "count": count, "dtype": dtype})
        for src, dst in (("opi.model", "model"), ("opi.model_version", "model_version"),
                         ("opi.normalized", "normalized"), ("opi.scope", "scope")):
            if src in meta:
                entry[dst] = meta[src]
        if FRAME_SPANS in tensors:
            entry["spans"] = "frame"
        elif SPANS in tensors:
            entry["spans"] = "ms"
    if rows is not None:
        entry["rows"] = rows
    return entry
