"""Generate the manifest vectors (SPEC §5, §6, §8). Deterministic.

    python vectors/manifest/make_vectors.py            # write
    python vectors/manifest/make_vectors.py --check    # exit 1 on drift

Each vector is a JSON file: {"title", "spec", "manifest", "expect"} where
`expect` = {"schema": "valid"|"invalid", "validator": "valid"|"invalid"|null,
"check": <reference validator row a must-fail vector is rejected by, or null>}.
`validator: null` marks a rule the schema enforces but the reference
validator does not (yet) carry a row for.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from openpicture import runs  # noqa: E402

HERE = Path(__file__).resolve().parent
SHA = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"  # sha256(b"abc")
SHA2 = "fcde2b2edba56bf408601fb721fe9b5c338d10ee429ea04fac5fd1d8b1e5c22b"  # sha256(b"proxy")


def run(producer, mv, facets, **extra):
    r = {"run_id": runs.run_id(producer, mv, SHA), "producer": producer, "model_version": mv, "facets": facets}
    r.update(extra)
    return r


MINIMAL = {
    "opi": 0,
    "profile": "core",
    "media_binding": {"files": [{"name": "clip.mov", "sha256": SHA}]},
}

MAXIMAL = {
    "opi": 0,
    "profile": "core",
    "generator": "openpicture vectors 0",
    "generated_at": "2026-08-29T20:00:00Z",
    "$schema": "https://openpictureintelligence.org/schema/opi-0.schema.json",
    "media_binding": {
        "asset_id": "01a04db6-481c-7255-a87e-b426e1f2c130",
        "duration_s": 6.006,
        "duration_frames": 144,
        "shot_at": "2026-08-27T09:15:00-07:00",
        "camera": "ALEXA35",
        "ingested_at": "2026-08-29T13:29:46+00:00",
        "timecode": {
            "start": "01:00:00:00",
            "recorded": "01:00:00:00",
            "rate": {"num": 24000, "den": 1001},
            "drop_frame": False,
            "label": "23.976",
        },
        "files": [
            {
                "role": "original", "name": "clip.mov", "path": "clip.mov", "size": 3, "sha256": SHA,
                "xxh64be": "44bc2cf5ad770999", "container": "mov,mp4,m4a,3gp,3g2,mj2",
                "video_codec": "prores", "audio_codec": "pcm_s24le", "width": 3840, "height": 2160, "fps": 23.976,
            },
            {"role": "proxy", "name": "clip_proxy.mov", "size": 5, "sha256": SHA2, "video_codec": "h264",
             "audio_codec": "aac", "width": 1920, "height": 1080, "fps": 23.976},
            {"role": "audio", "name": "clip.wav", "size": 5, "sha256": SHA2, "video_codec": None,
             "audio_codec": "pcm_s24le", "width": None, "height": None, "fps": None},
        ],
        "provenance": [
            {"session_id": "01a04db6-479a-7e7e-adae-b6b2fe13357e", "original_path": "A001/clip.mov",
             "source_label": "A001", "checksum_verified_at": "2026-08-29T13:29:46Z", "note": None}
        ],
    },
    "machine_intelligence": [
        run("shots:scenedetect", "scenedetect-0.7",
            {"shots": [{"idx": 0, "confidence": None,
                        "span": {"frame_in": 0, "frame_out": 144, "t_start_s": 0.0, "t_end_s": 6.006,
                                 "tc_in": "01:00:00:00", "tc_out": "01:00:06:00", "frames": 144}}]},
            generator="openpicture vectors 0", generated_at="2026-08-29T19:00:00Z", egress="none",
            confidence_scale="unit"),
    ],
    "editorial_annotations": {
        "labels": [
            {"name": "select", "value": "hero", "created_by": "D", "created_at": "2026-08-29T13:30:43+00:00",
             "id": "lbl-1", "span": {"frame_in": 0, "frame_out": 48}},
            {"name": "flagged", "value": None, "created_by": "opi:urn:example:producer"},
        ],
        "rating": 5,
        "notes": "director's pick",
        "com.example.mam": {"bin": "B-roll/Day 3"},
    },
}


def fail(title, spec, mutate, *, schema="invalid", validator="invalid", check=None, base=None):
    m = copy.deepcopy(base or MAXIMAL)
    mutate(m)
    return {"title": title, "spec": spec, "manifest": m,
            "expect": {"schema": schema, "validator": validator, "check": check}}


def _two_originals(m):
    m["media_binding"]["files"][1]["role"] = "original"


def _no_original(m):
    m["media_binding"]["files"][0]["role"] = "transcode"


def _uppercase_sha(m):
    m["media_binding"]["files"][0]["sha256"] = SHA.upper()


def _missing_sha(m):
    del m["media_binding"]["files"][0]["sha256"]


def _bad_role(m):
    m["media_binding"]["files"][1]["role"] = "sidecar"


def _bad_generated_at(m):
    m["generated_at"] = "29 Aug 2026"


def _opi_string(m):
    m["opi"] = "0"


def _profile_mismatch(m):
    m["profile"] = "full"


def _duration_disagree(m):
    m["media_binding"]["duration_frames"] = 200  # 8.34 s vs duration_s 6.006


def _label_missing_created_by(m):
    del m["editorial_annotations"]["labels"][0]["created_by"]


def _annotations_not_object(m):
    m["editorial_annotations"] = ["hero"]


def _name_with_slash(m):
    m["media_binding"]["files"][0]["name"] = "A001/clip.mov"


VECTORS = {
    "valid-minimal.json": {
        "title": "Smallest valid manifest: version, profile, one original file",
        "spec": "§5.1, §6.3",
        "manifest": MINIMAL,
        "expect": {"schema": "valid", "validator": "valid", "check": None},
    },
    "valid-maximal.json": {
        "title": "Every optional envelope, binding and human-layer key exercised",
        "spec": "§5.1, §6.1, §6.2, §6.4, §8.1, §8.2",
        "manifest": MAXIMAL,
        "expect": {"schema": "valid", "validator": "valid", "check": None},
    },
    "invalid-two-originals.json": fail("Two files with role original", "§6.3", _two_originals,
                                    check="media_binding.original"),
    "invalid-no-original.json": fail("No file is the original", "§6.3", _no_original,
                                  check="media_binding.original"),
    "invalid-uppercase-sha256.json": fail("sha256 must be lowercase hex", "§6.2", _uppercase_sha,
                                       check="media_binding.files"),
    "invalid-missing-sha256.json": fail("Every file needs a sha256", "§6.2", _missing_sha,
                                     check="media_binding.files"),
    "invalid-bad-role.json": fail("role outside the enumeration", "§6.2", _bad_role, validator=None),
    "invalid-bad-generated-at.json": fail("generated_at must be RFC 3339", "§5.1", _bad_generated_at, validator=None),
    "invalid-opi-string.json": fail("opi must be an integer", "§5.1", _opi_string, check="opi version"),
    "invalid-profile-mismatch.json": fail("profile says full, members say core", "§5.1, §3.3", _profile_mismatch,
                                       schema="valid", check="profile matches contents"),
    "invalid-duration-disagree.json": fail("duration_frames disagrees with duration_s", "§6.1", _duration_disagree,
                                        schema="valid", check="time: duration"),
    "invalid-label-missing-created-by.json": fail("labels[] entries need created_by", "§8.2",
                                              _label_missing_created_by, validator=None),
    "invalid-annotations-not-object.json": fail("editorial_annotations must be an object", "§8.1",
                                            _annotations_not_object, check="editorial_annotations"),
    "invalid-name-with-slash.json": fail("files[].name is a basename", "§6.2", _name_with_slash,
                                      check="media_binding.files"),
}

OVERSIZE = {
    "title": "A manifest.json over 16 MiB is invalid and must not be parsed",
    "spec": "§5.6",
    "synthetic": "Build MAXIMAL, then pad editorial_annotations.notes until manifest_bytes() exceeds 16777216; "
                 "a validator reports `manifest size` without loading the JSON.",
    "limit_bytes": 16777216,
    "expect": {"schema": None, "validator": None, "check": "manifest size"},
}


def render(v) -> str:
    return json.dumps(v, indent=2, ensure_ascii=False) + "\n"


def main(argv) -> int:
    files = {**VECTORS, "invalid-oversize.json": OVERSIZE}
    drift = 0
    for name, v in files.items():
        text = render(v)
        path = HERE / name
        if "--check" in argv:
            if not path.exists() or path.read_text() != text:
                print(f"stale: {name}", file=sys.stderr)
                drift += 1
        else:
            path.write_text(text)
    if "--check" in argv:
        return 1 if drift else 0
    print(f"wrote {len(files)} vectors to {HERE}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
