"""Spec chapter 6A — the time model — proven against vectors/time/*.json and,
where available, frame by frame against the reference producer's converter."""

import json
import os
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from openpicture import time as T

VEC = Path(__file__).resolve().parent.parent / "vectors" / "time"


def _load(name):
    return json.loads((VEC / name).read_text())


def _rate(case):
    r = case["rate"]
    return T.Rate(r["num"], r["den"], bool(case.get("drop_frame", False)))


def _frac(d):
    return Fraction(d["num"], d["den"])


# ── rates.json ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", _load("rates.json")["cases"], ids=lambda c: f"{c['rate']['num']}/{c['rate']['den']}{'DF' if c.get('drop_frame') else ''}")
def test_rate_vectors(case):
    if "error" in case:
        with pytest.raises(ValueError):
            T.Rate(case["rate"]["num"], case["rate"]["den"], case["drop_frame"])
        return
    r = T.Rate(case["rate"]["num"], case["rate"]["den"], case["drop_frame"])
    assert r.label == case["label"]
    assert r.nominal == case["nominal"]
    assert r.dropped_per_minute == case["dropped_per_minute"]
    assert r.has_timecode == case["has_timecode"]
    assert T.Rate.from_dict(case["rate"], case["drop_frame"]) == r
    assert r.to_dict() == case["rate"]


@pytest.mark.parametrize("case", _load("rates.json")["labels"], ids=lambda c: c["label"])
def test_rate_label_vectors(case):
    if "error" in case:
        with pytest.raises(ValueError):
            T.Rate.parse(case["label"])
        return
    r = T.Rate.parse(case["label"])
    assert r.to_dict() == case["rate"] and r.drop_frame == case["drop_frame"]


def test_rate_snaps_probe_floats_and_refuses_floats_in_manifests():
    assert T.Rate.from_fps(23.976023976).fps == Fraction(24000, 1001)
    assert T.Rate.from_fps("29.97", drop_frame=True).dropped_per_minute == 2
    with pytest.raises(ValueError):
        T.Rate.from_fps(27.5)
    with pytest.raises(ValueError):
        T.Rate.from_dict({"num": 23.976, "den": 1})
    with pytest.raises(ValueError):
        T.Rate(True, 1)


# ── timecode.json ──────────────────────────────────────────────────────

@pytest.mark.parametrize("case", _load("timecode.json")["cases"], ids=lambda c: c["label"])
def test_timecode_vectors(case):
    r = _rate(case)
    t = T.Timecode.parse(case["label"], r)
    assert t.frames == case["frames"]
    assert str(t) == case["label"]
    assert t.seconds == _frac(case["seconds"])
    assert T.frames_to_seconds(case["frames"], r) == _frac(case["seconds"])
    assert str(T.Timecode(case["frames"], r)) == case["label"]


def test_sequence_across_the_first_drop_point():
    seq = _load("timecode.json")["sequence_29_97_DF_across_first_minute"]
    r = T.Rate(30000, 1001, True)
    labels = [str(T.Timecode(c["frames"], r)) for c in seq]
    assert labels == [c["label"] for c in seq]
    assert "00:01:00;00" not in labels and "00:01:00;01" not in labels
    assert labels[labels.index("00:00:59;29") + 1] == "00:01:00;02"


@pytest.mark.parametrize("case", _load("timecode.json")["labels"], ids=lambda c: c["label"])
def test_timecode_label_edge_cases(case):
    r = _rate(case)
    if case.get("valid"):
        assert str(T.Timecode.parse(case["label"], r)) == case["label"]
    else:
        with pytest.raises(ValueError):
            T.Timecode.parse(case["label"], r)


def test_either_separator_is_accepted_and_rate_decides():
    df = T.Rate(30000, 1001, True)
    assert T.Timecode.parse("00:01:00:02", df).frames == T.Timecode.parse("00:01:00;02", df).frames
    assert str(T.Timecode.parse("00:01:00:02", df)) == "00:01:00;02"
    with pytest.raises(ValueError):
        T.Timecode(-1, df)


# ── spans.json ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", _load("spans.json")["cases"], ids=lambda c: f"{c['rate']['num']}:{c.get('t_start_s')}-{c.get('t_end_s')}")
def test_span_vectors(case):
    r = _rate(case)
    if "error" in case:
        with pytest.raises(ValueError):
            T.span_from_seconds(case["t_start_s"], case["t_end_s"], r)
        return
    fi, fo = T.span_from_seconds(case["t_start_s"], case["t_end_s"], r)
    assert (fi, fo) == (case["frame_in"], case["frame_out"])
    assert fo > fi
    assert T.frames_to_seconds(fi, r) == _frac(case["t_start_s_exact"])
    assert T.frames_to_seconds(fo, r) == _frac(case["t_end_s_exact"])


def test_seconds_to_frames_modes():
    r = T.Rate(24)
    assert T.seconds_to_frames("1.5", r) == 36
    assert T.seconds_to_frames("1.02", r, "floor") == 24
    assert T.seconds_to_frames("1.02", r, "ceil") == 25
    assert T.seconds_to_frames("1.02", r, "round") == 24
    assert T.seconds_to_frames(Fraction(3, 2), r, "round") == 36
    with pytest.raises(ValueError):
        T.seconds_to_frames(-0.1, r)
    with pytest.raises(ValueError):
        T.seconds_to_frames(1, r, "nearest")


