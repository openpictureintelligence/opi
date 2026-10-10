import json
from pathlib import Path

import pytest

from openpicture import facets

ROOT = Path(__file__).resolve().parent.parent
VEC = ROOT / "vectors" / "facets"
SCHEMA = json.loads((ROOT / "schema" / "facets-0.schema.json").read_text())

ROW_KINDS = {"transcript", "description", "usability"}


def _manifest_with(name: str, entry, *, row_form: bool = False) -> dict:
    run = {"run_id": "r1", "producer": "test", "model_version": "1", "facets": {}}
    items = entry if isinstance(entry, list) else [entry]
    if name in ROW_KINDS:
        run["facets"]["signals"] = items
    elif row_form:
        run["facets"]["signals"] = [
            {"kind": f"facet.{name}", "span": e.get("span"), "confidence": e.get("confidence"),
             "coverage": e.get("coverage"), "payload": {k: v for k, v in e.items() if k not in ("span", "confidence", "coverage")}}
            for e in items
        ]
    else:
        run["facets"][name] = items
    return {"opi": 0, "profile": "core", "media_binding": {"files": []}, "machine_intelligence": [run]}


def _failures(report):
    return [c for c in report if not c.ok]


# ── vocabulary ────────────────────────────────────────────────────────


def test_vocabulary_matches_appendix_and_schema():
    assert facets.CAMERA_MOTION_VERBS == ("fixed", "pan", "tilt", "roll", "zoom", "dolly", "track", "boom")
    assert facets.SHOT_SIZES == ("ECU", "CU", "MCU", "MS", "MWS", "WS", "EWS")
    schema_verbs = SCHEMA["$defs"]["camera_motion"]["properties"]["verb"]["enum"]
    assert set(schema_verbs) == set(facets.CAMERA_MOTION_VERBS_EXTENDED)
    assert SCHEMA["$defs"]["shot_size"]["properties"]["value"]["enum"] == list(facets.SHOT_SIZES)
    assert SCHEMA["$defs"]["clearance"]["properties"]["review_required"] == {"const": True} | {
        k: v for k, v in SCHEMA["$defs"]["clearance"]["properties"]["review_required"].items() if k != "const"}
    # every facet in code has a schema list property (row kinds live under signals)
    for name in facets.FACETS:
        if name in ROW_KINDS:
            continue
        assert name in SCHEMA["properties"], name


def test_describe_tolerates_prefix_and_reports_maturity():
    assert facets.describe("facet.camera_motion").maturity == "research"
    assert facets.describe("continuity").maturity == "research"
    assert facets.describe("nope") is None
    stable = {n for n, f in facets.FACETS.items() if f.maturity == "stable"}
    assert stable == {"shots", "transcript", "usability", "exposure_color",
                      "energy_curve", "audio_usability"}


def test_shape_and_maturity_are_independent_axes():
    """B12: `camera_motion` is a frozen shape computed by a research producer.

    Collapsing the two axes into one word is what the decision had to undo,
    so this pins that they can disagree — in both directions.
    """
    cm = facets.describe("camera_motion")
    assert cm.frozen and cm.maturity == "research"
    desc = facets.describe("description")
    assert not desc.frozen and desc.maturity == "proposed"
    assert all(f.shape in ("frozen", "proposed") for f in facets.FACETS.values())


def test_b12_froze_exactly_these_facets():
    """The frozen set is a format commitment; it does not drift by edit."""
    assert facets.FROZEN == {
        "shots", "transcript", "usability", "exposure_color",
        "energy_curve", "audio_usability", "camera_motion",
    }
    # `clearance` is never frozen as a quality claim (§10.3, C.0.0)
    assert "clearance" not in facets.FROZEN


def test_appendix_c_marks_the_same_facets_frozen_as_the_code():
    """The prose and `FACETS` must not disagree about what a reader may rely on."""
    text = (ROOT / "spec" / "appendix-c-proposed-facet-vocabulary-non-normative.md").read_text()
    head = text[text.index("### C.19 Summary"):]
    for name, f in facets.FACETS.items():
        if name == "embeddings":
            continue                     # frozen by §7b.3 as an attachment, not as a facet
        label = "transcript" if name == "transcript" else name
        row = next(l for l in head.splitlines()
                   if l.startswith(f"| `{label}`"))
        assert ("**frozen**" in row) == f.frozen, row
        assert f"| {f.maturity} |" in row, row


