"""Per-DTO wrapper views for application / audit DTOs (B1 + B2).

Phase 3 implements:

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

from collections.abc import Callable, Iterator, Mapping
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from kernel.core.store._support import SupportArtifact
from kernel.core.store.ledger import Claim, MetaRow

from .errors import WalkerFrozenError, WalkerLookupError, WalkerReferenceError, WalkerSnapshotError
from .keys import AtomKeyView, parse_atom_key

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


class AssertionView:
    """Frozen surfaced view over a ledger `Claim`.

    `underlying` returns the original `Claim` escape hatch. The surfaced
    fields snapshot mutable `Claim.rest_terms`; callers who use `underlying`
    accept its mutability and DTO evolution risk.
    """

    __slots__ = (
        "_asrt_id",
        "_e_ref",
        "_frozen",
        "_meta_rows",
        "_pred_id",
        "_rest_terms",
        "_underlying",
    )

    def __init__(
        self,
        asrt_id: str,
        claim_index: Mapping[str, Claim],
        meta_index: Mapping[str, tuple[MetaRow, ...]] | None = None,
    ) -> None:
        if not isinstance(asrt_id, str) or not asrt_id:
            raise WalkerReferenceError("asrt_id must be non-empty string")
        if not isinstance(claim_index, Mapping):
            raise TypeError("claim_index must be Mapping[str, Claim]")
        claim = claim_index.get(asrt_id)
        if claim is None:
            raise WalkerReferenceError(f"assertion not found: {asrt_id!r}")
        if not isinstance(claim, Claim):
            raise TypeError("claim_index values must be Claim")
        snapshot = _snapshot_assertion(asrt_id, claim, _snapshot_meta_rows(meta_index, asrt_id))

        object.__setattr__(self, "_frozen", False)
        _set_assertion_snapshot(self, snapshot, claim)
        object.__setattr__(self, "_frozen", True)

    @classmethod
    def _from_snapshot(cls, snapshot: "_AssertionSnapshot") -> "AssertionView":
        view = cls.__new__(cls)
        object.__setattr__(view, "_frozen", False)
        _set_assertion_snapshot(view, snapshot, snapshot.underlying)
        object.__setattr__(view, "_frozen", True)
        return view

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("AssertionView is frozen")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("AssertionView is frozen")
        object.__delattr__(self, name)

    @property
    def asrt_id(self) -> str:
        return self._asrt_id

    @property
    def pred_id(self) -> str:
        return self._pred_id

    @property
    def e_ref(self) -> str:
        return self._e_ref

    @property
    def rest_terms(self) -> tuple[tuple[str, Any], ...]:
        return self._rest_terms

    @property
    def meta_rows(self) -> tuple[MetaRow, ...]:
        return self._meta_rows

    @property
    def underlying(self) -> Claim:
        return self._underlying

    def _surface(self) -> tuple[Any, ...]:
        return (
            self.asrt_id,
            self.pred_id,
            self.e_ref,
            self.rest_terms,
            self.meta_rows,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AssertionView):
            return NotImplemented
        return self._surface() == other._surface()

    def __hash__(self) -> int:
        return hash(self._surface())

    def __repr__(self) -> str:
        return f"AssertionView(asrt_id={self.asrt_id!r}, pred_id={self.pred_id!r})"


class SupportArtifactView:
    """Frozen wrapper view over `SupportArtifact` plus assertion indexes."""

    __slots__ = (
        "_claim_index",
        "_frozen",
        "_meta_index",
        "_non_fact_steps",
        "_pred_witnesses",
        "_source_id",
        "_underlying",
    )

    def __init__(
        self,
        support: SupportArtifact,
        frozen_claim_index: Mapping[str, Claim],
        frozen_meta_index: Mapping[str, tuple[MetaRow, ...]] | None = None,
        *,
        source_id: str | None = None,
    ) -> None:
        if not isinstance(support, SupportArtifact):
            raise TypeError("support must be SupportArtifact")
        if not isinstance(frozen_claim_index, Mapping):
            raise TypeError("frozen_claim_index must be Mapping[str, Claim]")

        meta_index = _freeze_meta_index(frozen_meta_index)
        claim_index = _freeze_claim_index(frozen_claim_index, meta_index)

        object.__setattr__(self, "_frozen", False)
        object.__setattr__(self, "_underlying", support)
        object.__setattr__(self, "_claim_index", claim_index)
        object.__setattr__(self, "_meta_index", meta_index)
        object.__setattr__(self, "_source_id", source_id)
        object.__setattr__(self, "_pred_witnesses", FrozenTupleView(support.pred_witnesses, source_id=source_id))
        object.__setattr__(self, "_non_fact_steps", FrozenTupleView(support.non_fact_steps, source_id=source_id))
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("SupportArtifactView is frozen")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("SupportArtifactView is frozen")
        object.__delattr__(self, name)

    @property
    def underlying(self) -> SupportArtifact:
        return self._underlying

    @property
    def source_id(self) -> str | None:
        return self._source_id

    @property
    def pred_witnesses(self) -> FrozenTupleView[Any]:
        return self._pred_witnesses

    @property
    def non_fact_steps(self) -> FrozenTupleView[Any]:
        return self._non_fact_steps

    def parse_pred_atom_key(self, key: str) -> AtomKeyView:
        return parse_atom_key(key).as_pred()

    def parse_step_key(self, key: str) -> AtomKeyView:
        return parse_atom_key(key).as_step()

    def lookup_assertion(self, asrt_id: str) -> AssertionView:
        if not isinstance(asrt_id, str) or not asrt_id:
            raise WalkerReferenceError("asrt_id must be non-empty string")
        snapshot = self._claim_index.get(asrt_id)
        if snapshot is None:
            raise WalkerReferenceError(f"assertion not found: {asrt_id!r}")
        return AssertionView._from_snapshot(snapshot)

    def __repr__(self) -> str:
        return (
            f"SupportArtifactView(source_id={self.source_id!r}, "
            f"pred_witnesses={len(self.pred_witnesses)}, non_fact_steps={len(self.non_fact_steps)})"
        )


class _AssertionSnapshot:
    __slots__ = ("asrt_id", "e_ref", "meta_rows", "pred_id", "rest_terms", "underlying")

    def __init__(
        self,
        *,
        asrt_id: str,
        pred_id: str,
        e_ref: str,
        rest_terms: tuple[tuple[str, Any], ...],
        meta_rows: tuple[MetaRow, ...],
        underlying: Claim,
    ) -> None:
        self.asrt_id = asrt_id
        self.pred_id = pred_id
        self.e_ref = e_ref
        self.rest_terms = rest_terms
        self.meta_rows = meta_rows
        self.underlying = underlying


def _set_assertion_snapshot(view: AssertionView, snapshot: _AssertionSnapshot, underlying: Claim) -> None:
    object.__setattr__(view, "_asrt_id", snapshot.asrt_id)
    object.__setattr__(view, "_pred_id", snapshot.pred_id)
    object.__setattr__(view, "_e_ref", snapshot.e_ref)
    object.__setattr__(view, "_rest_terms", snapshot.rest_terms)
    object.__setattr__(view, "_meta_rows", snapshot.meta_rows)
    object.__setattr__(view, "_underlying", underlying)


def _snapshot_assertion(
    requested_asrt_id: str,
    claim: Claim,
    meta_rows: tuple[MetaRow, ...],
) -> _AssertionSnapshot:
    if not isinstance(claim.asrt_id, str) or not claim.asrt_id:
        raise WalkerSnapshotError("Claim.asrt_id must be non-empty string")
    if claim.asrt_id != requested_asrt_id:
        raise WalkerSnapshotError("claim_index key must match Claim.asrt_id")
    if not isinstance(claim.pred_id, str) or not claim.pred_id:
        raise WalkerSnapshotError("Claim.pred_id must be non-empty string")
    if not isinstance(claim.e_ref, str) or not claim.e_ref:
        raise WalkerSnapshotError("Claim.e_ref must be non-empty string")
    return _AssertionSnapshot(
        asrt_id=claim.asrt_id,
        pred_id=claim.pred_id,
        e_ref=claim.e_ref,
        rest_terms=_snapshot_rest_terms(claim.rest_terms),
        meta_rows=_snapshot_meta_rows_values(meta_rows),
        underlying=claim,
    )


def _snapshot_rest_terms(rest_terms: list[tuple[str, Any]]) -> tuple[tuple[str, Any], ...]:
    if not isinstance(rest_terms, list):
        raise WalkerSnapshotError("Claim.rest_terms must be list")
    frozen_terms: list[tuple[str, Any]] = []
    for term in rest_terms:
        if not isinstance(term, tuple) or len(term) != 2:
            raise WalkerSnapshotError("Claim.rest_terms entries must be tuple(tag, value)")
        tag, value = term
        if not isinstance(tag, str) or not tag:
            raise WalkerSnapshotError("Claim.rest_terms tag must be non-empty string")
        frozen_terms.append((tag, _freeze_value(value)))
    return tuple(frozen_terms)


def _snapshot_meta_rows(
    meta_index: Mapping[str, tuple[MetaRow, ...]] | None,
    asrt_id: str,
) -> tuple[MetaRow, ...]:
    if meta_index is None:
        return ()
    if not isinstance(meta_index, Mapping):
        raise TypeError("meta_index must be Mapping[str, tuple[MetaRow, ...]]")
    rows = tuple(meta_index.get(asrt_id, ()))
    for row in rows:
        if not isinstance(row, MetaRow):
            raise TypeError("meta_index values must contain MetaRow instances")
    return rows


def _snapshot_meta_rows_values(meta_rows: tuple[MetaRow, ...]) -> tuple[MetaRow, ...]:
    frozen_rows: list[MetaRow] = []
    for row in meta_rows:
        if not isinstance(row.asrt_id, str) or not row.asrt_id:
            raise WalkerSnapshotError("MetaRow.asrt_id must be non-empty string")
        if not isinstance(row.key, str) or not row.key:
            raise WalkerSnapshotError("MetaRow.key must be non-empty string")
        if not isinstance(row.kind, str) or not row.kind:
            raise WalkerSnapshotError("MetaRow.kind must be non-empty string")
        frozen_rows.append(MetaRow(row.asrt_id, row.key, row.kind, _freeze_value(row.value)))
    return tuple(frozen_rows)


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(
            sorted(
                ((_freeze_value(key), _freeze_value(item_value)) for key, item_value in value.items()),
                key=lambda item: repr(item[0]),
            )
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_freeze_value(item) for item in value), key=repr))
    try:
        hash(value)
    except TypeError as exc:
        raise WalkerSnapshotError(f"value is not recursively freezable: {value!r}") from exc
    return value


def _freeze_claim_index(
    claim_index: Mapping[str, Claim],
    meta_index: Mapping[str, tuple[MetaRow, ...]],
) -> Mapping[str, _AssertionSnapshot]:
    frozen = dict(claim_index)
    snapshots: dict[str, _AssertionSnapshot] = {}
    for key, claim in frozen.items():
        if not isinstance(key, str) or not key:
            raise TypeError("claim_index keys must be non-empty strings")
        if not isinstance(claim, Claim):
            raise TypeError("claim_index values must be Claim")
        snapshots[key] = _snapshot_assertion(key, claim, meta_index.get(key, ()))
    return MappingProxyType(snapshots)


def _freeze_meta_index(
    meta_index: Mapping[str, tuple[MetaRow, ...]] | None,
) -> Mapping[str, tuple[MetaRow, ...]]:
    if meta_index is None:
        return MappingProxyType({})
    if not isinstance(meta_index, Mapping):
        raise TypeError("frozen_meta_index must be Mapping[str, tuple[MetaRow, ...]]")
    frozen: dict[str, tuple[MetaRow, ...]] = {}
    for key, rows in meta_index.items():
        if not isinstance(key, str) or not key:
            raise TypeError("meta_index keys must be non-empty strings")
        row_tuple = tuple(rows)
        for row in row_tuple:
            if not isinstance(row, MetaRow):
                raise TypeError("meta_index values must contain MetaRow instances")
        frozen[key] = row_tuple
    return MappingProxyType(frozen)


__all__ = [
    "AssertionView",
    "FrozenTupleView",
    "SupportArtifactView",
    "frozen_collection",
]
