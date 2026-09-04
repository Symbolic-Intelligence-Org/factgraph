"""Condition key parsing for evidence cross-referencing (B2)."""

from __future__ import annotations

import re
from typing import Any, Literal

from .errors import WalkerFrozenError, WalkerParseError

ConditionKeyKind = Literal["unknown", "pred", "step"]

_CONDITION_KEY_RE = re.compile(r"^c(?P<case>\d+)\.c(?P<condition>\d+):(?P<payload>.+)$")


class ConditionKeyView:
    """Frozen parsed view over a `c{case}.c{condition}:{payload}` condition key."""

    __slots__ = (
        "_case_index",
        "_condition_index",
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
        case_index: int,
        condition_index: int,
        payload: str,
        kind: ConditionKeyKind = "unknown",
        pred_id: str | None = None,
        step_kind: str | None = None,
        underlying: str | None = None,
    ) -> None:
        _validate_condition_key_view_args(
            key=key,
            case_index=case_index,
            condition_index=condition_index,
            payload=payload,
            kind=kind,
            pred_id=pred_id,
            step_kind=step_kind,
            underlying=underlying,
        )
        object.__setattr__(self, "_frozen", False)
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "_case_index", case_index)
        object.__setattr__(self, "_condition_index", condition_index)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_pred_id", pred_id)
        object.__setattr__(self, "_step_kind", step_kind)
        object.__setattr__(self, "_underlying", key if underlying is None else underlying)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("ConditionKeyView is frozen")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_frozen", False):
            raise WalkerFrozenError("ConditionKeyView is frozen")
        object.__delattr__(self, name)

    @property
    def key(self) -> str:
        return self._key

    @property
    def case_index(self) -> int:
        return self._case_index

    @property
    def condition_index(self) -> int:
        return self._condition_index

    @property
    def payload(self) -> str:
        return self._payload

    @property
    def kind(self) -> ConditionKeyKind:
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

    def as_pred(self) -> ConditionKeyView:
        return ConditionKeyView(
            key=self.key,
            case_index=self.case_index,
            condition_index=self.condition_index,
            payload=self.payload,
            kind="pred",
            pred_id=self.payload,
            step_kind=None,
            underlying=self.underlying,
        )

    def as_step(self) -> ConditionKeyView:
        return ConditionKeyView(
            key=self.key,
            case_index=self.case_index,
            condition_index=self.condition_index,
            payload=self.payload,
            kind="step",
            pred_id=None,
            step_kind=self.payload,
            underlying=self.underlying,
        )

    def _surface(self) -> tuple[Any, ...]:
        return (
            self.key,
            self.case_index,
            self.condition_index,
            self.payload,
            self.kind,
            self.pred_id,
            self.step_kind,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConditionKeyView):
            return NotImplemented
        return self._surface() == other._surface()

    def __hash__(self) -> int:
        return hash(self._surface())

    def __repr__(self) -> str:
        return (
            "ConditionKeyView("
            f"key={self.key!r}, kind={self.kind!r}, "
            f"case_index={self.case_index}, condition_index={self.condition_index})"
        )


def parse_condition_key(key: str) -> ConditionKeyView:
    """Parse `c{case}.c{condition}:{payload}` into a `ConditionKeyView`.

    The payload is intentionally syntactic here; context-specific callers
    promote it to pred or step semantics with `as_pred()` / `as_step()`.
    """

    if not isinstance(key, str):
        raise WalkerParseError("condition key must be string")
    match = _CONDITION_KEY_RE.match(key)
    if match is None:
        raise WalkerParseError(f"invalid condition key: {key!r}")
    return ConditionKeyView(
        key=key,
        case_index=int(match.group("case")),
        condition_index=int(match.group("condition")),
        payload=match.group("payload"),
        kind="unknown",
        pred_id=None,
        step_kind=None,
        underlying=key,
    )


def _validate_condition_key_view_args(
    *,
    key: str,
    case_index: int,
    condition_index: int,
    payload: str,
    kind: ConditionKeyKind,
    pred_id: str | None,
    step_kind: str | None,
    underlying: str | None,
) -> None:
    if not isinstance(key, str) or not key:
        raise WalkerParseError("condition key must be non-empty string")
    if isinstance(case_index, bool) or not isinstance(case_index, int) or case_index < 0:
        raise WalkerParseError("case_index must be non-negative int")
    if isinstance(condition_index, bool) or not isinstance(condition_index, int) or condition_index < 0:
        raise WalkerParseError("condition_index must be non-negative int")
    if not isinstance(payload, str) or not payload:
        raise WalkerParseError("payload must be non-empty string")
    if kind not in {"unknown", "pred", "step"}:
        raise WalkerParseError("kind must be 'unknown', 'pred', or 'step'")
    if kind == "unknown" and (pred_id is not None or step_kind is not None):
        raise WalkerParseError("unknown condition key must not carry pred_id or step_kind")
    if kind == "pred" and (not isinstance(pred_id, str) or not pred_id or step_kind is not None):
        raise WalkerParseError("pred condition key must carry pred_id only")
    if kind == "step" and (not isinstance(step_kind, str) or not step_kind or pred_id is not None):
        raise WalkerParseError("step condition key must carry step_kind only")
    if underlying is not None and not isinstance(underlying, str):
        raise WalkerParseError("underlying condition key must be string")


__all__ = [
    "ConditionKeyKind",
    "ConditionKeyView",
    "parse_condition_key",
]
