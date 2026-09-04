"""ProofFrame recheck protocol DTOs.

ProofFrame Rechecker is a narrow application capability over native
``ProofReceipt`` frames and fact-side ``FactOverlay`` actions. Runtime
dependencies such as ``Store`` stay side-channel kwargs to the executor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from factgraph.core.store._support import (
    BindingItems,
    ProofReceipt,
    normalize_binding_items,
)

from .common import ProtocolShapeError, _require_literal, _require_non_empty_str
from .derivation_fact_overlay import FactOverlay

ProofFrameStatus: TypeAlias = Literal["still_valid", "invalidated", "unknown"]

_PROOF_FRAME_STATUSES = ("still_valid", "invalidated", "unknown")
_PROOF_FRAME_STATUS_PRIORITY = {
    "still_valid": 0,
    "unknown": 1,
    "invalidated": 2,
}


def aggregate_proof_frame_status(
    atom_verdicts: tuple["ProofFrameConditionVerdict", ...],  # noqa: UP037 - Preserve Python 3.10 runtime hint shape.
) -> ProofFrameStatus:
    """Aggregate per-atom verdicts using the scoped Batch 4 priority rule."""

    if not atom_verdicts:
        return "unknown"
    return max(
        (verdict.verdict for verdict in atom_verdicts),
        key=lambda status: _PROOF_FRAME_STATUS_PRIORITY[status],
    )


def _validate_binding_items(value: Any, *, field_name: str) -> BindingItems:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be BindingItems tuple")
    try:
        return normalize_binding_items(value)
    except ValueError as exc:
        raise ProtocolShapeError(f"{field_name} must be valid BindingItems") from exc


def _validate_action_indices(
    value: Any, *, field_name: str
) -> tuple[int, ...]:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[int, ...]")
    seen: set[int] = set()
    normalized: list[int] = []
    for idx, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise ProtocolShapeError(f"{field_name}[{idx}] must be non-negative int")
        if item in seen:
            raise ProtocolShapeError(f"{field_name} must not contain duplicate indices")
        seen.add(item)
        normalized.append(item)
    if tuple(normalized) != tuple(sorted(normalized)):
        raise ProtocolShapeError(f"{field_name} must be sorted")
    return tuple(normalized)


def _validate_atom_verdicts(
    value: Any, *, field_name: str
) -> tuple["ProofFrameConditionVerdict", ...]:  # noqa: UP037 - Preserve Python 3.10 runtime hint shape.
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[ProofFrameConditionVerdict, ...]")
    for idx, item in enumerate(value):
        if not isinstance(item, ProofFrameConditionVerdict):
            raise ProtocolShapeError(f"{field_name}[{idx}] must be ProofFrameConditionVerdict")
    return value


@dataclass(frozen=True)
class ProofFrameRecheckRequest:
    support_artifact: ProofReceipt
    overlay: FactOverlay

    def __post_init__(self) -> None:
        if not isinstance(self.support_artifact, ProofReceipt):
            raise ProtocolShapeError("support_artifact must be ProofReceipt")
        if not isinstance(self.overlay, FactOverlay):
            raise ProtocolShapeError("overlay must be FactOverlay")


@dataclass(frozen=True)
class ProofFrameConditionVerdict:
    condition_key: str
    verdict: ProofFrameStatus
    affected_action_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.condition_key, field_name="condition_key")
        _require_literal(
            self.verdict,
            field_name="verdict",
            allowed=_PROOF_FRAME_STATUSES,
        )
        object.__setattr__(
            self,
            "affected_action_indices",
            _validate_action_indices(
                self.affected_action_indices,
                field_name="affected_action_indices",
            ),
        )


@dataclass(frozen=True)
class ProofFrameRecheckResult:
    status: ProofFrameStatus
    binding_items: BindingItems
    atom_verdicts: tuple[ProofFrameConditionVerdict, ...]

    def __post_init__(self) -> None:
        _require_literal(self.status, field_name="status", allowed=_PROOF_FRAME_STATUSES)
        object.__setattr__(
            self,
            "binding_items",
            _validate_binding_items(self.binding_items, field_name="binding_items"),
        )
        object.__setattr__(
            self,
            "atom_verdicts",
            _validate_atom_verdicts(self.atom_verdicts, field_name="atom_verdicts"),
        )
        expected = aggregate_proof_frame_status(self.atom_verdicts)
        if self.status != expected:
            raise ProtocolShapeError(
                "status must equal aggregate_proof_frame_status(atom_verdicts)"
            )


__all__ = [
    "ProofFrameConditionVerdict",
    "ProofFrameRecheckRequest",
    "ProofFrameRecheckResult",
    "ProofFrameStatus",
    "aggregate_proof_frame_status",
]
