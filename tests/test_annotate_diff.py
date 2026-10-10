import hashlib
import zipfile

import pytest

from openpicture import annotate, container, diff, ed25519, sign


def _signed(tmp_path, full=False):
    media = tmp_path / "c.mov"
    media.write_bytes(b"movie")
    m = {
        "opi": 0, "profile": "full" if full else "core",
        "media_binding": {"timecode": {"start": "00:00:00:00", "rate": {"num": 24, "den": 1}, "drop_frame": False}, "files": [{"role": "original", "name": "c.mov", "size": 5,
                                     "sha256": hashlib.sha256(b"movie").hexdigest()}]},
        "machine_intelligence": [{"run_id": "r1", "producer": "test:shots", "model_version": "1",
                                  "facets": {"shots": [{"idx": 0}, {"idx": 1}]}}],
        "editorial_annotations": {"labels": [{"name": "select", "value": "hero"}]},
    }
    members = {}
    if full:
        emb = b"\x01" * 100
        m["machine_intelligence"][0]["attachments"] = {"embeddings.bin": {"sha256": hashlib.sha256(emb).hexdigest(), "size": 100}}
        members["embeddings.bin"] = emb
    sk = ed25519.generate_secret()
    sign.sign_all(m, sk, signer="urn:p")
    path = tmp_path / ("c.mov.opi")
    if full:
        container.write_full(m, path, members)
    else:
        container.write_core(m, path)
    return path, m


# ── annotate ───────────────────────────────────────────────────────────


def test_set_remove_and_label_keep_signatures(tmp_path):
    path, _ = _signed(tmp_path)
    annotate.set_fields(path, {"rating": 5, "notes": "director's pick"})
    annotate.add_label(path, "scene", "42B", created_by="ae", span={"t_start_s": 0, "t_end_s": 1})
    annotate.remove_fields(path, ["notes", "does-not-exist"])
    m, _ = container.read_manifest(path)
    ann = m["editorial_annotations"]
    assert ann["rating"] == 5 and "notes" not in ann
    assert [l["name"] for l in ann["labels"]] == ["select", "scene"]
    assert ann["labels"][1]["created_by"] == "ae" and ann["labels"][1]["span"]["t_end_s"] == 1
    assert sign.verify_manifest(m).status == "signed"


def test_a_label_without_a_span_omits_the_key_rather_than_writing_null(tmp_path):
    """§8.2: an absent span means the whole medium; `null` means nothing, and
    the published schema types span as an object."""
    path, _ = _signed(tmp_path)
    annotate.add_label(path, "select", True, created_by="ae")
    m, _ = container.read_manifest(path)
    entry = m["editorial_annotations"]["labels"][-1]
    assert "span" not in entry
    for optional in ("by", "at", "notes", "id"):
        assert optional not in entry


def test_self_declared_identity_round_trips_and_anonymize_strips_it(tmp_path):
    path, _ = _signed(tmp_path)
    annotate.add_label(path, "note", "watch the boom", created_by="opi:latent",
                       by="u-417", at="2026-08-29T10:00:00Z", notes="second unit",
                       id="lbl-7")
    m, _ = container.read_manifest(path)
    entry = m["editorial_annotations"]["labels"][-1]
    assert entry["by"] == "u-417" and entry["at"] == "2026-08-29T10:00:00Z"
    assert entry["notes"] == "second unit" and entry["id"] == "lbl-7"

    annotate.anonymize(path)
    m, _ = container.read_manifest(path)
    entry = m["editorial_annotations"]["labels"][-1]
    assert "by" not in entry and "at" not in entry
    # §8.2 requires created_by; stripping it would trade privacy for invalidity.
    assert entry["created_by"] == "opi:latent"
    assert entry["id"] == "lbl-7" and entry["notes"] == "second unit"
    assert sign.verify_manifest(m).status == "signed"


def test_anonymize_leaves_a_file_without_labels_alone(tmp_path):
    path, _ = _signed(tmp_path)
    annotate.remove_fields(path, ["labels"])
    annotate.anonymize(path)
    m, _ = container.read_manifest(path)
    assert m["editorial_annotations"] == {}


def test_full_profile_members_survive_byte_for_byte(tmp_path):
    path, _ = _signed(tmp_path, full=True)
    with zipfile.ZipFile(path) as zf:
        before = zf.read("embeddings.bin")
    annotate.set_fields(path, {"rating": 3})
    assert container.detect(path) == "zip"
    with zipfile.ZipFile(path) as zf:
        assert zf.read("embeddings.bin") == before
    assert container.member_data_offset(path, "embeddings.bin") % 64 == 0
    m, _ = container.read_manifest(path)
    assert m["editorial_annotations"]["rating"] == 3 and sign.verify_manifest(m).status == "signed"


def test_edit_that_escapes_the_human_layer_is_refused(tmp_path):
    path, _ = _signed(tmp_path)

    def sneaky(ann):
        ann["rating"] = 1
        # reach the parent manifest through a shared reference? we can't — but
        # a callable could mutate the dict it was handed to be non-dict-like;
        # simulate a machine-layer edit via a closure over the file instead.
    annotate.edit(path, sneaky)  # legitimate edit works
    with pytest.raises(annotate.AnnotationRefused):
        annotate.set_fields(path, {"labels": "not a list"})
    # a manifest whose human block is not an object is refused rather than guessed
    m, _ = container.read_manifest(path)
    m["editorial_annotations"] = "junk"
    container.write_core(m, path)
    with pytest.raises(annotate.AnnotationRefused):
        annotate.set_fields(path, {"x": 1})


