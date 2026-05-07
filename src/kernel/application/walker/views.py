"""Per-DTO wrapper views for application / audit DTOs (B1 + B2).

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

Phase 2 implements `FrozenTupleView` / `frozen_collection`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Generic, TypeVar

from .errors import WalkerFrozenError, WalkerLookupError

ViewT = TypeVar("ViewT")

_KEY_ATTRS = (
    "key",
    "pred_atom_key",
    "step_key",
    "atom_key",
    "asrt_id",
    "id",
)


class FrozenTupleView(Generic[ViewT]):
    """Frozen adapter around an already-frozen tuple collection."""

    __slots__ = ("_frozen", "_items", "_source_id")

    def __init__(self, items: tuple[ViewT, ...], *, source_id: str | None = None) -> None:
        if not isinstance(items, tuple):
            raise TypeError("FrozenTupleView items must be tuple")
        object.__setattr__(self, "_frozen", False)
        object.__setattr__(self, "_items", items)
        object.__setattr__(self, "_source_id", source_id)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("FrozenTupleView is frozen")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("FrozenTupleView is frozen")
        object.__delattr__(self, name)

    @property
    def underlying(self) -> tuple[ViewT, ...]:
        return self._items

    @property
    def source_id(self) -> str | None:
        return self._source_id

    def __iter__(self) -> Iterator[ViewT]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> ViewT:
        return self._items[index]

    def filter(
        self,
        predicate: Callable[[ViewT], bool] | None = None,
        **attrs: Any,
    ) -> "FrozenTupleView[ViewT]":
        """Return a new eager view narrowed by predicate and attr equality."""

        def matches(item: ViewT) -> bool:
            if predicate is not None and not predicate(item):
                return False
            for name, expected in attrs.items():
                if getattr(item, name, None) != expected:
                    return False
            return True

        return FrozenTupleView(tuple(item for item in self._items if matches(item)), source_id=self.source_id)

    def find(self, predicate: Callable[[ViewT], bool]) -> ViewT | None:
        for item in self._items:
            if predicate(item):
                return item
        return None

    def first(self) -> ViewT | None:
        if not self._items:
            return None
        return self._items[0]

    def require_position(self, position: int) -> ViewT:
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            raise WalkerLookupError(f"position must be non-negative int: {position!r}")
        try:
            return self._items[position]
        except IndexError as exc:
            raise WalkerLookupError(f"item not found at position: {position}") from exc

    def require_key(
        self,
        value: Any,
        *,
        key: Callable[[ViewT], Any] | None = None,
    ) -> ViewT:
        extractor = key or _default_key
        saw_key_like_item = False
        for item in self._items:
            try:
                item_key = extractor(item)
            except WalkerLookupError:
                continue
            saw_key_like_item = True
            if item_key == value:
                return item
        if not saw_key_like_item:
            raise WalkerLookupError("no item exposes a key-like attribute")
        raise WalkerLookupError(f"item not found for key: {value!r}")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FrozenTupleView):
            return NotImplemented
        return self.underlying == other.underlying

    def __hash__(self) -> int:
        return hash(self.underlying)

    def __repr__(self) -> str:
        return f"FrozenTupleView(source_id={self.source_id!r}, count={len(self)})"


def _default_key(item: object) -> Any:
    for attr in _KEY_ATTRS:
        if hasattr(item, attr):
            return getattr(item, attr)
    raise WalkerLookupError("item does not expose a key-like attribute")


def frozen_collection(items: tuple[ViewT, ...], *, source_id: str | None = None) -> FrozenTupleView[ViewT]:
    """Wrap an existing tuple in a `FrozenTupleView`."""

    return FrozenTupleView(items, source_id=source_id)


__all__ = [
    "FrozenTupleView",
    "frozen_collection",
]
