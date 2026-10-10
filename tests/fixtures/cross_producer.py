"""Build `cross-producer.opi`: a foreign producer's Full file for the lanes.

Not a test by name. It is the cross-producer fixture the OPI lane publishes
early for INGEST and EXCHANGE: one signed Full file that exercises every
additive alignment item at the same time, so a consumer can prove it reads
another producer's output without the original producer present.

What it deliberately carries:

- **F1** a frame-exact `frame_spans` tensor on the embeddings member, with the
  attachment `spans: "frame"` convenience key.
- **F2** a canonical facet entry (`x-foreign.scene`) with a searchable `text`.
- **F3** an absolute `media_binding.files[].path` and `provenance[].original_path`
  — a *foreign* writer's mistake. A reader must ignore them and bind by
  `name` + `sha256`; nothing is allowed to fail over them.
- **F4** non-`labels` `editorial_annotations` keys (`mam`, `rating`, `colourist`).
- **F5** a label whose `by` is absent: `created_by` names the machine record
  (`opi:foreign-signer`), and a reader must not invent a human from the run's
  signer.
- an unknown run key (`vendor_note`) and an unknown top-level-ish key inside
  the run, both of which a reader must preserve and ignore.

The file is signed with a fixed throwaway key so it is reproducible byte for
byte; the signature is *original foreign proof* and must survive any supported
modification (an annotation edit) untouched.

    python tests/fixtures/cross_producer.py            # (re)write the fixture
    python tests/fixtures/cross_producer.py --check    # exit 1 if it would change
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from openpicture import container, ed25519, embeddings, runs, sign  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "cross-producer.opi"

# A throwaway fixture key (never a real producer key).
SECRET = bytes.fromhex("5243eaeec429125621c9ab0d9af4e86c892671b9be124e2e1fbd1cd6ebe6ddfa")
SIGNER = "urn:foreign:producer"
MEDIA = b"FOREIGN-MEDIA-BYTES-01"
MEDIA_SHA = hashlib.sha256(MEDIA).hexdigest()
EMBEDDING_ROWS = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8], [0.9, 0.0, 0.1, 0.2]]
FRAME_SPANS = [(0, 24), (24, 101), (101, 240)]  # 23.976 fps: 4.2 s falls in frame 101


def build_manifest() -> tuple[dict, dict[str, bytes]]:
    member = embeddings.member_name("foreign-clip-v1")
    data = embeddings.pack_vectors(
        EMBEDDING_ROWS, 4, model="foreign-clip", model_version="v1", scope="shot",
        frame_spans=FRAME_SPANS)
    attachment = embeddings.attachment_entry(data)  # carries spans: "frame"
    manifest = {
        "opi": 0,
        "profile": "full",
        "generator": "ForeignTool 2.0",
        "media_binding": {
            "timecode": {"start": "01:00:00:00", "rate": {"num": 24000, "den": 1001},
                         "drop_frame": False, "label": "23.976"},
            "duration_frames": 240,
            "files": [{
                "role": "original", "name": "FOREIGN_CAM_01.mov", "size": len(MEDIA),
                "sha256": MEDIA_SHA,
                # F3: an absolute path a foreign writer left in. Informative,
                # untrusted, never a failure condition.
                "path": "/Volumes/CARD_A/DCIM/FOREIGN_CAM_01.mov",
                "video_codec": "prores", "width": 1920, "height": 1080, "fps": 23.976,
            }],
            "provenance": [{"source_label": "A001",
                            "original_path": "E:\\DCIM\\FOREIGN_CAM_01.mov"}],
        },
        "machine_intelligence": [{
            "run_id": runs.run_id("x-foreign:embed", "foreign-v1", MEDIA_SHA),
            "producer": "x-foreign:embed",
            "model_version": "foreign-v1",
            "generator": "ForeignTool 2.0",
            "generated_at": "2026-09-01T12:00:00Z",
            "egress": "derived",
            "confidence_scale": "unit",
            # an unknown run key: preserved and ignored (§7.2)
            "vendor_note": {"nested": [1, 2, 3]},
            "facets": {
                # F2: canonical facet entry with a searchable `text`
                "x-foreign.scene": [
                    {"span": {"frame_in": 0, "frame_out": 24}, "confidence": 0.9,
                     "text": "wide establishing shot", "label": "establishing"},
                    {"span": {"frame_in": 24, "frame_out": 101}, "confidence": 0.7,
                     "text": "two-shot dialogue", "label": "dialogue"},
                ],
            },
            "attachments": {member: attachment},
        }],
        "editorial_annotations": {
            # F5: record provenance, no `by` — a machine signer is not a person
            "labels": [{"id": "fl-1", "name": "select", "value": "opening wide",
                        "created_by": "opi:foreign-signer",
                        "span": {"frame_in": 0, "frame_out": 24}}],
            # F4: non-label clauses the producer must carry forward verbatim
            "rating": 4,
            "mam": {"field": {"show": "fixture", "reel": "A001"}},
            "colourist": {"lut": "show_v3"},
        },
    }
    sign.sign_run(manifest, 0, SECRET, signer=SIGNER, signed_at="2026-09-01T12:00:01Z")
    return manifest, {member: data}


def build_bytes() -> bytes:
    import tempfile
    manifest, members = build_manifest()
    with tempfile.TemporaryDirectory(prefix="opi-cross-") as tmp:
        path = Path(tmp) / OUT.name
        container.write_full(manifest, path, members, aligned=set(members))
        return path.read_bytes()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = build_bytes()
    if argv[:1] == ["--check"]:
        current = OUT.read_bytes() if OUT.exists() else b""
        if current != text:
            print(f"{OUT.relative_to(ROOT)} is out of date; run tests/fixtures/cross_producer.py", file=sys.stderr)
            return 1
        print("cross-producer fixture up to date")
        return 0
    OUT.write_bytes(text)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
