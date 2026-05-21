"""Top-level ``python -m factgraph`` dispatch entry point.

Slice 7C / Q6-A (d.4) — provides ``python -m factgraph migrate-workspace``
for users with legacy workspaces carrying a ``registry/`` directory or
``components.registry`` manifest entry.
"""

from __future__ import annotations

import sys

from factgraph.cli import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
