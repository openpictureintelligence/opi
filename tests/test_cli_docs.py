"""docs/reference/cli.md is generated — its usage blocks must match --help.

Same contract as test_spec_build (SPEC.md) and test_bundle (opi_verify.py):
the prose is hand-written, the ```text blocks are artifacts of
openpicture.cli. When this fails, run:

    python tools/build_cli_docs.py

and commit the page together with the CLI change.
"""

import io
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "build_cli_docs.py"
DOC = ROOT / "docs" / "reference" / "cli.md"

SECTIONS = ["validate", "inspect", "pack", "unpack", "keygen", "sign",
            "doctor", "keys", "annotate", "diff", "companion"]

# `keys` documents its nested subcommands in the same section
NESTED = {"keys": [["keys"], ["keys", "add"], ["keys", "list"]]}

HEAD = re.compile(r"^## `openpicture ?([\w-]*)`", re.M)
FENCE = re.compile(r"```text\n(.*?)```", re.S)


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _help(argv):
    from openpicture import cli
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            cli.main(argv + ["--help"])
        except SystemExit as e:
            assert e.code in (0, None)
    return buf.getvalue()


def test_usage_blocks_match_help():
    r = subprocess.run([sys.executable, str(TOOL), "--check"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_usage_blocks_cover_every_documented_command():
    """Sections in order, the right block count, each matching live help."""
    text = DOC.read_text()
    heads = list(HEAD.finditer(text))
    subs = [m.group(1) for m in heads]
    assert subs == SECTIONS, f"sections out of sync with the CLI: {subs}"

    # the page's first block (before any heading) is the top-level help
    m0 = FENCE.search(text, 0, heads[0].start())
    assert m0 is not None, "no top-level usage block"
    assert _norm(m0.group(1)) == _norm(_help([])), "top-level block drifted"

    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        blocks = FENCE.findall(text, m.end(), end)
        want = NESTED.get(m.group(1), [[m.group(1)]])
        assert len(blocks) == len(want), \
            f"section `{m.group(1)}` must hold {len(want)} block(s)"
        for block, argv in zip(blocks, want):
            assert _norm(block) == _norm(_help(argv)), (
                f"`{' '.join(argv)}` usage block drifted from --help — "
                "run: python tools/build_cli_docs.py")
