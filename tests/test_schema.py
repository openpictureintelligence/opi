"""The envelope schema agrees with the files the implementation writes.

`jsonschema` is not a dependency of this package, so this test carries a
small stdlib checker that implements exactly the keywords
`schema/opi-0.schema.json` uses: type, const, enum, required, properties,
additionalProperties, patternProperties, items, minItems, maxItems,
contains/minContains/maxContains, minLength, maxLength, minimum, maximum,
exclusiveMinimum, pattern, oneOf, anyOf, not, allOf, $ref (local
`#/$defs/...` only). If `jsonschema`
happens to be importable it is run as well, so the two agree.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from openpicture import container

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "opi-0.schema.json").read_text())
FACETS = json.loads((ROOT / "schema" / "facets-0.schema.json").read_text())

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _resolve(ref: str, root: dict) -> dict:
    assert ref.startswith("#/"), ref
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def errors(value, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    root = root if root is not None else schema
    out: list[str] = []
    if "$ref" in schema:
        return errors(value, _resolve(schema["$ref"], root), root, path)
    if "allOf" in schema:
        for sub in schema["allOf"]:
            out += errors(value, sub, root, path)
    if "oneOf" in schema:
        hits = [s for s in schema["oneOf"] if not errors(value, s, root, path)]
        if len(hits) != 1:
            out.append(f"{path}: oneOf matched {len(hits)} branches")
        return out
    if "anyOf" in schema:
        if not any(not errors(value, s, root, path) for s in schema["anyOf"]):
            out.append(f"{path}: anyOf matched no branch")
    if "not" in schema:
        if not errors(value, schema["not"], root, path):
            out.append(f"{path}: matched a forbidden schema")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[t](value) for t in types):
            return [f"{path}: expected {types}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        out.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: {value!r} not in {schema['enum']}")
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(f"{path}: {value!r} does not match {schema['pattern']}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            out.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            out.append(f"{path}: longer than {schema['maxLength']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{path}: {value} < {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{path}: {value} > {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            out.append(f"{path}: {value} <= {schema['exclusiveMinimum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            out.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, item in enumerate(value):
                out += errors(item, schema["items"], root, f"{path}[{i}]")
        if "contains" in schema:
            n = sum(1 for item in value if not errors(item, schema["contains"], root, path))
            lo, hi = schema.get("minContains", 1), schema.get("maxContains")
            if n < lo:
                out.append(f"{path}: contains matched {n} items, fewer than {lo}")
            if hi is not None and n > hi:
                out.append(f"{path}: contains matched {n} items, more than {hi}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                out.append(f"{path}: missing required {key!r}")
        props = schema.get("properties", {})
        patterns = schema.get("patternProperties", {})
        for key, item in value.items():
            if key in props:
                out += errors(item, props[key], root, f"{path}.{key}")
                continue
            matched = False
            for pat, sub in patterns.items():
                if re.search(pat, key):
                    matched = True
                    out += errors(item, sub, root, f"{path}.{key}")
            if not matched and schema.get("additionalProperties", True) is False:
                out.append(f"{path}: additional property {key!r} not allowed")
    return out


def check(value):
    errs = errors(value, SCHEMA)
    try:  # cross-check with the real thing when it is around
        import jsonschema  # type: ignore

        try:
            jsonschema.validate(value, SCHEMA)
            assert not errs, f"jsonschema accepted but the local checker did not: {errs}"
        except jsonschema.ValidationError:
            assert errs, "jsonschema rejected but the local checker did not"
    except ImportError:
        pass
    return errs


@pytest.mark.parametrize("name", ["A001_C001.mov.opi", "A001_C001.mov.full.opi"])
def test_examples_conform(name):
    manifest, _ = container.read_manifest(ROOT / "examples" / name)
    assert check(manifest) == []


def _minimal():
    return {
        "opi": 0,
        "profile": "core",
        "media_binding": {"files": [{"name": "c.mov", "sha256": "0" * 64}]},
    }


def test_minimal_conforms_and_unknown_keys_are_fine():
    m = _minimal()
    m["future_key"] = {"anything": [1, 2]}
    m["media_binding"]["files"][0]["vendor_thing"] = True
    m["machine_intelligence"] = [{"run_id": "0" * 32, "producer": "x:y", "model_version": "1",
                                  "facets": {"brand_new_facet": 1}, "extra": 2}]
    assert check(m) == []


def test_schema_rejects_what_the_spec_rejects():
    m = _minimal(); m["opi"] = "0"
    assert check(m)
    m = _minimal(); m["opi"] = 1
    assert check(m)  # this schema is for version 0 only
    m = _minimal(); m["profile"] = "lite"
    assert check(m)
    m = _minimal(); m["media_binding"]["files"] = []
    assert check(m)
    m = _minimal(); m["media_binding"]["files"][0]["sha256"] = "ABC"
    assert check(m)
    m = _minimal(); del m["media_binding"]
    assert check(m)
    m = _minimal(); m["editorial_annotations"] = []
    assert check(m)
    # §6.3 exactly one original
    m = _minimal(); m["media_binding"]["files"].append({"name": "d.mov", "sha256": "1" * 64})
    assert check(m)
    m = _minimal(); m["media_binding"]["files"][0]["role"] = "proxy"
    assert check(m)
    m = _minimal(); m["media_binding"]["files"][0]["role"] = "sidecar"
    assert check(m)
    m = _minimal(); m["media_binding"]["files"].append({"name": "d.mov", "sha256": "1" * 64, "role": "proxy"})
    assert check(m) == []
    # §5.1 generated_at is RFC 3339
    m = _minimal(); m["generated_at"] = "yesterday"
    assert check(m)
    m = _minimal(); m["generated_at"] = "2026-08-29T20:00:00Z"
    assert check(m) == []


def test_run_host_and_models_shapes():
    """§7.2: a class of machine, and model files with real digests."""
    def _with(**run_keys):
        m = _minimal()
        m["machine_intelligence"] = [{"run_id": "0" * 32, "producer": "x:y",
                                      "model_version": "1", "facets": {}, **run_keys}]
        return m

    assert check(_with(host={"os": "macos", "arch": "arm64", "accelerator": "metal"})) == []
    assert check(_with(host={"os": "linux"})) == []
    assert check(_with(host={"os": "macos", "hostname": "studio-3"}))
    assert check(_with(host={"os": "macos", "arch": "MacBook.local"}))
    assert check(_with(host="macos"))

    assert check(_with(models=[{"name": "w.safetensors", "sha256": "ab" * 32}])) == []
    assert check(_with(models=[{"name": "w.safetensors", "sha256": "AB" * 32}]))
    assert check(_with(models=[{"sha256": "ab" * 32}]))
    assert check(_with(models=[{"name": "", "sha256": "ab" * 32}]))
    assert check(_with(models="w.safetensors"))


def test_label_identity_keys_are_optional_and_typed():
    """§8.2: `by`, `at`, `notes` and `id` are never required, always typed."""
    def _labelled(**keys):
        m = _minimal()
        m["editorial_annotations"] = {"labels": [
            {"name": "select", "value": True, "created_by": "opi:latent", **keys}]}
        return m

    assert check(_labelled()) == []
    assert check(_labelled(id="lbl-7", by="u-417", at="2026-08-29T10:00:00Z",
                           notes="second unit")) == []
    assert check(_labelled(at="yesterday"))
    assert check(_labelled(by=""))
    assert check(_labelled(id=""))
    assert check(_labelled(notes=17))
    # §8.2: a bare tag is `value: null`, and stays valid — it is not a retraction.
    m = _minimal()
    m["editorial_annotations"] = {"labels": [
        {"name": "select", "value": None, "created_by": "opi:latent"}]}
    assert check(m) == []
    # §8.1: layer-level notes
    m["editorial_annotations"]["notes"] = "the whole reel is soft"
    assert check(m) == []
    m["editorial_annotations"]["notes"] = ["soft"]
    assert check(m)


def test_timecode_is_rational_or_null():
    m = _minimal()
    m["media_binding"]["timecode"] = None
    assert check(m) == []
    m["media_binding"]["timecode"] = {"rate": {"num": 24000, "den": 1001}, "drop_frame": False}
    assert check(m) == []
    m["media_binding"]["timecode"] = {"rate": 23.976, "drop_frame": False}
    assert check(m)
    m["media_binding"]["timecode"] = {"rate": {"num": 0, "den": 1}, "drop_frame": False}
    assert check(m)


def test_signature_and_attachment_shapes():
    m = _minimal()
    run = {
        "run_id": "c" * 32, "producer": "test:p", "model_version": "1", "facets": {},
        "attachments": {"embeddings/x.safetensors": {"sha256": "a" * 64, "size": 10, "media_type": "application/x-safetensors"}},
        "signature": {"algorithm": "Ed25519", "public_key": "b" * 64, "signature": "A" * 86 + "=="},
    }
    m["machine_intelligence"] = [copy.deepcopy(run)]
    assert check(m) == []
    bad = copy.deepcopy(m); bad["machine_intelligence"][0]["signature"]["algorithm"] = "RSA"
    assert check(bad)
    bad = copy.deepcopy(m); bad["machine_intelligence"][0]["signature"]["public_key"] = "zz"
    assert check(bad)
    bad = copy.deepcopy(m); bad["machine_intelligence"][0]["attachments"]["extensions/com.x/x.bin"] = {"size": 1}
    assert check(bad)  # sha256 and media_type are required
    bad = copy.deepcopy(m); bad["machine_intelligence"][0]["attachments"]["/abs.bin"] = {"sha256": "a" * 64, "size": 1, "media_type": "a/b"}
    assert check(bad)  # absolute member names are not allowed
    bad = copy.deepcopy(m); bad["machine_intelligence"][0]["attachments"]["x.bin"] = {"sha256": "a" * 64, "size": 1, "media_type": "a/b"}
    assert check(bad)  # top-level members are not allowed (§7b)
    bad = copy.deepcopy(m); bad["machine_intelligence"][0]["producer"] = "p"
    assert check(bad)  # producer needs vendor:pass
    bad = copy.deepcopy(m); del bad["machine_intelligence"][0]["facets"]
    assert check(bad)


def test_schema_document_is_well_formed():
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert SCHEMA["properties"]["opi"]["const"] == 0
    # every $ref resolves
    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                _resolve(node["$ref"], SCHEMA)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(SCHEMA)


# ── proposed facet vocabulary (non-normative) ──────────────────────────


def test_facets_schema_accepts_the_vocabulary_and_rejects_misuse():
    good = {
        "shots": [{"idx": 0, "span": {"frame_in": 0, "frame_out": 48, "t_start_s": 0.0, "t_end_s": 2.0}}],
        "camera_motion": [{"verb": "pan", "direction": {"pan": "left", "tilt": None, "zoom": None}, "magnitude": 0.4,
                           "editorial": ["drift"], "samples": 12, "confidence": 0.7,
                           "span": {"t_start_s": 0.0, "t_end_s": 2.0}}],
        "shot_size": [{"value": "CU", "iptc_scene_code": "011800", "confidence": 9100}],
        "energy_curve": [{"t": [0.5, 1.5, 2.5], "motion": [0.1, 0.5, 0.9], "audio": [-40.0, -30.0, -20.0],
                          "peak_t": 2.5, "samples": 3, "confidence": None}],
        "clearance": [{"flag": "minor", "review_required": True, "bbox": [0.1, 0.1, 0.2, 0.3], "confidence": 0.6}],
        "embeddings": [{"member": "embeddings/siglip.safetensors", "model": "siglip-so400m", "dim": 1152, "dtype": "F16"}],
        "somebody_elses_facet": [{"anything": True}],
    }
    assert errors(good, FACETS, FACETS) == []
    bad_verb = {"camera_motion": [{"verb": "push", "samples": 1, "confidence": 0.5}]}  # editorial word in the MPEG-7 slot
    assert errors(bad_verb, FACETS, FACETS)
    bad_flag = {"clearance": [{"flag": "minor", "review_required": False}]}  # a determination, not a flag
    assert errors(bad_flag, FACETS, FACETS)
    bad_size = {"shot_size": [{"value": "MLS"}]}                # not in the CV
    assert errors(bad_size, FACETS, FACETS)
    bad_conf = {"shot_size": [{"value": "CU", "confidence": 1.5}]}
    assert errors(bad_conf, FACETS, FACETS)


def test_facets_schema_document_is_well_formed():
    assert FACETS["$schema"].endswith("2020-12/schema")
    assert FACETS["additionalProperties"] is True
    for name in ("shot_size", "camera_motion", "composition", "exposure_color", "focus", "continuity",
                 "take", "audio_usability", "energy_curve", "clearance"):
        assert name in FACETS["properties"] and name in FACETS["$defs"], name
    verbs = FACETS["$defs"]["camera_motion"]["properties"]["verb"]["enum"]
    assert verbs[:8] == ["fixed", "pan", "tilt", "roll", "zoom", "dolly", "track", "boom"]
