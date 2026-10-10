#!/usr/bin/env python3
"""Regenerate the usage blocks in docs/reference/cli.md from the live CLI.

docs/reference/cli.md is a generated artifact, like SPEC.md and
tools/opi_verify.py: the prose around each block is written by hand, every
```text block is the parser's own --help output. Run this after changing
openpicture/cli.py; tests/test_cli_docs.py fails when the page drifts.

    python tools/build_cli_docs.py           # rewrite in place
    python tools/build_cli_docs.py --check   # exit 1 if it would change

Usage output is produced at COLUMNS=100 for stable wrapping; `--check`
compares whitespace-normalized text, because argparse wraps differently
across Python versions (the CI matrix runs 3.11–3.14) and wrap width is
not content.
"""

import io
import os
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reference" / "cli.md"

os.environ["COLUMNS"] = "100"
sys.path.insert(0, str(ROOT))

from openpicture import cli  # noqa: E402

SECTIONS = ["validate", "inspect", "pack", "unpack", "keygen", "sign",
            "doctor", "keys", "annotate", "diff", "companion"]

# how many help outputs a section holds, in order; `keys` documents its
# nested subcommands in the same section
NESTED = {"keys": [["keys"], ["keys", "add"], ["keys", "list"]]}


def helpargvs(sub):
    return NESTED.get(sub, [[sub]])

HEAD = re.compile(r"^## `openpicture ?([\w-]*)`", re.M)
FENCE = re.compile(r"```text\n(.*?)```", re.S)


def help_text(argv):
    """The parser's own --help output, captured the way a user sees it."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            cli.main(argv + ["--help"])
        except SystemExit as e:
            if e.code not in (0, None):
                raise
    return buf.getvalue()


def regenerate(text):
    """Return `text` with every usage block replaced by live --help output."""
    headings = list(HEAD.finditer(text))
    subs_found = [m.group(1) for m in headings]
    if subs_found != SECTIONS:
        raise SystemExit(
            f"section/subcommand mismatch:\n  doc:     {subs_found}\n"
            f"  parser:  {SECTIONS}\n"
            "add the missing `## `openpicture <sub>`` section (and the "
            "subcommand to SECTIONS here), then re-run.")

    # first fenced block in the file is the top-level help (no heading)
    edits = []  # (span, replacement)
    m0 = FENCE.search(text, 0, headings[0].start() if headings else len(text))
    if m0 is None:
        raise SystemExit("no top-level ```text block before the first section")
    edits.append((m0.span(1), help_text([])))

    for i, m in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        blocks = list(FENCE.finditer(text, m.end(), end))
        want = helpargvs(m.group(1))
        if len(blocks) != len(want):
            raise SystemExit(
                f"section `{m.group(1)}` holds {len(blocks)} ```text block(s), "
                f"expected {len(want)}: {[a for a in want]}")
        for fm, argv in zip(blocks, want):
            edits.append((fm.span(1), help_text(argv)))

    out, pos = [], 0
    for (a, b), repl in edits:
        out.append(text[pos:a])
        out.append(repl.rstrip("\n") + "\n")
        pos = b
    out.append(text[pos:])
    return "".join(out)


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def main():
    check = "--check" in sys.argv[1:]
    old = DOC.read_text()
    new = regenerate(old)
    if check:
        if _norm(new) != _norm(old):
            print("docs/reference/cli.md is stale — run: python tools/build_cli_docs.py")
            return 1
        print("docs/reference/cli.md up to date")
        return 0
    DOC.write_text(new)
    print(f"regenerated {DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