def test_log_profile_vocabulary_is_enumerated_and_extensible():
    """B12 Q4: enums make files comparable; `x-` keeps a new encode nameable."""
    assert "Nikon_NLog" in facets.LOG_PROFILES and "BMD_BRAWFilm" in facets.LOG_PROFILES
    assert facets.LOG_PROFILE_EXT_RE.match("x-DJI_DLog")
    assert not facets.LOG_PROFILE_EXT_RE.match("DJI_DLog")

    def rows(profile):
        entry = {"mean_ire": 40.0, "clipped_highlight_ratio": 0.0, "crushed_black_ratio": 0.0,
                 "contrast": 0.2, "wb_drift": {"r_over_g": 1.0, "b_over_g": 1.0},
                 "log_profile_likely": True, "frames_sampled": 4, "log_profile": profile,
                 "confidence": None}
        return [c for c in facets.checks({"machine_intelligence": [
            {"facets": {"exposure_color": [entry]}}]}) if not c.ok]

    assert not rows("Sony_SLog3") and not rows("x-DJI_DLog") and not rows(None)
    assert rows("S-Log3"), "free text must not pass a frozen enum"


# ── vectors ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", sorted(VEC.glob("valid-*.json")), ids=lambda p: p.stem)
def test_valid_vectors_pass(path):
    v = json.loads(path.read_text())
    report = facets.checks(_manifest_with(v["facet"], v["entry"]))
    assert not _failures(report), [(c.name, c.detail) for c in _failures(report)]
    assert any(c.ok and v["facet"] in c.name for c in report)


@pytest.mark.parametrize("path", sorted(VEC.glob("valid-*.json")), ids=lambda p: p.stem)
def test_valid_vectors_pass_in_row_form(path):
    v = json.loads(path.read_text())
    if v["facet"] in ROW_KINDS or isinstance(v["entry"], list):
        pytest.skip("already a row form or a shots list")
    report = facets.checks(_manifest_with(v["facet"], v["entry"], row_form=True))
    assert not _failures(report), [(c.name, c.detail) for c in _failures(report)]


@pytest.mark.parametrize("path", sorted(VEC.glob("invalid-*.json")), ids=lambda p: p.stem)
def test_invalid_vectors_are_flagged(path):
    v = json.loads(path.read_text())
    report = facets.checks(_manifest_with(v["facet"], v["entry"]))
    bad = _failures(report)
    assert bad, "expected a failure"
    assert any(v["expect_failure_in"] in c.name or v["expect_failure_in"] in c.detail for c in bad), \
        [(c.name, c.detail) for c in bad]


def test_sensitive_facet_violations_are_conformance_level():
    m = _manifest_with("clearance", {"span": {"frame_in": 0, "frame_out": 1}, "flag": "minor",
                                     "confidence": 0.5, "recall": 0.9})
    bad = _failures(facets.checks(m))
    assert "conformance" in {c.level for c in bad}
    assert any("review_required" in c.name for c in bad) and any("accuracy claim" in c.name for c in bad)


# ── rules ─────────────────────────────────────────────────────────────


def test_unknown_facets_pass():
    m = _manifest_with("something_new", {"whatever": 1})
    m["machine_intelligence"][0]["facets"]["signals"] = [{"kind": "facet.other_new", "payload": {"x": 1}}]
    assert facets.checks(m) == []


def test_measured_facet_with_confidence_is_read_as_coverage_not_failed():
    v = json.loads((VEC / "valid-exposure_color.json").read_text())["entry"]
    v = dict(v); v.pop("coverage", None); v["confidence"] = 0.95
    report = facets.checks(_manifest_with("exposure_color", v))
    assert not _failures(report)
    assert any("read as coverage" in c.detail for c in report)


def test_basis_point_scale_is_honoured():
    m = _manifest_with("camera_motion", {"span": {"frame_in": 0, "frame_out": 10}, "verb": "pan", "samples": 4, "confidence": 8200})
    assert _failures(facets.checks(m))  # unit scale by default
    m["machine_intelligence"][0]["confidence_scale"] = "bp"
    assert not _failures(facets.checks(m))


def test_audio_usability_without_audio_may_have_null_confidence():
    m = _manifest_with("audio_usability", {"span": {"frame_in": 0, "frame_out": 10}, "dominant": None, "rms_dbfs": None,
                                           "noise_floor_dbfs": None, "speech_ratio": None, "clipping_ratio": None,
                                           "frames": 0, "confidence": None})
    assert not _failures(facets.checks(m))


def test_shots_dense_idx_and_span_order():
    m = _manifest_with("shots", [{"idx": 0, "span": {"frame_in": 0, "frame_out": 10}}, {"idx": 2, "span": {"frame_in": 10, "frame_out": 20}}])
    assert any("idx" in c.name for c in _failures(facets.checks(m)))
    m = _manifest_with("shots", [{"idx": 0, "span": {"frame_in": 5, "frame_out": 5}}])
    assert any("span" in c.name for c in _failures(facets.checks(m)))


def test_real_examples_pass_facet_checks():
    from openpicture import container
    for p in (ROOT / "examples").glob("*.opi"):
        manifest, _ = container.read_manifest(p)
        assert not _failures(facets.checks(manifest)), p.name
