"""The time model — rational rates, integer frames, SMPTE ST 12 timecode.

Spec chapter 6A. One rule underlies everything here: **a position is an
integer frame count at an exact rational rate.** Seconds and `HH:MM:SS:FF`
labels are renderings of that count, never the value. 23.976 fps *is*
24000/1001; a drop-frame label is a name for a frame index, not a different
clock. Nothing in this module converts through a float, so round trips are
exact by construction.

Standard library only. The drop-frame arithmetic is a port of the reference
producer's converter, which was verified against an independent brute-force
SMPTE simulator; `tests/test_time.py` re-proves the port frame by frame.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable, Mapping

__all__ = [
    "LEGAL_RATES",
    "DROP_FRAME_RATES",
    "Rate",
    "Timecode",
    "frames_to_seconds",
    "seconds_to_frames",
    "span_from_seconds",
    "check_span",
    "checks",
    "fcpxml_time",
    "fcpxml_frame_duration",
    "otio_rational_time",
    "edl_fcm",
    "edl_timecode",
    "xmeml_timebase",
]

# Rates with SMPTE ST 12 timecode semantics. NTSC rates are exact 1000/1001
# pulldowns of their nominal — never the decimal printed on a camera menu.
LEGAL_RATES: tuple[Fraction, ...] = (
    Fraction(24000, 1001),   # 23.976
    Fraction(24),
    Fraction(25),
    Fraction(30000, 1001),   # 29.97
    Fraction(30),
    Fraction(48000, 1001),   # 47.952
    Fraction(48),
    Fraction(50),
    Fraction(60000, 1001),   # 59.94
    Fraction(60),
    Fraction(120000, 1001),  # 119.88
    Fraction(120),
)

# Drop-frame: labels dropped at the start of every minute except each tenth.
# ST 12-1 §5.2.2 defines 2 at nominal 30; 4 at nominal 60 (ST 12-1 60 Hz
# counting); ST 12-3 defines 120 DF as 30 DF × 4, i.e. 8. Nothing else.
DROP_FRAME_RATES: dict[Fraction, int] = {
    Fraction(30000, 1001): 2,
    Fraction(60000, 1001): 4,
    Fraction(120000, 1001): 8,
}

_SNAP = Fraction(1, 100)
_LABEL_SPEC = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ndf|nd|df)?\s*$", re.IGNORECASE)
_TC = re.compile(r"^\s*(\d+)[:;](\d{1,2})[:;](\d{1,2})[:;.](\d{1,3})\s*$")


# ── rate ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Rate:
    """An exact frame rate `num/den` and whether its labels drop."""

    num: int
    den: int = 1
    drop_frame: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.num, int) or not isinstance(self.den, int) or isinstance(self.num, bool):
            raise ValueError("rate num/den must be integers")
        if self.num <= 0 or self.den <= 0:
            raise ValueError(f"rate must be positive, got {self.num}/{self.den}")
        if math.gcd(self.num, self.den) != 1:
            raise ValueError(f"rate {self.num}/{self.den} is not reduced")
        if self.drop_frame and self.fps not in DROP_FRAME_RATES:
            legal = ", ".join(f"{r.numerator}/{r.denominator}" for r in DROP_FRAME_RATES)
            raise ValueError(f"drop_frame is defined only at {legal}; got {self.num}/{self.den}")

    # construction

    @classmethod
    def from_fraction(cls, fps: Fraction, drop_frame: bool = False) -> "Rate":
        return cls(fps.numerator, fps.denominator, drop_frame)

    @classmethod
    def from_dict(cls, rate: Mapping[str, Any], drop_frame: bool = False) -> "Rate":
        """`{"num": 24000, "den": 1001}` → Rate. Unreduced input is an error."""
        try:
            return cls(rate["num"], rate["den"], drop_frame)
        except (KeyError, TypeError) as exc:
            raise ValueError(f"rate must be an object with integer num and den: {rate!r}") from exc

    @classmethod
    def from_fps(cls, fps: float | int | str | Fraction, drop_frame: bool = False) -> "Rate":
        """Snap a measured or printed fps onto the legal rate it means.

        23.976023976 and "23.98" both mean 24000/1001. A value more than
        0.01 from every legal rate has no timecode semantics and raises.
        """
        value = fps if isinstance(fps, Fraction) else Fraction(str(fps))
        for canonical in LEGAL_RATES:
            if abs(canonical - value) < _SNAP:
                return cls.from_fraction(canonical, drop_frame)
        raise ValueError(f"{float(value):g} fps is not a rate with timecode semantics")

    @classmethod
    def parse(cls, label: str) -> "Rate":
        """`"23.976"`, `"29.97DF"`, `"30"` → Rate."""
        match = _LABEL_SPEC.match(label)
        if not match:
            raise ValueError(f"unreadable frame rate label {label!r}")
        fps, suffix = match.groups()
        return cls.from_fps(fps, drop_frame=(suffix or "").lower() == "df")

    # properties

    @property
    def fps(self) -> Fraction:
        return Fraction(self.num, self.den)

    @property
    def has_timecode(self) -> bool:
        """Whether `HH:MM:SS:FF` labels are defined at this rate."""
        return self.fps in LEGAL_RATES

    @property
    def nominal(self) -> int:
        """Frames per labelled second — where the FF field wraps."""
        return math.ceil(self.fps)

    @property
    def dropped_per_minute(self) -> int:
        return DROP_FRAME_RATES[self.fps] if self.drop_frame else 0

    @property
    def label(self) -> str:
        shown = f"{float(self.fps):.3f}".rstrip("0").rstrip(".")
        return f"{shown}{'DF' if self.drop_frame else ''}"

    def to_dict(self) -> dict:
        return {"num": self.num, "den": self.den}

    def __str__(self) -> str:
        return self.label


# ── timecode ───────────────────────────────────────────────────────────


def _label_to_frames(hours: int, minutes: int, seconds: int, frames: int, rate: Rate) -> int:
    if not rate.has_timecode:
        raise ValueError(f"no timecode semantics at {rate.num}/{rate.den}")
    nominal = rate.nominal
    if hours < 0:
        raise ValueError("timecode cannot be negative")
    if not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError(f"{hours:02d}:{minutes:02d}:{seconds:02d} is not a clock time")
    if not 0 <= frames < nominal:
        raise ValueError(f"frame field {frames} out of range for {rate.label} (0–{nominal - 1})")
    total = ((hours * 60 + minutes) * 60 + seconds) * nominal + frames
    if not rate.drop_frame:
        return total
    dropped = rate.dropped_per_minute
    elapsed_minutes = hours * 60 + minutes
    if seconds == 0 and frames < dropped and elapsed_minutes % 10:
        raise ValueError(
            f"{hours:02d}:{minutes:02d}:{seconds:02d};{frames:02d} is a dropped label — "
            f"it does not exist at {rate.label}")
    return total - dropped * (elapsed_minutes - elapsed_minutes // 10)


def _frames_to_parts(count: int, rate: Rate) -> tuple[int, int, int, int]:
    if not rate.has_timecode:
        raise ValueError(f"no timecode semantics at {rate.num}/{rate.den}")
    nominal = rate.nominal
    if rate.drop_frame:
        dropped = rate.dropped_per_minute
        per_minute = nominal * 60 - dropped
        per_ten = nominal * 600 - 9 * dropped
        tens, within = divmod(count, per_ten)
        count += 9 * dropped * tens
        if within >= dropped:
            count += dropped * ((within - dropped) // per_minute)
    hours, rest = divmod(count, 3600 * nominal)
    minutes, rest = divmod(rest, 60 * nominal)
    seconds, frames = divmod(rest, nominal)
    return hours, minutes, seconds, frames


@dataclass(frozen=True, slots=True)
class Timecode:
    """A frame index on a rate. The label is a rendering; the index is the value."""

    frames: int
    rate: Rate

    def __post_init__(self) -> None:
        if not isinstance(self.frames, int) or isinstance(self.frames, bool):
            raise ValueError("frames must be an integer")
        if self.frames < 0:
            raise ValueError(f"timecode cannot be negative, got {self.frames} frames")

    @classmethod
    def parse(cls, label: str, rate: Rate) -> "Timecode":
        """`"01:00:00:00"` or `"01:00:00;02"` → Timecode on `rate`.

        Either separator is accepted; the rate, not the punctuation, says
        whether labels drop. A label that ST 12 drops raises.
        """
        match = _TC.match(label)
        if not match:
            raise ValueError(f"unreadable timecode {label!r}")
        h, m, s, f = (int(part) for part in match.groups())
        return cls(_label_to_frames(h, m, s, f, rate), rate)

    @classmethod
    def from_seconds(cls, seconds: float | int | str | Fraction, rate: Rate, mode: str = "floor") -> "Timecode":
        return cls(seconds_to_frames(seconds, rate, mode), rate)

    @property
    def parts(self) -> tuple[int, int, int, int]:
        return _frames_to_parts(self.frames, self.rate)

    @property
    def seconds(self) -> Fraction:
        """Elapsed real time — exact, and *not* what an NTSC label reads."""
        return frames_to_seconds(self.frames, self.rate)

    def __str__(self) -> str:
        h, m, s, f = self.parts
        tick = ";" if self.rate.drop_frame else ":"
        return f"{h:02d}:{m:02d}:{s:02d}{tick}{f:02d}"

    def __add__(self, frames: int) -> "Timecode":
        return Timecode(self.frames + frames, self.rate)

    def __sub__(self, other: "Timecode | int") -> "Timecode | int":
        if isinstance(other, Timecode):
            if other.rate != self.rate:
                raise ValueError(f"rate mismatch: {self.rate} vs {other.rate}")
            return self.frames - other.frames
        return Timecode(self.frames - other, self.rate)


# ── conversions ────────────────────────────────────────────────────────


def frames_to_seconds(frames: int, rate: Rate) -> Fraction:
    """Exact: `frames * den / num`."""
    return Fraction(frames * rate.den, rate.num)


def _exact(seconds: float | int | str | Fraction) -> Fraction:
    # str() of a float is its shortest round-trip repr, so 0.1 stays 1/10
    # rather than becoming 3602879701896397/36028797018963968.
    return seconds if isinstance(seconds, Fraction) else Fraction(str(seconds))


def seconds_to_frames(seconds: float | int | str | Fraction, rate: Rate, mode: str = "floor") -> int:
    """Seconds → the frame covering that instant.

    `floor` for an in-point, `ceil` for an out-point, `round` (half up) for
    display. Negative seconds are an error: media starts at frame 0.
    """
    exact = _exact(seconds)
    if exact < 0:
        raise ValueError(f"seconds cannot be negative, got {exact}")
    position = exact * rate.fps
    if mode == "floor":
        return math.floor(position)
    if mode == "ceil":
        return math.ceil(position)
    if mode == "round":
        return math.floor(position + Fraction(1, 2))
    raise ValueError(f"unknown rounding mode {mode!r}")


def span_from_seconds(t_start_s, t_end_s, rate: Rate) -> tuple[int, int]:
    """Sub-frame seconds → `[frame_in, frame_out)` that *contains* the range.

    In floors, out ceils, out is exclusive, and a zero-length instant
    occupies one frame — so the exported clip never clips a frame off
    either end of the moment that produced it.
    """
    start, end = _exact(t_start_s), _exact(t_end_s)
    if end < start:
        raise ValueError(f"span ends before it starts: {start} → {end}")
    frame_in = seconds_to_frames(start, rate, "floor")
    frame_out = seconds_to_frames(end, rate, "ceil")
    if frame_out == frame_in:
        frame_out += 1
    return frame_in, frame_out


# ── checks ─────────────────────────────────────────────────────────────


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check_span(span: Mapping[str, Any], rate: Rate | None, start: Timecode | None = None) -> list[str]:
    """Everything a validator says about one `span`. Empty list = consistent.

    Rules (spec 6A.3–6A.4): frames are authoritative when present; seconds,
    when also present, must name the same frames (compared exactly as
    fractions, within half a frame); timecode strings, when present, must
    render exactly from `start` + frames; `frames` must equal the length.
    Without a rate only seconds are allowed.
    """
    errors: list[str] = []
    if not isinstance(span, Mapping):
        return ["span is not an object"]
    fin, fout = span.get("frame_in"), span.get("frame_out")
    t0, t1 = span.get("t_start_s"), span.get("t_end_s")
    tc_in, tc_out = span.get("tc_in"), span.get("tc_out")
    has_frames = fin is not None or fout is not None
    has_seconds = t0 is not None or t1 is not None

    if rate is None:
        if has_frames or tc_in is not None or tc_out is not None or span.get("frames") is not None:
            errors.append("media has no rate: span may carry seconds only")
        if not has_seconds:
            errors.append("span has no position at all")
        if has_seconds:
            errors.extend(_check_seconds_only(t0, t1))
        return errors

    if not has_frames and not has_seconds:
        return ["span has no position at all"]

    if has_frames:
        if not _is_int(fin) or not _is_int(fout):
            return ["frame_in and frame_out must both be integers"]
        if fin < 0:
            errors.append(f"frame_in {fin} is negative")
        if fout <= fin:
            errors.append(f"frame_out {fout} must exceed frame_in {fin} (half-open, at least one frame)")
        if span.get("frames") is not None and span["frames"] != fout - fin:
            errors.append(f"frames {span['frames']} != frame_out - frame_in ({fout - fin})")
        if has_seconds:
            errors.extend(_seconds_agree(t0, t1, fin, fout, rate))
        if tc_in is not None or tc_out is not None:
            if start is None:
                errors.append("tc_in/tc_out present but media_binding.timecode has no start")
            else:
                errors.extend(_tc_agree(tc_in, tc_out, fin, fout, start))
    else:
        errors.extend(_check_seconds_only(t0, t1))
        if tc_in is not None or tc_out is not None:
            errors.append("tc_in/tc_out without frame_in/frame_out: frames are the position, timecode is derived")
    return errors


def _check_seconds_only(t0, t1) -> list[str]:
    errors = []
    for name, v in (("t_start_s", t0), ("t_end_s", t1)):
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
            errors.append(f"{name} must be a number")
    if not errors and t0 is not None and t1 is not None and _exact(t1) < _exact(t0):
        errors.append(f"t_end_s {t1} before t_start_s {t0}")
    if not errors and t0 is not None and _exact(t0) < 0:
        errors.append("t_start_s is negative")
    return errors


def _seconds_agree(t0, t1, fin: int, fout: int, rate: Rate) -> list[str]:
    errors = _check_seconds_only(t0, t1)
    if errors:
        return errors
    half = Fraction(rate.den, 2 * rate.num)
    if t0 is not None and abs(_exact(t0) - frames_to_seconds(fin, rate)) > half:
        errors.append(f"t_start_s {t0} does not name frame_in {fin} at {rate.label} (>½ frame apart)")
    if t1 is not None:
        # out is exclusive and ceiled: the seconds value lies in (frame_out-1, frame_out] frames
        end_frames = _exact(t1) * rate.fps
        if not (Fraction(fout) - 1 - Fraction(1, 2) < end_frames <= Fraction(fout) + Fraction(1, 2)):
            errors.append(f"t_end_s {t1} does not name frame_out {fout} at {rate.label}")
    return errors


def _tc_agree(tc_in, tc_out, fin: int, fout: int, start: Timecode) -> list[str]:
    errors = []
    for name, label, frames in (("tc_in", tc_in, fin), ("tc_out", tc_out, fout)):
        if label is None:
            continue
        try:
            got = Timecode.parse(str(label), start.rate).frames
        except ValueError as exc:
            errors.append(f"{name} {label!r}: {exc}")
            continue
        expected = start.frames + frames
        if got != expected:
            errors.append(f"{name} {label} is frame {got - start.frames} from start, span says {frames}")
    return errors


def _walk_spans(node: Any, where: str) -> Iterable[tuple[str, Mapping]]:
    """Every object carrying a `span` under `node`, with a path for messages."""
    if isinstance(node, Mapping):
        if isinstance(node.get("span"), Mapping):
            yield where, node["span"]
        for key, value in node.items():
            if key != "span" and isinstance(value, (Mapping, list)):
                yield from _walk_spans(value, f"{where}.{key}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            if isinstance(item, (Mapping, list)):
                yield from _walk_spans(item, f"{where}[{i}]")


def _duration_rows(mb, rate: "Rate | None") -> list[tuple[str, bool, str]]:
    """SPEC §6.1/§6.5: `duration_frames` needs a rate, and must agree with `duration_s`.

    Agreement is "within one frame", evaluated exactly:
    `abs(frames × den/num − seconds) < den/num`.
    """
    if not isinstance(mb, Mapping) or "duration_frames" not in mb:
        return []
    frames = mb.get("duration_frames")
    if not isinstance(frames, int) or isinstance(frames, bool) or frames < 0:
        return [("duration", False, f"duration_frames must be a non-negative integer, got {frames!r}")]
    if rate is None:
        return [("duration", False, "duration_frames at timecode: null — the medium has no rate")]
    seconds = mb.get("duration_s")
    if seconds is None:
        return [("duration", True, f"{frames} frames")]
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        return [("duration", False, f"duration_s must be a number, got {seconds!r}")]
    one_frame = Fraction(rate.den, rate.num)
    exact = frames * one_frame
    off = abs(exact - Fraction(seconds).limit_denominator(10 ** 9))
    ok = off < one_frame
    return [("duration", ok, f"{frames} frames = {float(exact):.6f}s" if ok else
             f"{frames} frames is {float(exact):.6f}s, duration_s says {seconds} "
             f"({float(off):.6f}s apart, one frame is {float(one_frame):.6f}s)")]


def checks(manifest: Mapping) -> list[tuple[str, bool, str]]:
    """The time-model checks for a whole manifest: `(name, ok, detail)` rows.

    Reads `media_binding.timecode` for the rate and start, then checks every
    `span` under `machine_intelligence[*].facets` and
    `editorial_annotations`. Designed to be appended to the structural
    validator's report.
    """
    rows: list[tuple[str, bool, str]] = []
    rate: Rate | None = None
    start: Timecode | None = None
    mb = manifest.get("media_binding") if isinstance(manifest, Mapping) else None
    tc = mb.get("timecode") if isinstance(mb, Mapping) else None

    if tc is None:
        rows.append(("timecode", True, "media has no rate; spans are seconds-only"))
    elif not isinstance(tc, Mapping):
        rows.append(("timecode", False, "must be an object or null"))
        return rows
    else:
        try:
            rate = Rate.from_dict(tc.get("rate") or {}, drop_frame=bool(tc.get("drop_frame", False)))
            rows.append(("timecode.rate", True, f"{rate.num}/{rate.den}" + (" DF" if rate.drop_frame else "")))
        except ValueError as exc:
            rows.append(("timecode.rate", False, str(exc)))
            return rows
        label = tc.get("label")
        if label is not None:
            try:
                ok = Rate.parse(str(label)) == rate
            except ValueError:
                ok = False
            rows.append(("timecode.label", ok, "" if ok else f"label {label!r} does not name {rate.label}"))
        if tc.get("start") is not None:
            if not rate.has_timecode:
                rows.append(("timecode.start", False, f"no timecode semantics at {rate.num}/{rate.den}"))
            else:
                try:
                    start = Timecode.parse(str(tc["start"]), rate)
                    rows.append(("timecode.start", True, str(start)))
                except ValueError as exc:
                    rows.append(("timecode.start", False, str(exc)))

    rows += _duration_rows(mb, rate)

    bad = 0
    total = 0
    for i, run in enumerate(manifest.get("machine_intelligence") or []):
        if isinstance(run, Mapping) and isinstance(run.get("facets"), Mapping):
            for where, span in _walk_spans(run["facets"], f"run[{i}].facets"):
                total += 1
                errs = check_span(span, rate, start)
                if errs:
                    bad += 1
                    rows.append((f"span {where}", False, "; ".join(errs)))
    ann = manifest.get("editorial_annotations")
    if isinstance(ann, Mapping):
        for where, span in _walk_spans(ann, "editorial_annotations"):
            total += 1
            errs = check_span(span, rate, start)
            if errs:
                bad += 1
                rows.append((f"span {where}", False, "; ".join(errs)))
    rows.append(("spans", bad == 0, f"{total - bad}/{total} consistent"))
    return rows


# ── interchange formatting ─────────────────────────────────────────────


def fcpxml_time(frames: int, rate: Rate) -> str:
    """FCPXML rational seconds for a frame position: `<frames*den/num>s`, reduced.

    Lossless and frame-aligned by construction; `"3600s"` when integral.
    """
    value = frames_to_seconds(frames, rate)
    return f"{value.numerator}s" if value.denominator == 1 else f"{value.numerator}/{value.denominator}s"


def fcpxml_frame_duration(rate: Rate) -> str:
    """FCPXML `frameDuration`: one frame as rational seconds, `den/num s`."""
    d = Fraction(rate.den, rate.num)
    return f"{d.numerator}s" if d.denominator == 1 else f"{d.numerator}/{d.denominator}s"


def otio_rational_time(frames: int, rate: Rate) -> dict:
    """OTIO `RationalTime.1`. **Lossy**: OTIO stores the rate as a double.

    An importer MUST snap the double back to the nearest legal rational
    (|r - num/den| < 1e-6) and use `round()` on `value`, never truncation.
    """
    return {"OTIO_SCHEMA": "RationalTime.1", "rate": rate.num / rate.den, "value": frames}


def edl_fcm(rate: Rate) -> str:
    """The CMX 3600 `FCM:` line — the only rate signal an EDL carries."""
    return "DROP FRAME" if rate.drop_frame else "NON-DROP FRAME"


def edl_timecode(frames: int, start: Timecode) -> str:
    """Source timecode for a frame offset from the media head: `start + frames`."""
    return str(start + frames)


def xmeml_timebase(rate: Rate) -> tuple[int, bool]:
    """FCP7 XML `<timebase>` and `<ntsc>`: the nominal, and whether 1000/1001."""
    return rate.nominal, rate.den == 1001
