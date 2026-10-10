"""The facet vocabulary (SPEC Appendix C) as code, and structural checks over it.

Appendix C is a *proposal* until decision B12 closes, so nothing here can
reject a file for disagreeing with it (§10.2). What this module does is
narrower and useful now:

- it is the one place the enums, required keys and maturity of each facet
  live, so producers and the docs read the same table;
- `checks()` verifies **known** facets structurally — required keys, enum
  membership, the measured-vs-inferred confidence rule, and the sensitive-
  facet rules of §10.3 — and passes everything it does not know.

Both encodings of a facet are understood: the canonical list under
`facets.<name>` and the row form `facets.signals[] {kind: "facet.<name>",
payload: {...}}` that a store-backed producer emits (C.0).

Only the §10.3 violations are failures a *conformance* validator should
adopt; the rest are advisory and are labelled so in the returned details.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping

__all__ = [
    "FACETS",
    "CAMERA_MOTION_VERBS",
    "CAMERA_MOTION_EDITORIAL",
    "SHOT_SIZES",
    "CLEARANCE_FLAGS",
    "LOG_PROFILES",
    "SENSITIVE_FACETS",
    "FROZEN",
    "Facet",
    "FacetCheck",
    "describe",
    "entries",
    "checks",
]

# ── vocabularies ───────────────────────────────────────────────────────

CAMERA_MOTION_VERBS = ("fixed", "pan", "tilt", "roll", "zoom", "dolly", "track", "boom")
CAMERA_MOTION_VERBS_EXTENDED = CAMERA_MOTION_VERBS + ("zoom_or_dolly", "unknown")
CAMERA_MOTION_EDITORIAL = ("static", "push", "pull", "whip", "drift", "handheld", "locked_off", "reveal")
SHOT_SIZES = ("ECU", "CU", "MCU", "MS", "MWS", "WS", "EWS")
IPTC_SCENE_CODES = ("010100", "010200", "010300", "011000", "011200", "011800")
CLEARANCE_FLAGS = ("logo", "face", "minor", "artwork", "licensed_music", "signage", "text")
AUDIO_DOMINANT = ("speech", "tonal_or_music", "ambience", "silence")
SCREEN_DIRECTIONS = ("screen_left", "screen_right", "center_facing")
SUBJECT_POSITIONS = ("left", "center", "right")
EMBEDDING_DTYPES = ("F32", "F16", "BF16", "I8", "U8")

#: Facets governed by §10.3: review flags, never determinations.
SENSITIVE_FACETS = frozenset({"clearance"})
#: Log encodings `exposure_color.log_profile` names (C.5, frozen by B12).
#: Enumerated so files compare across producers; anything not here is
#: written `x-<vendor>_<profile>` rather than as unconstrained free text,
#: which is how a vocabulary silently drifts.
LOG_PROFILES: tuple[str, ...] = (
    "ARRI_LogC3", "ARRI_LogC4",
    "Sony_SLog2", "Sony_SLog3",
    "Panasonic_VLog",
    "Canon_CLog2", "Canon_CLog3",
    "Nikon_NLog",
    "RED_Log3G10",
    "BMD_BRAWFilm",
    "Rec709",            # not a log encode — the honest "looks normal" answer
)

#: A vendor profile outside the enumeration: `x-` plus vendor and profile.
LOG_PROFILE_EXT_RE = re.compile(r"^x-[A-Za-z0-9]+_[A-Za-z0-9]+$")

#: Keys that must never appear on a sensitive-facet entry (§10.3 rule 2).
FORBIDDEN_ACCURACY_KEYS = frozenset({"accuracy", "precision", "recall", "f1", "error_rate"})


@dataclass(frozen=True)
class Facet:
    """One facet's vocabulary, on two independent axes.

    `shape` is about the *keys*: `frozen` means the name, required keys,
    units and enums do not change without a major-version bump, this
    appendix is normative for them, and an implementation may claim
    conformance on the facet. `maturity` is about the *producer*: how well
    solved the measurement is. B12 (2026-08-29) separated the two because
    `camera_motion` is both — an ISO vocabulary whose keys will not move,
    computed by a research-grade producer.
    """

    name: str
    tier: int
    maturity: str                      # stable | proposed | research
    confidence: str                    # required | forbidden | optional
    required: tuple[str, ...] = ()
    enums: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    mirrors: str = "none"
    row_kind: str | None = None        # bare signals kind, for inherently-row facets
    note: str = ""
    shape: str = "proposed"            # frozen | proposed  (B12)

    @property
    def frozen(self) -> bool:
        return self.shape == "frozen"


FACETS: dict[str, Facet] = {f.name: f for f in (
    Facet("shots", 1, "stable", "optional", ("idx", "span"), mirrors="MPEG-7 MDS VideoSegment",
          note="contiguous half-open spans; a continuous take is one shot", shape="frozen"),
    Facet("transcript", 1, "stable", "required", ("text", "span"), mirrors="IPTC VMH transcript",
          row_kind="transcript", shape="frozen"),
    Facet("description", 1, "proposed", "optional", ("text",), row_kind="description"),
    Facet("usability", 1, "stable", "forbidden", ("frame_count_sampled",), row_kind="usability",
          shape="frozen"),
    Facet("exposure_color", 2, "stable", "forbidden",
          ("mean_ire", "clipped_highlight_ratio", "crushed_black_ratio", "contrast", "wb_drift",
           "log_profile_likely", "frames_sampled"),
          {"log_profile": LOG_PROFILES}, shape="frozen"),
    Facet("energy_curve", 2, "stable", "forbidden", ("t", "motion", "audio", "peak_t", "samples"),
          mirrors="MPEG-7 MotionActivity (concept)", shape="frozen"),
    # B12: the shape is ISO's and will not move; the producer is research-grade.
    Facet("camera_motion", 2, "research", "required", ("verb", "samples"),
          {"verb": CAMERA_MOTION_VERBS_EXTENDED, "editorial[]": CAMERA_MOTION_EDITORIAL},
          mirrors="MPEG-7 CameraMotion", note="research-grade producer; zoom/dolly confidence capped",
          shape="frozen"),
    Facet("audio_usability", 2, "stable", "required",
          ("dominant", "rms_dbfs", "noise_floor_dbfs", "speech_ratio", "clipping_ratio", "frames"),
          {"dominant": AUDIO_DOMINANT}, shape="frozen"),
    Facet("embeddings", 0, "proposed", "forbidden", ("member",), {"dtype": EMBEDDING_DTYPES},
          note="attachment form is stable; facet form proposed"),
    Facet("shot_size", 2, "proposed", "required", ("value",),
          {"value": SHOT_SIZES, "iptc_scene_code": IPTC_SCENE_CODES},
          mirrors="IPTC VMH videoShotTypes (slot) + IPTC Scene NewsCodes"),
    Facet("composition", 2, "proposed", "forbidden", ("subject_detected",),
          {"subject_position": SUBJECT_POSITIONS}),
    Facet("focus", 2, "proposed", "required", ("sharpness", "in_focus"),
          {"focal_feel": ("wide", "normal", "long")}),
    Facet("continuity", 2, "research", "required", (),
          {"screen_direction": SCREEN_DIRECTIONS, "staging_position": SUBJECT_POSITIONS,
           "key_light_side": ("left", "right", "front", "top", "back"),
           "time_of_day": ("day", "night", "dawn_dusk", "interior"),
           "weather": ("clear", "overcast", "rain", "snow", "fog")}),
    Facet("take", 2, "proposed", "required", ()),
    Facet("clearance", 2, "proposed", "required", ("flag", "review_required"), {"flag": CLEARANCE_FLAGS},
          mirrors="IPTC VMH modelReleaseStatus / propertyReleaseStatus (egress)",
          note="§10.3 review flags, never determinations"),
    Facet("text_on_screen", 1, "proposed", "required", ("text",),
          {"kind": ("caption", "slate", "sign", "screen", "jersey", "other")},
          mirrors="IPTC VMH dataOnScreen"),
    Facet("persons", 1, "proposed", "required", ("cluster",), {"modality": ("seen", "heard", "both")},
          mirrors="IPTC VMH personsShown / personsHeard"),
    Facet("audio_events", 1, "proposed", "required", ("event",)),
)}


def describe(name: str) -> Facet | None:
    """The vocabulary entry for a facet name (`facet.` prefix tolerated)."""
    return FACETS.get(name[6:] if name.startswith("facet.") else name)


# ── walking a manifest ─────────────────────────────────────────────────


def entries(run: Mapping) -> Iterator[tuple[str, str, dict]]:
    """Every facet entry in a run as (facet_name, location, entry).

    Canonical entries are yielded as-is. Row-form entries are flattened:
    the row's `payload` keys become the entry with `span`, `confidence`,
    `coverage`, `shot_idx`, `scope` and `text` carried over, so callers see
    one shape.
    """
    facets = run.get("facets")
    if not isinstance(facets, dict):
        return
    for name, value in facets.items():
        if name == "signals":
            continue
        if isinstance(value, list):
            for i, e in enumerate(value):
                if isinstance(e, dict):
                    yield name, f"facets.{name}[{i}]", e
    rows = facets.get("signals")
    if isinstance(rows, list):
        for i, row in enumerate(rows):
            if not isinstance(row, dict) or not isinstance(row.get("kind"), str):
                continue
            kind = row["kind"]
            name = kind[6:] if kind.startswith("facet.") else kind
            flat = dict(row.get("payload") or {}) if isinstance(row.get("payload"), (dict, type(None))) else {}
            for k in ("span", "confidence", "coverage", "shot_idx", "scope", "text"):
                if k in row and k not in flat:
                    flat[k] = row[k]
            yield name, f"facets.signals[{i}]", flat


# ── checks ─────────────────────────────────────────────────────────────


@dataclass
class FacetCheck:
    name: str
    ok: bool
    detail: str = ""
    level: str = "advisory"   # advisory | conformance

    def as_tuple(self) -> tuple[str, bool, str]:
        return (self.name, self.ok, self.detail)


def checks(manifest: Mapping) -> list[FacetCheck]:
    """Structural checks over every known facet in every run.

    Unknown facet names pass silently (forward compatibility, §10.2).
    Failures are `advisory` except §10.3 violations, which are
    `conformance` — a validator MAY promote those to hard failures.
    """
    out: list[FacetCheck] = []
    runs = manifest.get("machine_intelligence")
    if not isinstance(runs, list):
        return out
    for ri, run in enumerate(runs):
        if not isinstance(run, dict):
            continue
        scale = run.get("confidence_scale", "unit")
        seen: dict[str, int] = {}
        for name, loc, entry in entries(run):
            spec = FACETS.get(name)
            if spec is None:
                continue
            seen[name] = seen.get(name, 0) + 1
            where = f"run[{ri}].{loc}"
            out.extend(_check_entry(spec, entry, where, scale))
        if "shots" in (run.get("facets") or {}):
            out.extend(_check_shots(run["facets"]["shots"], f"run[{ri}]"))
        if "camera_motion" in (run.get("facets") or {}):
            out.extend(_camera_motion_cap(run["facets"]["camera_motion"], f"run[{ri}]"))
        for name, n in seen.items():
            out.append(FacetCheck(f"run[{ri}] {name}", True, f"{n} entr{'y' if n == 1 else 'ies'} · {FACETS[name].maturity}"))
    return out


def _check_entry(spec: Facet, e: dict, where: str, scale: str) -> list[FacetCheck]:
    out: list[FacetCheck] = []
    missing = [k for k in spec.required if k not in e]
    if missing:
        out.append(FacetCheck(f"{where} required", False, f"{spec.name} missing {missing}"))
    for key, allowed in spec.enums.items():
        if key.endswith("[]"):
            vals = e.get(key[:-2])
            if isinstance(vals, list):
                bad = [v for v in vals if v not in allowed]
                if bad:
                    out.append(FacetCheck(f"{where} {key[:-2]}", False, f"not in vocabulary: {bad}"))
        elif key in e and e[key] is not None and e[key] not in allowed:
            # C.5: a profile outside the enumeration is written `x-<vendor>_<profile>`,
            # so an unknown encode stays comparable instead of becoming free text.
            if key == "log_profile" and isinstance(e[key], str) and LOG_PROFILE_EXT_RE.match(e[key]):
                continue
            hint = " (or x-<vendor>_<profile>)" if key == "log_profile" else ""
            out.append(FacetCheck(f"{where} {key}", False, f"{e[key]!r} not in {list(allowed)}{hint}"))
    if spec.name == "camera_motion" and isinstance(e.get("verbs"), dict):
        bad = [v for v in e["verbs"] if v not in CAMERA_MOTION_VERBS_EXTENDED]
        if bad:
            out.append(FacetCheck(f"{where} verbs", False, f"unknown verbs {bad}"))
    conf = e.get("confidence")
    if spec.confidence == "required" and conf is None and spec.name != "audio_usability":
        out.append(FacetCheck(f"{where} confidence", False, f"{spec.name} is an inference; confidence required (C.0.1)"))
    if spec.confidence == "forbidden" and conf is not None:
        out.append(FacetCheck(f"{where} confidence", True,
                              f"{spec.name} is measured; confidence read as coverage (C.0.1 transitional)"))
    if conf is not None and not _confidence_in_scale(conf, scale):
        out.append(FacetCheck(f"{where} confidence", False, f"{conf!r} outside scale {scale!r}"))
    if spec.name in SENSITIVE_FACETS:
        if e.get("review_required") is not True:
            out.append(FacetCheck(f"{where} review_required", False,
                                  "sensitive facet must carry review_required: true (§10.3 rule 1)", "conformance"))
        forbidden = sorted(FORBIDDEN_ACCURACY_KEYS & set(e))
        if forbidden:
            out.append(FacetCheck(f"{where} accuracy claim", False,
                                  f"sensitive facet carries {forbidden} (§10.3 rule 2)", "conformance"))
    return out


#: Facets whose shape B12 froze (2026-08-29). Their names, required keys,
#: units and enums do not change without a major-version bump, this
#: appendix is normative for them, and an implementation may claim
#: conformance on them. The embeddings **attachment** form is frozen too,
#: but by SPEC §7b.3, which was normative already — it is not a facet.
FROZEN: frozenset[str] = frozenset(n for n, f in FACETS.items() if f.frozen)


#: C.7: zoom, dolly, track, boom and zoom_or_dolly cannot be told apart
#: without parallax, so a producer caps their confidence below its cap for
#: the verbs it can resolve.
AMBIGUOUS_MOTION_VERBS: frozenset[str] = frozenset(
    {"zoom", "dolly", "track", "boom", "zoom_or_dolly"})


def _camera_motion_cap(entries: Any, where: str) -> list[FacetCheck]:
    """C.7's confidence cap, as far as a file can show it.

    The rule is relative to the producer's own caps, so it is a **writer**
    requirement (§11) that no reader can verify from one file: a validator
    never sees the caps, only samples drawn under them. What it can see is
    the ordering being contradicted — an ambiguous verb scored at or above
    everything the producer claimed for a verb it can actually resolve. That
    is reported as a passing note, never a failure, because a small run can
    produce it honestly.
    """
    scored: dict[bool, list[float]] = {True: [], False: []}
    for e in entries if isinstance(entries, list) else []:
        if not isinstance(e, dict) or not isinstance(e.get("confidence"), (int, float)):
            continue
        if isinstance(e["confidence"], bool):
            continue
        scored[e.get("verb") in AMBIGUOUS_MOTION_VERBS].append(float(e["confidence"]))
    if not scored[True] or not scored[False]:
        return []
    hi_amb, hi_res = max(scored[True]), max(scored[False])
    if hi_amb < hi_res:
        return []
    return [FacetCheck(f"{where} confidence cap", True,
                       f"an ambiguous verb scores {hi_amb} against {hi_res} for a resolvable one; "
                       f"C.7 caps zoom/dolly/track/boom below the rest (writer requirement, "
                       f"not observable from one file)")]


def _confidence_in_scale(conf: Any, scale: str) -> bool:
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        return False
    if scale == "bp":
        return isinstance(conf, int) and 0 <= conf <= 10000
    return 0 <= conf <= 1


def _check_shots(shots: Any, where: str) -> list[FacetCheck]:
    if not isinstance(shots, list) or not shots:
        return []
    idxs = [s.get("idx") for s in shots if isinstance(s, dict)]
    out = []
    if idxs != list(range(len(idxs))):
        out.append(FacetCheck(f"{where} shots idx", False, "idx must be 0-based and dense (C.1)"))
    spans = [s.get("span") for s in shots if isinstance(s, dict)]
    frames = [(sp.get("frame_in"), sp.get("frame_out")) for sp in spans
              if isinstance(sp, dict) and isinstance(sp.get("frame_in"), int) and isinstance(sp.get("frame_out"), int)]
    if len(frames) == len(spans) and frames:
        for (a_in, a_out), (b_in, _) in zip(frames, frames[1:]):
            if a_out != b_in:
                out.append(FacetCheck(f"{where} shots contiguity", False,
                                      f"gap or overlap between frame_out {a_out} and next frame_in {b_in} (C.1)"))
                break
        if any(o <= i for i, o in frames):
            out.append(FacetCheck(f"{where} shots span", False, "frame_out must exceed frame_in (§6a)"))
    return out
