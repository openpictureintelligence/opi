"""Every §-reference in the specification resolves to a section that exists.

Chapters are written and reviewed one at a time, so a rule that moves —
"preserve the human layer" from §8.1 to §8.3, "ignore unknown keys" from
§5.2 to §5.3 — silently leaves stale pointers behind in the chapters that
cite it. This test is the drift gate for that.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec"

# References into somebody else's document, which this test cannot resolve.
EXTERNAL = {
    "4.3.13",   # ZIP APPNOTE.TXT — the ZIP-level digital signature record
    "5.1.7",    # RFC 8032 — Ed25519 verification
    "5.2.2",    # SMPTE ST 12-1 — drop-frame counting
}

_HEADING = re.compile(r"^#{1,4}\s+(?:Appendix\s+([A-C])\b|([0-9]+[a-zA-Z]?(?:\.[0-9]+)*)\.?\s)")
_REF = re.compile(r"§\s*([0-9A-C][0-9a-zA-Z.]*)")


def _chapters() -> list[Path]:
    return sorted(p for p in SPEC.glob("*.md") if p.name != "README.md")


def _list_items(section: str) -> int:
    """How many top-level numbered list items a section's body has.

    §6A.3.5 is item 5 of §6A.3's rules, not a heading of its own. Rather
    than allowlisting each such reference, resolve it: find the section,
    count its `1.`/`2.`/… items, and check the reference points at one that
    exists. Returns -1 when the section itself is not found.
    """
    for p in _chapters():
        lines = p.read_text().splitlines()
        for i, line in enumerate(lines):
            h = _HEADING.match(line)
            if not (h and (h.group(1) or h.group(2)) == section):
                continue
            count = 0
            for line in lines[i + 1:]:
                if _HEADING.match(line):
                    break
                m = re.match(r"^(\d+)\. ", line)
                if m:
                    count = max(count, int(m.group(1)))
            return count
    return -1


def _resolves(ref: str, defined: set[str]) -> bool:
    if ref in EXTERNAL or ref in defined:
        return True
    parent, _, item = ref.rpartition(".")
    return bool(parent) and parent in defined and item.isdigit() and \
        0 < int(item) <= _list_items(parent)


def _defined() -> set[str]:
    out = set()
    for p in _chapters():
        m = re.match(r"^(\d+[a-z]?)-", p.name)
        if m:
            out.add(m.group(1))
        for line in p.read_text().splitlines():
            h = _HEADING.match(line)
            if h:
                out.add(h.group(1) or h.group(2))
    return out


def test_every_section_reference_resolves():
    defined = _defined()
    dangling = []
    for p in _chapters():
        for i, line in enumerate(p.read_text().splitlines(), 1):
            for m in _REF.finditer(line):
                ref = m.group(1).rstrip(".,;:)")
                if _resolves(ref, defined):
                    continue
                dangling.append(f"{p.name}:{i} §{ref}")
    assert not dangling, "references to sections that do not exist:\n  " + "\n  ".join(dangling)


def test_section_references_match_the_heading_case():
    """`§6a.2` and `§6A.2` are the same section; the document picks one."""
    defined = _defined()
    lower = {d.lower(): d for d in defined}
    wrong = []
    for p in _chapters():
        for i, line in enumerate(p.read_text().splitlines(), 1):
            for m in _REF.finditer(line):
                ref = m.group(1).rstrip(".,;:)")
                if _resolves(ref, defined):
                    continue
                if ref.lower() in lower:
                    wrong.append(f"{p.name}:{i} §{ref} — the heading is §{lower[ref.lower()]}")
    assert not wrong, "\n  ".join(wrong)


def test_the_chapter_list_and_the_files_agree():
    listed = [ln.strip() for ln in (SPEC / "CHAPTERS.txt").read_text().splitlines() if ln.strip()]
    on_disk = {p.name for p in _chapters()}
    assert set(listed) == on_disk, (set(listed) ^ on_disk)


# ── patterns quoted in the prose are the ones the code compiles ────────


def test_quoted_patterns_match_the_reference_implementation():
    """A regex written out in the spec MUST be the one the validator uses.

    §7.5 quoted `^(x-<vendor>\\.)?…` for years with `<vendor>` undefined, so
    the text and `openpicture.runs.FACET_NAME_RE` could not be compared at
    all. Now they can be, so they are.
    """
    from openpicture import runs

    quoted = {}
    for p in _chapters():
        for m in re.finditer(r"Pattern: `(\^[^`]+\$)`", p.read_text()):
            quoted[m.group(1)] = p.name

    expected = {runs.PRODUCER_RE.pattern, runs.FACET_NAME_RE.pattern}
    assert expected <= set(quoted), (
        "a pattern the reference compiles is not quoted in the spec: "
        f"{sorted(expected - set(quoted))}"
    )
    unknown = set(quoted) - expected
    assert not unknown, f"the spec quotes patterns nothing implements: {sorted(unknown)}"


def test_the_schema_and_the_spec_agree_on_those_patterns():
    import json

    from openpicture import runs

    schema = json.loads((ROOT / "schema" / "opi-0.schema.json").read_text())
    run = schema["$defs"]["run"]["properties"]
    assert run["producer"]["pattern"] == runs.PRODUCER_RE.pattern
