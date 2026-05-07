"""Per-DTO wrapper views for application / audit DTOs (B1 + B2).

See blueprint §4.1 Round 1 + Round 3.

Phase 2 will add:

- `FrozenTupleView[T]` with `.filter` / `.find` / `.first` / `.require_key`
  / `.require_position` (find returns `View | None`; require_* raise
  `WalkerLookupError` on miss).
- `frozen_collection(tuple)` helper.

Phase 3 will add:

- `SupportArtifactView(support, frozen_claim_index, frozen_meta_index=None)`
- `AssertionView`

Phase 4 will add:

- `ProofFrameView(frame)` per Round 6 design.

Phase 5 will add `ProofFrameDiffView(diff)` with locked Round 3 method
names:

- `frames_with_status_change() -> FrozenTupleView[FrameDelta]`
- `iter_atom_deltas(*, kind: AtomDeltaKind | None = None) -> Iterator[AtomDelta]`
- `frames_with_atom_verdict_changes() -> FrozenTupleView[FrameDelta]`

This is a Phase 0 skeleton per the blueprint.
"""

from __future__ import annotations
