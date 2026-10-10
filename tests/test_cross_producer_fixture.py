"""The published cross-producer fixture (INGEST/EXCHANGE interface contract).

`tests/fixtures/cross-producer.opi` is a signed Full file from a foreign
producer. These tests are the executable statement of what a consumer must
get out of it, and that a supported modification leaves the original foreign
proof intact.
"""

import subprocess
import sys
from pathlib import Path

from openpicture import annotate, container, embeddings, reader, validate

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "cross-producer.opi"


def _rows(manifest):
    return manifest["machine_intelligence"][0]["facets"]["x-foreign.scene"]


def test_fixture_is_reproducible():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "fixtures" / "cross_producer.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_validator_accepts_it_as_original_signed_proof():
    report = validate.validate(FIXTURE)
    assert report.ok and report.status == "valid-signed", [c for c in report.checks if not c.ok]


def test_reader_binds_by_hash_and_ignores_foreign_absolute_paths():
    side = reader.load(FIXTURE)
    assert side.sha256  # read from media_binding, never the path
    original = side.original
    assert original["name"] == "FOREIGN_CAM_01.mov"
    assert original["path"].startswith("/")  # present, informative, untrusted
    # the binding is by bytes; the path was never used to pair or fail
    report = validate.validate(FIXTURE)
    assert not any(not c.ok and "path" in c.name for c in report.checks)


def test_frame_spans_survive_from_a_foreign_member():
    side = reader.load(FIXTURE)
    run = side.runs[0]
    member = next(iter(run.attachments))
    _, tensors = embeddings.unpack(side.read_member(member))
    assert embeddings.spans(tensors) == ("frame", [(0, 24), (24, 101), (101, 240)])
    assert run.attachments[member]["spans"] == "frame"


def test_canonical_text_key_is_searchable():
    side = reader.load(FIXTURE)
    assert [e.get("text") for e in _rows(side.manifest)] == [
        "wide establishing shot", "two-shot dialogue"]


def test_machine_signer_never_becomes_a_human_attribution():
    side = reader.load(FIXTURE)
    label = side.annotations["labels"][0]
    assert label["created_by"] == "opi:foreign-signer"
    assert "by" not in label  # F5: not invented from the run's signer


def test_supported_edit_preserves_unknown_fields_and_original_proof(tmp_path):
    import shutil
    work = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, work)
    before, _ = container.read_manifest(work)
    before_sig = before["machine_intelligence"][0]["signature"]

    annotate.add_label(work, "note", "reviewed for the fixture", created_by="ae", id="fl-2")
    after, _ = container.read_manifest(work)

    # original foreign proof is byte-identical, so it still verifies
    assert after["machine_intelligence"][0]["signature"] == before_sig
    assert validate.validate(work).status == "valid-signed"
    # unknown run key survives
    assert after["machine_intelligence"][0]["vendor_note"] == {"nested": [1, 2, 3]}
    # non-label annotation clauses survive verbatim (F4)
    assert after["editorial_annotations"]["mam"] == {"field": {"show": "fixture", "reel": "A001"}}
    assert after["editorial_annotations"]["colourist"] == {"lut": "show_v3"}
    assert after["editorial_annotations"]["rating"] == 4
    # the new label sits beside the foreign one, which is untouched
    names = [l["name"] for l in after["editorial_annotations"]["labels"]]
    assert names == ["select", "note"]