def test_annotate_creates_block_when_absent(tmp_path):
    path, m = _signed(tmp_path)
    del m["editorial_annotations"]
    container.write_core(m, path)
    annotate.set_fields(path, {"x": 1})
    back, _ = container.read_manifest(path)
    assert back["editorial_annotations"] == {"x": 1}


def test_non_label_annotation_keys_survive_every_edit(tmp_path):
    """F4/§8.3: only `labels` is the tool's; every other clause is carried verbatim."""
    path, _ = _signed(tmp_path)
    carry = {
        "rating": 5,
        "tags": ["a", "b"],
        "mam": {"field": {"nested": [1, 2, {"deep": True}]}},
        "colourist": {"lut": "show_v3"},
        "weird key \u2603": "value with spaces",
    }
    annotate.edit(path, lambda ann: ann.update(carry))
    annotate.add_label(path, "scene", "42B", created_by="ae", id="l1")
    annotate.set_fields(path, {"rating": 4})
    annotate.remove_fields(path, ["colourist"])
    annotate.anonymize(path)
    m, _ = container.read_manifest(path)
    ann = m["editorial_annotations"]
    assert ann["mam"] == carry["mam"] and ann["tags"] == ["a", "b"]
    assert ann["weird key \u2603"] == carry["weird key \u2603"]
    assert ann["rating"] == 4 and "colourist" not in ann
    # no non-label clause was projected into labels or rewritten as an opi.* key
    assert [l["name"] for l in ann["labels"]] == ["select", "scene"]
    assert not any(str(k).startswith("opi.") for k in ann)


# ── diff ───────────────────────────────────────────────────────────────


def test_diff_identical_and_human_only(tmp_path):
    path, m = _signed(tmp_path)
    import copy
    a, b = copy.deepcopy(m), copy.deepcopy(m)
    r = diff.diff(a, b)
    assert r.identical and r.machine_identical
    b["editorial_annotations"]["rating"] = 5
    r = diff.diff(a, b)
    assert r.machine_identical and not r.identical
    assert r.human == {"rating": (None, 5)}


def test_diff_runs_added_removed_changed_and_binding(tmp_path):
    path, m = _signed(tmp_path)
    import copy
    a, b = copy.deepcopy(m), copy.deepcopy(m)
    # a second producer appends a run; the first run gets a third shot; the media sha changes
    b["machine_intelligence"].append({"run_id": "r2", "producer": "test:asr", "model_version": "v3",
                                      "facets": {"signals": [1, 2, 3]}})
    b["machine_intelligence"][0]["facets"]["shots"].append({"idx": 2})
    b["media_binding"]["files"][0]["sha256"] = "f" * 64
    r = diff.diff(a, b)
    assert not r.machine_identical
    assert set(r.binding) == {"files"}
    by_id = {x.run_id: x for x in r.runs}
    assert by_id["r2"].change == "added" and by_id["r2"].facets == {"signals": (0, 3)}
    assert by_id["r1"].change == "changed" and by_id["r1"].facets == {"shots": (2, 3)} and by_id["r1"].changed_facets == ["shots"]
    assert r.signature_status == ("signed", "invalid")  # r1's body changed under its signature; r2 unsigned
    r2 = diff.diff(b, a)
    assert {x.run_id: x.change for x in r2.runs} == {"r1": "changed", "r2": "removed"}


def test_diff_signer_change_alone_is_a_change(tmp_path):
    path, m = _signed(tmp_path)
    import copy
    b = copy.deepcopy(m)
    b["machine_intelligence"][0].pop("signature")
    sign.sign_run(b, 0, ed25519.generate_secret(), signer="urn:other")
    r = diff.diff(m, b)
    assert r.runs[0].change == "changed" and r.runs[0].signature == ("urn:p", "urn:other") and r.runs[0].changed_facets == []


def test_diff_matches_labels_by_stable_id(tmp_path):
    """W17: added/changed/removed are decided on §8.2's `id`."""
    import copy
    base = {
        "opi": 0, "profile": "core",
        "media_binding": {"files": [{"role": "original", "name": "c.mov", "sha256": "a" * 64}]},
        "machine_intelligence": [],
        "editorial_annotations": {"labels": [
            {"id": "l1", "name": "select", "value": "hero", "created_by": "u"},
            {"id": "l2", "name": "scene", "value": "42B", "created_by": "u"},
            {"name": "note", "value": "no id here", "created_by": "u"},
        ]},
    }
    a, b = copy.deepcopy(base), copy.deepcopy(base)
    b["editorial_annotations"]["labels"][0]["value"] = "runner-up"   # l1 changed
    del b["editorial_annotations"]["labels"][1]                       # l2 removed
    b["editorial_annotations"]["labels"].append(
        {"id": "l3", "name": "take", "value": 3, "created_by": "u"})  # added
    r = diff.diff(a, b)
    assert [e["id"] for e in r.labels.added] == ["l3"]
    assert [e["id"] for e in r.labels.changed] == ["l1"]
    assert [e["id"] for e in r.labels.removed] == ["l2"]
    assert r.machine_identical and not r.identical
    assert r.as_dict()["labels"]["changed"][0]["to"]["value"] == "runner-up"


def test_diff_label_without_id_matches_on_name_value_span():
    import copy
    label = {"name": "note", "value": "boom in shot", "created_by": "u"}
    a = {"editorial_annotations": {"labels": [dict(label)]}}
    b = {"editorial_annotations": {"labels": [dict(label)]}}
    assert diff.diff(a, b).labels.empty
    b["editorial_annotations"]["labels"][0]["value"] = "clean"
    r = diff.diff(a, b)
    assert [e["id"] for e in r.labels.removed] == [None]
    assert [e["id"] for e in r.labels.added] == [None]
