from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from factgraph.core.store._support import (
    BindingItems,
    ProofReceipt,
    ProvenanceEnvelope,
    normalize_binding_items,
)

from .common import (
    ErrorDTO,
    ProtocolShapeError,
    WarningDTO,
    _require_literal,
    _require_non_empty_str,
    _validate_tuple_items,
)
from .derivation import CompiledDerivationPlan

CheckStatus: TypeAlias = Literal["passed", "failed", "unsupported", "invalid_request"]
CheckEngine: TypeAlias = Literal["native", "souffle", "problog", "pyreason"]

_CHECK_ENGINES = ("native", "souffle", "problog", "pyreason")
_CHECK_STATUSES = ("passed", "failed", "unsupported", "invalid_request")


def _validate_binding_items(value: Any, *, field_name: str) -> BindingItems:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be BindingItems tuple")

    seen: set[str] = set()
    for idx, item in enumerate(value):
        if not isinstance(item, tuple) or len(item) != 2:
            raise ProtocolShapeError(f"{field_name}[{idx}] must be tuple[str, Any]")
        key = item[0]
        if not isinstance(key, str) or not key:
            raise ProtocolShapeError(f"{field_name}[{idx}][0] must be non-empty string")
        if not key.startswith("$") or len(key) == 1:
            raise ProtocolShapeError(f"{field_name}[{idx}][0] must be $-prefixed variable")
        if key in seen:
            raise ProtocolShapeError(f"{field_name} must not contain duplicate variable names")
        seen.add(key)

    try:
        return normalize_binding_items(value)
    except ValueError as exc:
        raise ProtocolShapeError(f"{field_name} must be valid BindingItems") from exc


def _validate_non_negative_int_or_none(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolShapeError(f"{field_name} must be non-negative int or None")
    return value


def _validate_event_sequence(value: Any, *, field_name: str) -> tuple[int, int]:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or any(
            isinstance(part, bool) or not isinstance(part, int) or part < 0
            for part in value
        )
    ):
        raise ProtocolShapeError(
            f"{field_name} must be a (tx_seq, op_ordinal) pair of non-negative ints"
        )
    return value


@dataclass(frozen=True)
class EvidenceEnvelope:
    engine: CheckEngine
    support_kind: str
    support_digest: str
    case_index: int | None
    proof: ProofReceipt | ProvenanceEnvelope
    as_of_event_seq: tuple[int, int]
    branch_atom_projection: None = None

    def __post_init__(self) -> None:
        _require_literal(self.engine, field_name="engine", allowed=_CHECK_ENGINES)
        _require_non_empty_str(self.support_kind, field_name="support_kind")
        support_digest = _require_non_empty_str(self.support_digest, field_name="support_digest")
        if not support_digest.startswith("sha256:"):
            raise ProtocolShapeError("support_digest must be sha256 token")
        _validate_non_negative_int_or_none(self.case_index, field_name="case_index")
        if not isinstance(self.proof, (ProofReceipt, ProvenanceEnvelope)):
            raise ProtocolShapeError("proof must be ProofReceipt or ProvenanceEnvelope")
        _validate_event_sequence(self.as_of_event_seq, field_name="as_of_event_seq")
        if self.branch_atom_projection is not None:
            raise ProtocolShapeError("branch_atom_projection must be None in MVP")


@dataclass(frozen=True)
class CheckRequest:
    plan: CompiledDerivationPlan
    binding: BindingItems
    engine: CheckEngine

    def __post_init__(self) -> None:
        if not isinstance(self.plan, CompiledDerivationPlan):
            raise ProtocolShapeError("plan must be CompiledDerivationPlan")
        if len(self.plan.heads) != 1:
            raise ProtocolShapeError("plan must contain exactly one head for CheckRequest")
        object.__setattr__(
            self,
            "binding",
            _validate_binding_items(self.binding, field_name="binding"),
        )
        _require_literal(self.engine, field_name="engine", allowed=_CHECK_ENGINES)


@dataclass(frozen=True)
class CheckResult:
    status: CheckStatus
    requested_binding: BindingItems
    matched_count: int | None
    matched_binding: BindingItems | None
    evidence_envelope: EvidenceEnvelope | None
    errors: tuple[ErrorDTO, ...] = field(default_factory=tuple)
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        status = _require_literal(self.status, field_name="status", allowed=_CHECK_STATUSES)
        object.__setattr__(
            self,
            "requested_binding",
            _validate_binding_items(self.requested_binding, field_name="requested_binding"),
        )
        if self.matched_binding is not None:
            object.__setattr__(
                self,
                "matched_binding",
                _validate_binding_items(self.matched_binding, field_name="matched_binding"),
            )
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)

        if status == "passed":
            if (
                isinstance(self.matched_count, bool)
                or not isinstance(self.matched_count, int)
                or self.matched_count < 1
            ):
                raise ProtocolShapeError("passed CheckResult requires matched_count >= 1")
            if self.matched_binding is None:
                raise ProtocolShapeError("passed CheckResult requires matched_binding")
            if not isinstance(self.evidence_envelope, EvidenceEnvelope):
                raise ProtocolShapeError("passed CheckResult requires evidence_envelope")
            return

        if status == "failed":
            if self.matched_count != 0:
                raise ProtocolShapeError("failed CheckResult requires matched_count == 0")
            if self.matched_binding is not None:
                raise ProtocolShapeError("failed CheckResult requires matched_binding=None")
            if self.evidence_envelope is not None:
                raise ProtocolShapeError("failed CheckResult requires evidence_envelope=None")
            return

        if self.matched_count is not None:
            raise ProtocolShapeError(f"{status} CheckResult requires matched_count=None")
        if self.matched_binding is not None:
            raise ProtocolShapeError(f"{status} CheckResult requires matched_binding=None")
        if self.evidence_envelope is not None:
            raise ProtocolShapeError(f"{status} CheckResult requires evidence_envelope=None")
        if not self.errors:
            raise ProtocolShapeError(f"{status} CheckResult requires errors")


__all__ = [
    "CheckRequest",
    "CheckResult",
    "CheckStatus",
    "EvidenceEnvelope",
]