# ── consistency.json ───────────────────────────────────────────────────

@pytest.mark.parametrize("case", _load("consistency.json")["cases"], ids=lambda c: c["note"])
def test_consistency_vectors(case):
    rate = T.Rate(case["rate"]["num"], case["rate"]["den"], bool(case["drop_frame"])) if case["rate"] else None
    start = T.Timecode.parse(case["start"], rate) if case["start"] else None
    errs = T.check_span(case["span"], rate, start)
    assert (not errs) == case["valid"], errs


def test_checks_over_a_manifest_and_report_shape():
    m = {
        "media_binding": {"timecode": {"start": "01:00:00:00", "rate": {"num": 24000, "den": 1001},
                                       "drop_frame": False, "label": "23.976"}},
        "machine_intelligence": [
            {"facets": {"shots": [{"idx": 0, "span": {"frame_in": 0, "frame_out": 101, "tc_in": "01:00:00:00"}},
                                  {"idx": 1, "span": {"frame_in": 101, "frame_out": 100}}],
                        "signals": [{"span": {"t_start_s": 1.0, "t_end_s": 2.0}}]}},
        ],
        "editorial_annotations": {"labels": [{"name": "x", "span": {"frame_in": 3, "frame_out": 9, "frames": 6}}]},
    }
    rows = T.checks(m)
    names = {r[0]: r for r in rows}
    assert names["timecode.rate"][1] and names["timecode.start"][1] and names["timecode.label"][1]
    assert names["span run[0].facets.shots[1]"][1] is False
    assert names["spans"] == ("spans", False, "3/4 consistent")

    m["media_binding"]["timecode"]["drop_frame"] = True
    assert T.checks(m)[0] == ("timecode.rate", False, T.checks(m)[0][2]) and "drop_frame" in T.checks(m)[0][2]

    m["media_binding"]["timecode"] = None
    rows = T.checks(m)
    assert rows[0][0] == "timecode" and rows[0][1]
    assert any(r[0].startswith("span run[0].facets.shots") and not r[1] for r in rows)  # frames without a rate


def test_checks_rejects_dropped_start_label():
    m = {"media_binding": {"timecode": {"start": "00:01:00;00", "rate": {"num": 30000, "den": 1001}, "drop_frame": True}}}
    rows = {r[0]: r for r in T.checks(m)}
    assert rows["timecode.start"][1] is False and "dropped" in rows["timecode.start"][2]


# ── interop.json ───────────────────────────────────────────────────────

@pytest.mark.parametrize("case", _load("interop.json")["cases"], ids=lambda c: f"{c['rate']['num']}@{c['frames']}")
def test_interop_vectors(case):
    r = _rate(case)
    start = T.Timecode.parse(case["start"], r)
    f = case["frames"]
    assert T.fcpxml_time(f, r) == case["fcpxml_time"]
    assert T.fcpxml_frame_duration(r) == case["fcpxml_frameDuration"]
    assert T.otio_rational_time(f, r) == case["otio"]
    assert T.edl_fcm(r) == case["edl_fcm"]
    assert T.edl_timecode(f, start) == case["edl_source_tc"]
    tb, ntsc = T.xmeml_timebase(r)
    assert {"timebase": tb, "ntsc": ntsc, "frames": f} == case["xmeml"]
    # FCPXML is lossless: parse the rational back to the same frame
    text = case["fcpxml_time"][:-1]
    value = Fraction(text) if "/" in text else Fraction(int(text))
    assert value * r.fps == f
    # OTIO is lossy in rate but round() recovers the frame
    assert round(case["otio"]["value"]) == f and abs(case["otio"]["rate"] - float(r.fps)) < 1e-9


# ── cross-check against the reference producer's converter ─────────────

@pytest.fixture(scope="module")
def latent_timecode():
    root = os.environ.get("OPI_LATENT_CHECKOUT")
    if not root:
        pytest.skip("set OPI_LATENT_CHECKOUT to a latent checkout to run the port cross-check")
    if not (Path(root) / "latent" / "core" / "timecode.py").exists():
        pytest.skip("OPI_LATENT_CHECKOUT does not contain latent/core/timecode.py")
    sys.path.insert(0, str(root))
    try:
        from latent.core import timecode
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"latent import failed: {exc}")
    return timecode


@pytest.mark.parametrize("num,den,df", [(30000, 1001, True), (60000, 1001, True), (24000, 1001, False), (25, 1, False)])
def test_port_is_identical_to_latent_over_twenty_minutes(latent_timecode, num, den, df):
    L = latent_timecode
    ours = T.Rate(num, den, df)
    theirs = L.Rate(Fraction(num, den), df)
    n = int(Fraction(num, den) * 1200)
    for f in range(n):
        label = str(T.Timecode(f, ours))
        assert label == str(L.Timecode(f, theirs)), f
        assert T.Timecode.parse(label, ours).frames == f
