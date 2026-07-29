from __future__ import annotations

import sys


def log(*values) -> None:
    print(*values, file=sys.stderr, flush=True)
