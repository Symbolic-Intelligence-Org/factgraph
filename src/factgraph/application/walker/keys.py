"""Atom key parsing for evidence cross-referencing (B2)."""

from __future__ import annotations

import re
from typing import Any, Literal

from .errors import WalkerFrozenError, WalkerParseError

AtomKeyKind = Literal["unknown", "pred", "step"]

_ATOM_KEY_RE = re.compile(r"^b(?P<branch>\d+)\.a(?P<atom>\d+):(?P<payload>.+)$")


class AtomKeyView:
    """Frozen parsed view over a `b{branch}.a{atom}:{payload}` atom key."""

    __slots__ = (
        "_atom_index",
        "_branch_index",
        "_frozen",
        "_key",
        "_kind",
        "_payload",
        "_pred_id",
        "_step_kind",
        "_underlying",
    )

    def __init__(
        self,
        *,
        key: str,
        branch_index: int,
        atom_index: int,
        payload: str,
        kind: AtomKeyKind = "unknown",
        pred_id: str | None = None,
        step_kind: str | None = None,
        underlying: str | None = None,
    ) -> None:
        _validate_atom_key_view_args(
            key=key,
            branch_index=branch_index,
            atom_index=atom_index,
            payload=payload,
            kind=kind,
            pred_id=pred_id,
            step_kind=step_kind,
            underlying=underlying,
        )
        object.__setattr__(self, "_frozen", False)
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "_branch_index", branch_index)
        object.__setattr__(self, "_atom_index", atom_index)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_pred_id", pred_id)
        object.__setattr__(self, "_step_kind", step_kind)
        object.__setattr__(self, "_underlying", key if underlying is None else underlying)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("AtomKeyView is frozen")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("AtomKeyView is frozen")
        object.__delattr__(self, name)

    @property
    def key(self) -> str:
        return self._key

    @property
    def branch_index(self) -> int:
        return self._branch_index

    @property
    def atom_index(self) -> int:
        return self._atom_index

    @property
    def payload(self) -> str:
        return self._payload

    @property
    def kind(self) -> AtomKeyKind:
        return self._kind

    @property
    def pred_id(self) -> str | None:
        return self._pred_id

    @property
    def step_kind(self) -> str | None:
        return self._step_kind

    @property
    def underlying(self) -> str:
        return self._underlying

    def as_pred(self) -> "AtomKeyView":
        return AtomKeyView(
            key=self.key,
            branch_index=self.branch_index,
            atom_index=self.atom_index,
            payload=self.payload,
            kind="pred",
            pred_id=self.payload,
            step_kind=None,
            underlying=self.underlying,
        )

    def as_step(self) -> "AtomKeyView":
        return AtomKeyView(
            key=self.key,
            branch_index=self.branch_index,
            atom_index=self.atom_index,
            payload=self.payload,
            kind="step",
            pred_id=None,
            step_kind=self.payload,
            underlying=self.underlying,
        )

    def _surface(self) -> tuple[Any, ...]:
        return (
            self.key,
            self.branch_index,
            self.atom_index,
            self.payload,
            self.kind,
            self.pred_id,
            self.step_kind,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AtomKeyView):
            return NotImplemented
        return self._surface() == other._surface()

    def __hash__(self) -> int:
        return hash(self._surface())

    def __repr__(self) -> str:
        return (
            "AtomKeyView("
            f"key={self.key!r}, kind={self.kind!r}, "
            f"branch_index={self.branch_index}, atom_index={self.atom_index})"
        )


def parse_atom_key(key: str) -> AtomKeyView:
    """Parse `b{branch}.a{atom}:{payload}` into an `AtomKeyView`.

    The payload is intentionally syntactic here; context-specific callers
    promote it to pred or step semantics with `as_pred()` / `as_step()`.
    """

    if not isinstance(key, str):
        raise WalkerParseError("atom key must be string")
    match = _ATOM_KEY_RE.match(key)
    if match is None:
        raise WalkerParseError(f"invalid atom key: {key!r}")
    return AtomKeyView(
        key=key,
        branch_index=int(match.group("branch")),
        atom_index=int(match.group("atom")),
        payload=match.group("payload"),
        kind="unknown",
        pred_id=None,
        step_kind=None,
        underlying=key,
    )


def _validate_atom_key_view_args(
    *,
    key: str,
    branch_index: int,
    atom_index: int,
    payload: str,
    kind: AtomKeyKind,
    pred_id: str | None,
    step_kind: str | None,
    underlying: str | None,
) -> None:
    if not isinstance(key, str) or not key:
        raise WalkerParseError("atom key must be non-empty string")
    if isinstance(branch_index, bool) or not isinstance(branch_index, int) or branch_index < 0:
        raise WalkerParseError("branch_index must be non-negative int")
    if isinstance(atom_index, bool) or not isinstance(atom_index, int) or atom_index < 0:
        raise WalkerParseError("atom_index must be non-negative int")
    if not isinstance(payload, str) or not payload:
        raise WalkerParseError("payload must be non-empty string")
    if kind not in {"unknown", "pred", "step"}:
        raise WalkerParseError("kind must be 'unknown', 'pred', or 'step'")
    if kind == "unknown" and (pred_id is not None or step_kind is not None):
        raise WalkerParseError("unknown atom key must not carry pred_id or step_kind")
    if kind == "pred" and (not isinstance(pred_id, str) or not pred_id or step_kind is not None):
        raise WalkerParseError("pred atom key must carry pred_id only")
    if kind == "step" and (not isinstance(step_kind, str) or not step_kind or pred_id is not None):
        raise WalkerParseError("step atom key must carry step_kind only")
    if underlying is not None and not isinstance(underlying, str):
        raise WalkerParseError("underlying atom key must be string")


__all__ = [
    "AtomKeyKind",
    "AtomKeyView",
    "parse_atom_key",
]
