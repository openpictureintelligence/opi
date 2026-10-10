import json
from pathlib import Path

import pytest

from openpicture import cli, companion, container, reader

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _manifest():
    return {
        "opi": 0, "profile": "core",
        "media_binding": {
            "asset_id": "a1", "duration_s": 6.0, "camera": "ALEXA35", "shot_at": None,
            "timecode": {"start": "01:00:00:00", "rate": {"num": 24000, "den": 1001}, "drop_frame": False, "label": "23.976"},
            "files": [{"role": "original", "name": "A001_C001.mov", "sha256": "a" * 64}],
        },
        "machine_intelligence": [
            {"run_id": "r1", "producer": "shots:scenedetect", "model_version": "0.7",
             "facets": {"shots": [{"idx": 0, "span": {"t_start_s": 0.0, "t_end_s": 2.0}},
                                  {"idx": 1, "span": {"t_start_s": 2.0, "t_end_s": 6.0}}],
                        "shot_size": [{"value": "CU", "confidence": 0.9}, {"value": "CU", "confidence": 0.8},
                                      {"value": "WS", "confidence": 0.7}]}},
            {"run_id": "r2", "producer": "asr:whisper", "model_version": "large-v3",
             "facets": {"signals": [
                 {"kind": "transcript", "text": "rolling", "span": {"t_start_s": 1.0, "t_end_s": 2.5}},
                 {"kind": "transcript", "text": "  and action ", "span": {"t_start_s": 3.0, "t_end_s": 4.0}},
                 {"kind": "usability", "text": None, "span": {"t_start_s": 0.0, "t_end_s": 1.0}}]}},
        ],
        "editorial_annotations": {"labels": [{"name": "select", "value": "hero"}, {"name": "flagged"}], "rating": 5},
    }


def test_iconik_shape_is_exactly_what_the_gateway_reads():
    doc = companion.iconik_json(_manifest())
    mv = doc["metadata_values"]
    assert mv["opi_media_name"] == {"field_values": [{"value": "A001_C001.mov"}]}
    assert mv["opi_shot_count"] == {"field_values": [{"value": "2"}]}
    assert mv["opi_transcript"]["field_values"][0]["value"] == "rolling and action"
    assert [v["value"] for v in mv["opi_labels"]["field_values"]] == ["select=hero", "flagged"]
    assert [v["value"] for v in mv["opi_shot_size"]["field_values"]] == ["CU", "WS"]
    assert "opi_shot_at" not in mv  # None is omitted, never blanks a view
    assert doc["segments"] == [
        {"start_milliseconds": 1000, "end_milliseconds": 2500, "text": "rolling", "segment_type": "transcript"},
        {"start_milliseconds": 3000, "end_milliseconds": 4000, "text": "and action", "segment_type": "transcript"},
    ]
    # every field_values entry is a string, as iconik expects
    assert all(isinstance(v["value"], str) for f in mv.values() for v in f["field_values"])


def test_flat_is_one_level_plus_segments():
    doc = companion.flat_json(_manifest())
    assert doc["opi_shot_count"] == 2 and doc["opi_frame_rate"] == "23.976"
    assert doc["opi_producers"] == ["asr:whisper@large-v3", "shots:scenedetect@0.7"]
    assert doc["opi_transcript_segments"][0] == {"start_ms": 1000, "end_ms": 2500, "text": "rolling"}
    for k, v in doc.items():
        if k == "opi_transcript_segments":
            continue
        assert not isinstance(v, dict), k
        if isinstance(v, list):
            assert all(isinstance(x, (str, int, float)) for x in v), k


def test_companion_path_is_same_basename_json():
    assert companion.companion_path("/x/A001_C001.mov.opi") == Path("/x/A001_C001.mov.json")
    assert companion.companion_path("/x/A001_C001.opi") == Path("/x/A001_C001.json")
    assert companion.companion_path("/x/c.mov.opi", "/out") == Path("/out/c.mov.json")


def test_write_companion_from_real_example_and_cli(tmp_path, capsys):
    src = EXAMPLES / "A001_C001.mov.opi"
    out = companion.write_companion(src, "iconik", dest=tmp_path)
    assert out == tmp_path / "A001_C001.mov.json"
    doc = json.loads(out.read_text())
    sc = reader.load(src)
    assert doc["metadata_values"]["opi_media_sha256"]["field_values"][0]["value"] == sc.sha256
    with pytest.raises(ValueError):
        companion.write_companion(src, "catdv", dest=tmp_path)
    assert cli.main(["companion", str(src), "--kind", "flat", "--dest", str(tmp_path)]) == 0
    assert "A001_C001.mov.json" in capsys.readouterr().out
    assert json.loads(out.read_text())["opi_shot_count"] >= 1
    (tmp_path / "bad.opi").write_bytes(b"nope")
    assert cli.main(["companion", str(tmp_path / "bad.opi")]) == 1
