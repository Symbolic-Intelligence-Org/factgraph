"""IR walker for derivation rule bodies (B1).

See blueprint §4.1 Round 1.

Phase 1 will add:

- `IRBodyWalker(source: list | tuple)` — construction-time snapshot via
  `tuple(source)`.
- Atom entry view exposing `.kind` / `.pred_id` / `.args` /
  `.branch_index` / `.atom_index`.

This is a Phase 0 skeleton per the blueprint.
"""

from __future__ import annotations
