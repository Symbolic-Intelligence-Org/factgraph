"""Fact Overlay protocol DTOs.

Overlay Check is a Sibling application capability, so it redeclares its status
and engine literals locally instead of importing Check's protocol types. The
DTOs carry only caller intent; runtime dependencies such as ``store`` and
``registry`` remain side-channel kwargs to the runtime entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from factgraph.core.store._support import BindingItems, normalize_binding_items

from .common import (
    ErrorDTO,
    ProtocolShapeError,
    WarningDTO,
    _require_literal,
    _require_non_empty_str,
    _validate_tuple_items,
)
from .derivation import CompiledDerivationPlan

OverlayCheckStatus: TypeAlias = Literal[
    "passed", "failed", "unsupported", "invalid_request"
]
OverlayCheckPhaseStatus: TypeAlias = Literal["passed", "failed"]
OverlayCheckEngine: TypeAlias = Literal["native", "souffle", "problog", "pyreason"]
ConditionPathKind: TypeAlias = Literal[
    "pred_term", "lhs", "rhs", "in_value", "const_operand"
]
AddedConditionKind: TypeAlias = Literal["eq", "ne", "gt", "ge", "lt", "le", "in"]

_OVERLAY_CHECK_STATUSES = ("passed", "failed", "unsupported", "invalid_request")
_OVERLAY_CHECK_PHASE_STATUSES = ("passed", "failed")
_OVERLAY_CHECK_ENGINES = ("native", "souffle", "problog", "pyreason")


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


def _validate_fact_tuple(value: Any, *, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[Any, ...]")
    return value


def _validate_non_negative_int(value: Any, *, field_name: str) -> int:
    if value is None or isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolShapeError(f"{field_name} must be non-negative int")
    return value


def _validate_signed_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolShapeError(f"{field_name} must be int")
    return value


def _validate_optional_non_negative_int(
    value: Any,
    *,
    field_name: str,
) -> int | None:
    if value is None:
        return None
    return _validate_non_negative_int(value, field_name=field_name)


def _validate_binding_items_tuple(
    value: Any, *, field_name: str
) -> tuple[BindingItems, ...]:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[BindingItems, ...]")
    return tuple(
        _validate_binding_items(item, field_name=f"{field_name}[{idx}]")
        for idx, item in enumerate(value)
    )


@dataclass(frozen=True)
class ReplaceFact:
    asrt_id: str
    pred_id: str
    e_ref: str
    old_fact_tuple: tuple[Any, ...]
    new_fact_tuple: tuple[Any, ...]
    note: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.asrt_id, field_name="asrt_id")
        _require_non_empty_str(self.pred_id, field_name="pred_id")
        _require_non_empty_str(self.e_ref, field_name="e_ref")
        _validate_fact_tuple(self.old_fact_tuple, field_name="old_fact_tuple")
        _validate_fact_tuple(self.new_fact_tuple, field_name="new_fact_tuple")
        if self.note is not None and not isinstance(self.note, str):
            raise ProtocolShapeError("note must be str or None")


@dataclass(frozen=True)
class RemoveFact:
    asrt_id: str
    pred_id: str
    e_ref: str
    old_fact_tuple: tuple[Any, ...]
    note: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.asrt_id, field_name="asrt_id")
        _require_non_empty_str(self.pred_id, field_name="pred_id")
        _require_non_empty_str(self.e_ref, field_name="e_ref")
        _validate_fact_tuple(self.old_fact_tuple, field_name="old_fact_tuple")
        if self.note is not None and not isinstance(self.note, str):
            raise ProtocolShapeError("note must be str or None")


FactOverlayAction: TypeAlias = ReplaceFact | RemoveFact


@dataclass(frozen=True)
class RuleDisableAction:
    rule_id: str
    version: str
    case_index: int
    condition_index: int
    note: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.rule_id, field_name="rule_id")
        _require_non_empty_str(self.version, field_name="version")
        _validate_non_negative_int(self.case_index, field_name="case_index")
        _validate_non_negative_int(self.condition_index, field_name="condition_index")
        if self.note is not None and not isinstance(self.note, str):
            raise ProtocolShapeError("note must be str or None")


@dataclass(frozen=True)
class ConditionPath:
    kind: ConditionPathKind
    index: int | None = None

    def __post_init__(self) -> None:
        _require_literal(
            self.kind,
            field_name="kind",
            allowed=("pred_term", "lhs", "rhs", "in_value", "const_operand"),
        )
        index = _validate_optional_non_negative_int(self.index, field_name="index")
        if self.kind in {"pred_term", "in_value"}:
            if index is None:
                raise ProtocolShapeError(f"{self.kind} literal path requires index")
            return
        if index is not None:
            raise ProtocolShapeError(f"{self.kind} literal path requires index=None")


@dataclass(frozen=True)
class RuleLiteralReplaceAction:
    rule_id: str
    version: str
    case_index: int
    condition_index: int
    literal_path: ConditionPath
    old_literal: Any
    new_literal: Any
    note: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.rule_id, field_name="rule_id")
        _require_non_empty_str(self.version, field_name="version")
        _validate_non_negative_int(self.case_index, field_name="case_index")
        _validate_non_negative_int(self.condition_index, field_name="condition_index")
        if not isinstance(self.literal_path, ConditionPath):
            raise ProtocolShapeError("literal_path must be ConditionPath")
        if self.note is not None and not isinstance(self.note, str):
            raise ProtocolShapeError("note must be str or None")


@dataclass(frozen=True)
class AddedCondition:
    atom: tuple[Any, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.atom, tuple) or not self.atom:
            raise ProtocolShapeError("atom must be non-empty tuple")
        if not isinstance(self.atom[0], str):
            raise ProtocolShapeError("atom[0] must be atom kind string")


@dataclass(frozen=True)
class RuleAddConditionAction:
    rule_id: str
    version: str
    case_index: int
    added_atom: AddedCondition
    note: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.rule_id, field_name="rule_id")
        _require_non_empty_str(self.version, field_name="version")
        _validate_non_negative_int(self.case_index, field_name="case_index")
        if not isinstance(self.added_atom, AddedCondition):
            raise ProtocolShapeError("added_atom must be AddedCondition")
        if self.note is not None and not isinstance(self.note, str):
            raise ProtocolShapeError("note must be str or None")


RuleOverlayAction: TypeAlias = (
    RuleDisableAction | RuleLiteralReplaceAction | RuleAddConditionAction
)


def _validate_fact_actions(
    value: Any, *, field_name: str
) -> tuple[FactOverlayAction, ...]:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[FactOverlayAction, ...]")
    for idx, item in enumerate(value):
        if not isinstance(item, (ReplaceFact, RemoveFact)):
            raise ProtocolShapeError(
                f"{field_name}[{idx}] must be ReplaceFact or RemoveFact"
            )
    return value


def _validate_rule_actions(
    value: Any, *, field_name: str
) -> tuple[RuleOverlayAction, ...]:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[RuleOverlayAction, ...]")
    for idx, item in enumerate(value):
        if not isinstance(
            item, (RuleDisableAction, RuleLiteralReplaceAction, RuleAddConditionAction)
        ):
            raise ProtocolShapeError(
                f"{field_name}[{idx}] must be RuleDisableAction, RuleLiteralReplaceAction, or RuleAddConditionAction"
            )
    return value


@dataclass(frozen=True)
class FactOverlay:
    fact_actions: tuple[FactOverlayAction, ...] = ()
    rule_actions: tuple[RuleOverlayAction, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "fact_actions",
            _validate_fact_actions(self.fact_actions, field_name="fact_actions"),
        )
        object.__setattr__(
            self,
            "rule_actions",
            _validate_rule_actions(self.rule_actions, field_name="rule_actions"),
        )


@dataclass(frozen=True)
class FactOverlayCheckRequest:
    plan: CompiledDerivationPlan
    binding: BindingItems
    overlay: tuple[ReplaceFact, ...] | FactOverlay
    engine: OverlayCheckEngine

    def __post_init__(self) -> None:
        if not isinstance(self.plan, CompiledDerivationPlan):
            raise ProtocolShapeError("plan must be CompiledDerivationPlan")
        if len(self.plan.heads) != 1:
            raise ProtocolShapeError(
                "plan must contain exactly one head for FactOverlayCheckRequest"
            )
        object.__setattr__(
            self,
            "binding",
            _validate_binding_items(self.binding, field_name="binding"),
        )
        if isinstance(self.overlay, FactOverlay):
            overlay = self.overlay
        else:
            overlay = _validate_tuple_items(
                self.overlay, field_name="overlay", item_type=ReplaceFact
            )
        object.__setattr__(self, "overlay", overlay)
        _require_literal(self.engine, field_name="engine", allowed=_OVERLAY_CHECK_ENGINES)


@dataclass(frozen=True)
class OverlayCheckPhase:
    status: OverlayCheckPhaseStatus
    matched_count: int
    matched_binding: BindingItems | None

    def __post_init__(self) -> None:
        status = _require_literal(
            self.status, field_name="status", allowed=_OVERLAY_CHECK_PHASE_STATUSES
        )
        _validate_non_negative_int(self.matched_count, field_name="matched_count")
        if self.matched_binding is not None:
            object.__setattr__(
                self,
                "matched_binding",
                _validate_binding_items(self.matched_binding, field_name="matched_binding"),
            )
        if status == "passed":
            if self.matched_count < 1:
                raise ProtocolShapeError("passed OverlayCheckPhase requires matched_count >= 1")
            if self.matched_binding is None:
                raise ProtocolShapeError("passed OverlayCheckPhase requires matched_binding")
            return
        if self.matched_count != 0:
            raise ProtocolShapeError("failed OverlayCheckPhase requires matched_count == 0")
        if self.matched_binding is not None:
            raise ProtocolShapeError("failed OverlayCheckPhase requires matched_binding=None")


@dataclass(frozen=True)
class OverlayCheckDiff:
    status_changed: bool
    matched_count_delta: int
    bindings_added: tuple[BindingItems, ...]
    bindings_removed: tuple[BindingItems, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status_changed, bool):
            raise ProtocolShapeError("status_changed must be bool")
        _validate_signed_int(self.matched_count_delta, field_name="matched_count_delta")
        object.__setattr__(
            self,
            "bindings_added",
            _validate_binding_items_tuple(
                self.bindings_added, field_name="bindings_added"
            ),
        )
        object.__setattr__(
            self,
            "bindings_removed",
            _validate_binding_items_tuple(
                self.bindings_removed, field_name="bindings_removed"
            ),
        )


@dataclass(frozen=True)
class FactOverlayCheckResult:
    status: OverlayCheckStatus
    requested_binding: BindingItems
    before: OverlayCheckPhase | None
    after: OverlayCheckPhase | None
    diff: OverlayCheckDiff | None
    errors: tuple[ErrorDTO, ...] = field(default_factory=tuple)
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        status = _require_literal(
            self.status, field_name="status", allowed=_OVERLAY_CHECK_STATUSES
        )
        object.__setattr__(
            self,
            "requested_binding",
            _validate_binding_items(self.requested_binding, field_name="requested_binding"),
        )
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)

        if self.before is not None and not isinstance(self.before, OverlayCheckPhase):
            raise ProtocolShapeError("before must be OverlayCheckPhase or None")
        if self.after is not None and not isinstance(self.after, OverlayCheckPhase):
            raise ProtocolShapeError("after must be OverlayCheckPhase or None")
        if self.diff is not None and not isinstance(self.diff, OverlayCheckDiff):
            raise ProtocolShapeError("diff must be OverlayCheckDiff or None")

        if status in {"passed", "failed"}:
            if not isinstance(self.before, OverlayCheckPhase):
                raise ProtocolShapeError(f"{status} FactOverlayCheckResult requires before")
            if not isinstance(self.after, OverlayCheckPhase):
                raise ProtocolShapeError(f"{status} FactOverlayCheckResult requires after")
            if not isinstance(self.diff, OverlayCheckDiff):
                raise ProtocolShapeError(f"{status} FactOverlayCheckResult requires diff")
            if self.after.status != status:
                raise ProtocolShapeError(
                    f"{status} FactOverlayCheckResult requires after.status={status!r}"
                )
            if self.errors:
                raise ProtocolShapeError(f"{status} FactOverlayCheckResult requires no errors")
            return

        if self.before is not None:
            raise ProtocolShapeError(f"{status} FactOverlayCheckResult requires before=None")
        if self.after is not None:
            raise ProtocolShapeError(f"{status} FactOverlayCheckResult requires after=None")
        if self.diff is not None:
            raise ProtocolShapeError(f"{status} FactOverlayCheckResult requires diff=None")
        if not self.errors:
            raise ProtocolShapeError(f"{status} FactOverlayCheckResult requires errors")


__all__ = [
    "FactOverlay",
    "FactOverlayAction",
    "FactOverlayCheckRequest",
    "FactOverlayCheckResult",
    "RemoveFact",
    "ReplaceFact",
    "OverlayCheckDiff",
    "OverlayCheckEngine",
    "OverlayCheckPhase",
    "OverlayCheckPhaseStatus",
    "OverlayCheckStatus",
    "RuleAddConditionAction",
    "AddedCondition",
    "AddedConditionKind",
    "RuleDisableAction",
    "ConditionPath",
    "ConditionPathKind",
    "RuleLiteralReplaceAction",
    "RuleOverlayAction",
]
