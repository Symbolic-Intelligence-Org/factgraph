"""IR walker for derivation rule bodies (B1)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from kernel.core.store._support import make_non_fact_step_key, make_pred_atom_key

from .errors import WalkerFrozenError, WalkerLookupError, WalkerSnapshotError


class IRAtomView:
    """Frozen view over one IR atom in a construction-time snapshot.

    `underlying` is the frozen snapshot atom, not the original mutable source
    object. It is an escape hatch and is excluded from equality / hash.
    """

    __slots__ = (
        "_args",
        "_atom_index",
        "_branch_index",
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
        branch_index: int,
        atom_index: int,
        key: str,
        underlying: tuple[Any, ...],
    ) -> None:
        object.__setattr__(self, "_frozen", False)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_pred_id", pred_id)
        object.__setattr__(self, "_args", args)
        object.__setattr__(self, "_branch_index", branch_index)
        object.__setattr__(self, "_atom_index", atom_index)
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
    def branch_index(self) -> int:
        return self._branch_index

    @property
    def atom_index(self) -> int:
        return self._atom_index

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
            self.branch_index,
            self.atom_index,
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
            f"branch_index={self.branch_index}, atom_index={self.atom_index})"
        )


class IRBodyWalker:
    """Walker over flat AND or OR-of-AND rule body IR."""

    def __init__(self, source: list[Any] | tuple[Any, ...], *, source_id: str | None = None) -> None:
        self._source_id = source_id
        self._branches = _snapshot_branches(source)
        self._atoms = tuple(
            _build_atom_view(atom, branch_index=branch_index, atom_index=atom_index)
            for branch_index, branch in enumerate(self._branches)
            for atom_index, atom in enumerate(branch)
        )

    @property
    def source_id(self) -> str | None:
        return self._source_id

    def __iter__(self):
        return iter(self._atoms)

    def __len__(self) -> int:
        return len(self._atoms)

    def find(
        self,
        *,
        key: str | None = None,
        kind: str | None = None,
        pred_id: str | None = None,
        branch_index: int | None = None,
        atom_index: int | None = None,
    ) -> IRAtomView | None:
        for atom in self._atoms:
            if key is not None and atom.key != key:
                continue
            if kind is not None and atom.kind != kind:
                continue
            if pred_id is not None and atom.pred_id != pred_id:
                continue
            if branch_index is not None and atom.branch_index != branch_index:
                continue
            if atom_index is not None and atom.atom_index != atom_index:
                continue
            return atom
        return None

    def require_key(self, key: str) -> IRAtomView:
        found = self.find(key=key)
        if found is None:
            raise WalkerLookupError(f"IR atom not found for key: {key}")
        return found

    def require_position(self, *, branch_index: int, atom_index: int) -> IRAtomView:
        found = self.find(branch_index=branch_index, atom_index=atom_index)
        if found is None:
            raise WalkerLookupError(
                f"IR atom not found at branch_index={branch_index}, atom_index={atom_index}"
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
    frozen = _freeze_ir_value(atom)
    if not isinstance(frozen, tuple) or not frozen:
        raise WalkerSnapshotError("IR atom snapshot failed")
    kind = frozen[0]
    if not isinstance(kind, str) or not kind:
        raise WalkerSnapshotError("IR atom kind must be non-empty string")
    if kind == "pred":
        if len(frozen) != 3 or not isinstance(frozen[1], str) or not isinstance(frozen[2], tuple):
            raise WalkerSnapshotError("pred atom must be ('pred', pred_id, [terms...])")
    if kind == "ruleref":
        if (
            len(frozen) != 4
            or not isinstance(frozen[1], str)
            or not (frozen[2] is None or isinstance(frozen[2], str))
            or not isinstance(frozen[3], tuple)
        ):
            raise WalkerSnapshotError("ruleref atom must be ('ruleref', rule_id, version, [terms...])")
    return frozen


def _freeze_ir_value(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_freeze_ir_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_ir_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(
            (key, _freeze_ir_value(inner_value))
            for key, inner_value in sorted(value.items(), key=lambda item: repr(item[0]))
        )
    return value


def _build_atom_view(atom: tuple[Any, ...], *, branch_index: int, atom_index: int) -> IRAtomView:
    kind = atom[0]
    if kind == "pred":
        pred_id = atom[1]
        args = _as_tuple(atom[2])
        key = make_pred_atom_key(branch_index, atom_index, pred_id)
    else:
        pred_id = None
        args = tuple(atom[1:])
        key = make_non_fact_step_key(branch_index, atom_index, kind)
    return IRAtomView(
        kind=kind,
        pred_id=pred_id,
        args=args,
        branch_index=branch_index,
        atom_index=atom_index,
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
