"""Open Picture Intelligence — `.opi`.

A per-clip sidecar that carries the intelligence layer beside the media it
describes. One extension, two profiles: **Core** is a plain UTF-8 JSON
document; **Full** is a ZIP container whose `manifest.json` is byte-identical
to a Core file, plus optional binary members. Readers dispatch on the first
byte: `{` is Core, `PK\\x03\\x04` is Full.

This package is deliberately standard-library only, so `opi/validate.py`
can be copied out of the tree and run anywhere Python runs.
"""

__version__ = "0.0.10"

SPEC_VERSION = 0            # integer major the writer emits; 0 = pre-freeze
EXTENSION = ".opi"
MANIFEST_MEMBER = "manifest.json"


def load(path, **kw):
    """Open a `.opi` as a `reader.Sidecar` — see `openpicture.reader.load`."""
    from .reader import load as _load
    return _load(path, **kw)
