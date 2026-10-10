"""Assemble SPEC.md from the chapters in spec/ (order: spec/CHAPTERS.txt).

    python tools/build_spec.py            # write SPEC.md
    python tools/build_spec.py --check    # exit 1 if SPEC.md is stale
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "spec"
OUT = ROOT / "SPEC.md"
BANNER = "<!-- GENERATED from spec/*.md by tools/build_spec.py — edit the chapters, not this file. -->\n"


def assemble() -> str:
    order = [ln.strip() for ln in (SPEC_DIR / "CHAPTERS.txt").read_text().splitlines() if ln.strip()]
    body = "\n\n".join((SPEC_DIR / name).read_text().rstrip() for name in order)
    # banner goes after the H1 so the first line stays the title
    first_nl = body.index("\n")
    return body[: first_nl + 1] + "\n" + BANNER + body[first_nl + 1 :] + "\n"


def main(argv: list[str]) -> int:
    text = assemble()
    if "--check" in argv:
        current = OUT.read_text() if OUT.exists() else ""
        if current != text:
            print("SPEC.md is stale: run python tools/build_spec.py", file=sys.stderr)
            return 1
        print("SPEC.md up to date")
        return 0
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text):,} bytes, {len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
