"""IR walker for derivation rule bodies (B1)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from factgraph.core.store._support import make_non_fact_step_key, make_pred_condition_key

from ._freeze import freeze_value
from .errors import WalkerFrozenError, WalkerLookupError, WalkerSnapshotError


class IRAtomView:
    """Frozen view over one IR atom in a construction-time snapshot.

    `underlying` is the frozen snapshot atom, not the original mutable source
    object. It is an escape hatch and is excluded from equality / hash.
    """

    __slots__ = (
        "_args",
        "_condition_index",
        "_case_index",
        "_frozen",
        "_key",
        "_kind",
        "_pred_id",
        "_underlying",
    )

    def __init__(
        self,
        *,
        kind: str,
        pred_id: str | None,
        args: tuple[Any, ...],
        case_index: int,
        condition_index: int,
        key: str,
        underlying: tuple[Any, ...],
    ) -> None:
        object.__setattr__(self, "_frozen", False)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_pred_id", pred_id)
        object.__setattr__(self, "_args", args)
        object.__setattr__(self, "_case_index", case_index)
        object.__setattr__(self, "_condition_index", condition_index)
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "_underlying", underlying)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("IRAtomView is frozen")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("IRAtomView is frozen")
        object.__delattr__(self, name)

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def pred_id(self) -> str | None:
        return self._pred_id

    @property
    def args(self) -> tuple[Any, ...]:
        return self._args

    @property
    def case_index(self) -> int:
        return self._case_index

    @property
    def condition_index(self) -> int:
        return self._condition_index

    @property
    def key(self) -> str:
        return self._key

    @property
    def underlying(self) -> tuple[Any, ...]:
        return self._underlying

    def _surface(self) -> tuple[Any, ...]:
        return (
            self.kind,
            self.pred_id,
            self.args,
            self.case_index,
            self.condition_index,
            self.key,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IRAtomView):
            return NotImplemented
        return self._surface() == other._surface()

    def __hash__(self) -> int:
        return hash(self._surface())

    def __repr__(self) -> str:
        return (
            "IRAtomView("
            f"kind={self.kind!r}, key={self.key!r}, "
            f"case_index={self.case_index}, condition_index={self.condition_index})"
        )


class IRBodyWalker:
    """Walker over flat AND or OR-of-AND rule body IR.

    Construction snapshots and freezes the source body; `IRAtomView` objects
    are created lazily during traversal / lookup.
    """

    __slots__ = ("_branches", "_frozen", "_source_id")

    def __init__(self, source: list[Any] | tuple[Any, ...], *, source_id: str | None = None) -> None:
        object.__setattr__(self, "_frozen", False)
        object.__setattr__(self, "_source_id", source_id)
        object.__setattr__(self, "_branches", _snapshot_branches(source))
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("IRBodyWalker is frozen")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("IRBodyWalker is frozen")
        object.__delattr__(self, name)

    @property
    def source_id(self) -> str | None:
        return self._source_id

    def __iter__(self):
        for case_index, branch in enumerate(self._branches):
            for condition_index, atom in enumerate(branch):
                yield _build_atom_view(atom, case_index=case_index, condition_index=condition_index)

    def __len__(self) -> int:
        return sum(len(branch) for branch in self._branches)

    def find(
        self,
        *,
        key: str | None = None,
        kind: str | None = None,
        pred_id: str | None = None,
        case_index: int | None = None,
        condition_index: int | None = None,
    ) -> IRAtomView | None:
        for atom in self:
            if key is not None and atom.key != key:
                continue
            if kind is not None and atom.kind != kind:
                continue
            if pred_id is not None and atom.pred_id != pred_id:
                continue
            if case_index is not None and atom.case_index != case_index:
                continue
            if condition_index is not None and atom.condition_index != condition_index:
                continue
            return atom
        return None

    def require_key(self, key: str) -> IRAtomView:
        found = self.find(key=key)
        if found is None:
            raise WalkerLookupError(f"IR atom not found for key: {key}")
        return found

    def require_position(self, *, case_index: int, condition_index: int) -> IRAtomView:
        found = self.find(case_index=case_index, condition_index=condition_index)
        if found is None:
            raise WalkerLookupError(
                f"IR atom not found at case_index={case_index}, condition_index={condition_index}"
            )
        return found

    @property
    def underlying(self) -> tuple[tuple[tuple[Any, ...], ...], ...]:
        return self._branches

    def __repr__(self) -> str:
        return f"IRBodyWalker(source_id={self.source_id!r}, atom_count={len(self)})"


def _snapshot_branches(source: object) -> tuple[tuple[tuple[Any, ...], ...], ...]:
    if not isinstance(source, (list, tuple)):
        raise WalkerSnapshotError("IRBodyWalker source must be list or tuple")
    # Empty sources must stay unambiguously empty; otherwise `all(...)` below
    # would treat them as a vacuous flat-AND body.
    if not source:
        return ()

    if all(_is_atom(item) for item in source):
        return (tuple(_snapshot_atom(atom) for atom in source),)

    if all(_is_branch(item) for item in source):
        return tuple(
            tuple(_snapshot_atom(atom) for atom in branch)  # type: ignore[arg-type]
            for branch in source
        )

    raise WalkerSnapshotError("IR body must be flat AND or OR-of-AND")


def _is_atom(value: object) -> bool:
    return isinstance(value, tuple) and bool(value) and isinstance(value[0], str)


def _is_branch(value: object) -> bool:
    return isinstance(value, (list, tuple)) and bool(value) and not _is_atom(value) and all(
        _is_atom(item) for item in value
    )


def _snapshot_atom(atom: object) -> tuple[Any, ...]:
    if not _is_atom(atom):
        raise WalkerSnapshotError("IR atom must be tuple(kind, ...)")
    frozen = freeze_value(atom)
    if not isinstance(frozen, tuple) or not frozen:
        raise WalkerSnapshotError("IR atom snapshot failed")
    kind = frozen[0]
    if not isinstance(kind, str) or not kind:
        raise WalkerSnapshotError("IR atom kind must be non-empty string")
    if kind == "pred" and (
        len(frozen) != 3
        or not isinstance(frozen[1], str)
        or not frozen[1]
        or not isinstance(frozen[2], tuple)
    ):
        raise WalkerSnapshotError("pred atom must be ('pred', pred_id, [terms...])")
    if kind == "ruleref" and (
        len(frozen) != 4
        or not isinstance(frozen[1], str)
        or not frozen[1]
        or not (frozen[2] is None or (isinstance(frozen[2], str) and bool(frozen[2])))
        or not isinstance(frozen[3], tuple)
    ):
        raise WalkerSnapshotError("ruleref atom must be ('ruleref', rule_id, version, [terms...])")
    return frozen


def _build_atom_view(atom: tuple[Any, ...], *, case_index: int, condition_index: int) -> IRAtomView:
    kind = atom[0]
    if kind == "pred":
        pred_id = atom[1]
        args = _as_tuple(atom[2])
        key = make_pred_condition_key(case_index, condition_index, pred_id)
    else:
        pred_id = None
        args = tuple(atom[1:])
        key = make_non_fact_step_key(case_index, condition_index, kind)
    return IRAtomView(
        kind=kind,
        pred_id=pred_id,
        args=args,
        case_index=case_index,
        condition_index=condition_index,
        key=key,
        underlying=atom,
    )


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(value)
    return (value,)


__all__ = [
    "IRAtomView",
    "IRBodyWalker",
]
