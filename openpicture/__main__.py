"""`python -m openpicture` — the CLI, without needing the console script (W18).

The `openpicture` entry point installed by the package runs `cli.main`;
this module makes the same command reachable from a checkout or an
environment where only the package is importable.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
