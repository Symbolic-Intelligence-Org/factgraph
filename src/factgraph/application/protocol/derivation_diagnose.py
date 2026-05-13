"""Diagnose runtime protocol DTOs (Step 0.B D1–D9 + 0.C C7 §7-Diagnose-N gates).

Diagnose is the explanatory dual to Check: it answers "why did this binding fail"
rather than "did it pass / fail / unsupported / invalid". Per Q1 Sibling supersede
(Step 0.B), Diagnose owns its full dispatch and does NOT call
``check_derivation_binding(...)``; this protocol redeclares its status / engine
Literals locally rather than importing Check's, keeping the two capabilities
decoupled at the protocol layer despite identical surface vocabulary.

Anti-regression invariants enforced here (per blueprint §7.2):

- §7-Diagnose-7: ``DiagnoseStatus`` Literal contains exactly Check's 4 values
  (``passed`` / ``failed`` / ``unsupported`` / ``invalid_request``); no 5th value.
- §7-Diagnose-1: evidence-unavailable maps to ``status="unsupported"`` with
  ``EVIDENCE_LOOKUP_MISS`` error (NOT ``status="failed"`` with a hypothetical
  ``failure_kind="evidence_unavailable"``); ``DiagnoseFailureKind`` Literal
  therefore contains only ``no_candidate`` and ``atom_localized``.
- §7-Diagnose-2: ``DiagnoseAtomLocator`` lives only on
  ``DiagnoseResult.diagnostic_payload``; never joins
  ``EvidenceEnvelope.engine_payload`` Union (per D8.note §6.5 scope clarification —
  DiagnoseAtomLocator is capability-output, not engine-native).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from factgraph.core.store._support import (
    BindingItems,
    normalize_binding_items,
)

from .common import (
    ErrorDTO,
    ProtocolShapeError,
    WarningDTO,
    _require_literal,
    _validate_tuple_items,
)
from .derivation import CompiledDerivationPlan

DiagnoseStatus: TypeAlias = Literal["passed", "failed", "unsupported", "invalid_request"]
DiagnoseFailureKind: TypeAlias = Literal["no_candidate", "atom_localized"]
DiagnoseEngine: TypeAlias = Literal["native", "souffle", "problog", "pyreason"]

_DIAGNOSE_STATUSES = ("passed", "failed", "unsupported", "invalid_request")
_DIAGNOSE_FAILURE_KINDS = ("no_candidate", "atom_localized")
_DIAGNOSE_ENGINES = ("native", "souffle", "problog", "pyreason")


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


def _validate_non_negative_int(value: Any, *, field_name: str) -> int:
    if value is None or isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolShapeError(f"{field_name} must be non-negative int")
    return value


@dataclass(frozen=True)
class DiagnoseAtomLocator:
    """Native atom-localizer payload (Step 0.B D8).

    Capability-output (Diagnose-runtime-computed), NOT engine-native — does NOT
    join ``EvidenceEnvelope.engine_payload`` Union per §6.5 scope clarification
    (D8.note). Lives only on ``DiagnoseResult.diagnostic_payload``.

    Top-level atom only in MVP. When the failing atom is ``not(...)`` or
    compound, ``failed_atom_index`` points at the top-level atom in
    ``branch[i]``; nested-atom path tracking is deferred to v1+.
    """

    branch_index: int
    failed_atom_index: int
    attempted_binding: BindingItems

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.branch_index, field_name="branch_index")
        _validate_non_negative_int(self.failed_atom_index, field_name="failed_atom_index")
        object.__setattr__(
            self,
            "attempted_binding",
            _validate_binding_items(self.attempted_binding, field_name="attempted_binding"),
        )


@dataclass(frozen=True)
class DiagnoseRequest:
    """Diagnose intent DTO (Step 0.B D1–D4).

    Carries the diagnostic question only; runtime dependencies (``store`` and
    optional ``registry``) flow through the runtime function's side-channel
    kwargs, NOT through DTO fields. Per Q1 Sibling supersede, no
    ``engine_options``, ``diagnostic_mode``, ``store``, ``registry``,
    ``query_id``, ``run_id``, or precomputed resolutions live on the DTO; the
    Python ``TypeError`` on unknown kwargs is the anti-regression gate (§7.3).
    """

    plan: CompiledDerivationPlan
    binding: BindingItems
    engine: DiagnoseEngine

    def __post_init__(self) -> None:
        if not isinstance(self.plan, CompiledDerivationPlan):
            raise ProtocolShapeError("plan must be CompiledDerivationPlan")
        if len(self.plan.heads) != 1:
            raise ProtocolShapeError("plan must contain exactly one head for DiagnoseRequest")
        object.__setattr__(
            self,
            "binding",
            _validate_binding_items(self.binding, field_name="binding"),
        )
        _require_literal(self.engine, field_name="engine", allowed=_DIAGNOSE_ENGINES)


@dataclass(frozen=True)
class DiagnoseResult:
    """Diagnose result DTO (Step 0.B D5–D9, D6 nullable matrix).

    ``status`` Literal stays Check's 4 values verbatim (§7-Diagnose-7 type-level
    invariant). ``failure_kind`` is an orthogonal field populated only when
    ``status="failed"``. ``diagnostic_payload`` is populated only when
    ``status="failed"`` AND ``failure_kind="atom_localized"``. ``DiagnoseResult``
    does NOT carry an ``EvidenceEnvelope`` (per D9 + Q1 Sibling — callers
    wanting Check's evidence on ``passed`` invoke Check separately).

    Nullable matrix (D6):

    | status          | failure_kind   | matched_count | matched_binding | diagnostic_payload | errors   |
    |-----------------|----------------|---------------|-----------------|--------------------|----------|
    | passed          | None           | >= 1          | populated       | None               | empty    |
    | failed          | no_candidate   | 0             | None            | None               | empty    |
    | failed          | atom_localized | 0             | None            | populated          | empty    |
    | unsupported     | None           | None          | None            | None               | required |
    | invalid_request | None           | None          | None            | None               | required |
    """

    status: DiagnoseStatus
    requested_binding: BindingItems
    matched_count: int | None
    matched_binding: BindingItems | None
    failure_kind: DiagnoseFailureKind | None
    diagnostic_payload: DiagnoseAtomLocator | None
    errors: tuple[ErrorDTO, ...] = field(default_factory=tuple)
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        status = _require_literal(
            self.status, field_name="status", allowed=_DIAGNOSE_STATUSES
        )
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

        if self.failure_kind is not None:
            _require_literal(
                self.failure_kind,
                field_name="failure_kind",
                allowed=_DIAGNOSE_FAILURE_KINDS,
            )
        if self.diagnostic_payload is not None and not isinstance(
            self.diagnostic_payload, DiagnoseAtomLocator
        ):
            raise ProtocolShapeError(
                "diagnostic_payload must be DiagnoseAtomLocator or None"
            )

        if status == "passed":
            if (
                isinstance(self.matched_count, bool)
                or not isinstance(self.matched_count, int)
                or self.matched_count < 1
            ):
                raise ProtocolShapeError("passed DiagnoseResult requires matched_count >= 1")
            if self.matched_binding is None:
                raise ProtocolShapeError("passed DiagnoseResult requires matched_binding")
            if self.failure_kind is not None:
                raise ProtocolShapeError("passed DiagnoseResult requires failure_kind=None")
            if self.diagnostic_payload is not None:
                raise ProtocolShapeError(
                    "passed DiagnoseResult requires diagnostic_payload=None"
                )
            return

        if status == "failed":
            if self.matched_count != 0:
                raise ProtocolShapeError("failed DiagnoseResult requires matched_count == 0")
            if self.matched_binding is not None:
                raise ProtocolShapeError("failed DiagnoseResult requires matched_binding=None")
            if self.failure_kind is None:
                raise ProtocolShapeError("failed DiagnoseResult requires failure_kind")
            if self.failure_kind == "no_candidate":
                if self.diagnostic_payload is not None:
                    raise ProtocolShapeError(
                        "failed DiagnoseResult with failure_kind='no_candidate' "
                        "requires diagnostic_payload=None"
                    )
            else:  # atom_localized
                if not isinstance(self.diagnostic_payload, DiagnoseAtomLocator):
                    raise ProtocolShapeError(
                        "failed DiagnoseResult with failure_kind='atom_localized' "
                        "requires diagnostic_payload"
                    )
            return

        # unsupported / invalid_request
        if self.matched_count is not None:
            raise ProtocolShapeError(f"{status} DiagnoseResult requires matched_count=None")
        if self.matched_binding is not None:
            raise ProtocolShapeError(f"{status} DiagnoseResult requires matched_binding=None")
        if self.failure_kind is not None:
            raise ProtocolShapeError(f"{status} DiagnoseResult requires failure_kind=None")
        if self.diagnostic_payload is not None:
            raise ProtocolShapeError(
                f"{status} DiagnoseResult requires diagnostic_payload=None"
            )
        if not self.errors:
            raise ProtocolShapeError(f"{status} DiagnoseResult requires errors")


__all__ = [
    "DiagnoseAtomLocator",
    "DiagnoseEngine",
    "DiagnoseFailureKind",
    "DiagnoseRequest",
    "DiagnoseResult",
    "DiagnoseStatus",
]
