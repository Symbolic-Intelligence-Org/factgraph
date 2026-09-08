from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Literal, TypeAlias

from .common import (
    ErrorDTO,
    JSONValue,
    ProtocolShapeError,
    WarningDTO,
    _require_bool,
    _require_literal,
    _require_non_empty_str,
    _validate_json_mapping,
    _validate_json_value,
    _validate_tuple_items,
)
from .entity_read import FieldValue, _validate_field_value
from .schema_runtime import EntityRef, EntitySelector, FieldPath

WriteValue: TypeAlias = JSONValue | bytes | EntitySelector | EntityRef


def _validate_write_value(value: Any, *, field_name: str) -> None:
    if isinstance(value, (EntitySelector, EntityRef)):
        return
    if isinstance(value, bytes):
        return
    _validate_json_value(value, field_name=field_name)


@dataclass(frozen=True)
class FieldMutation:
    op: Literal["set", "add", "retract"]
    field: FieldPath
    value: WriteValue | None = None
    assertion_id: str | None = None
    meta: dict[str, JSONValue] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        op = _require_literal(self.op, field_name="op", allowed=("set", "add", "retract"))
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError("field must be FieldPath")
        if op in {"set", "add"}:
            if self.value is None:
                raise ProtocolShapeError(f"value is required when op={op!r}")
            if self.assertion_id is not None:
                raise ProtocolShapeError(f"assertion_id must be omitted when op={op!r}")
            _validate_write_value(self.value, field_name="value")
        else:
            if self.value is not None:
                raise ProtocolShapeError("value must be omitted when op='retract'")
            _require_non_empty_str(self.assertion_id, field_name="assertion_id")
        object.__setattr__(self, "meta", _validate_json_mapping(self.meta, field_name="meta"))


@dataclass(frozen=True)
class EntityWriteCommand:
    target: EntitySelector
    mutations: tuple[FieldMutation, ...] = ()
    create_if_missing: bool = False
    include_dependencies: bool = True
    command_meta: dict[str, JSONValue] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, EntitySelector):
            raise ProtocolShapeError("target must be EntitySelector")
        _validate_tuple_items(self.mutations, field_name="mutations", item_type=FieldMutation)
        for idx, mutation in enumerate(self.mutations):
            if mutation.field.entity_type != self.target.entity_type:
                raise ProtocolShapeError(
                    f"mutations[{idx}].field.entity_type must match target.entity_type={self.target.entity_type!r}"
                )
        _require_bool(self.create_if_missing, field_name="create_if_missing")
        _require_bool(self.include_dependencies, field_name="include_dependencies")
        object.__setattr__(self, "command_meta", _validate_json_mapping(self.command_meta, field_name="command_meta"))


@dataclass(frozen=True)
class PlannedOpDTO:
    op: Literal["record_exists", "set", "add", "retract"]
    target: EntityRef
    field: FieldPath | None = None
    value: FieldValue | None = None
    assertion_id: str | None = None
    meta: dict[str, JSONValue] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        op = _require_literal(self.op, field_name="op", allowed=("record_exists", "set", "add", "retract"))
        if not isinstance(self.target, EntityRef):
            raise ProtocolShapeError("target must be EntityRef")
        if op == "record_exists":
            if self.field is not None or self.value is not None or self.assertion_id is not None:
                raise ProtocolShapeError("record_exists must not carry field, value, or assertion_id")
        elif op in {"set", "add"}:
            if not isinstance(self.field, FieldPath):
                raise ProtocolShapeError(f"field is required when op={op!r}")
            if self.field.entity_type != self.target.entity_type:
                raise ProtocolShapeError(f"field.entity_type must match target.entity_type={self.target.entity_type!r}")
            if self.value is None:
                raise ProtocolShapeError(f"value is required when op={op!r}")
            _validate_field_value(self.value, field_name="value")
            if self.assertion_id is not None:
                raise ProtocolShapeError(f"assertion_id must be omitted when op={op!r}")
        else:
            if not isinstance(self.field, FieldPath):
                raise ProtocolShapeError("field is required when op='retract'")
            if self.field.entity_type != self.target.entity_type:
                raise ProtocolShapeError(f"field.entity_type must match target.entity_type={self.target.entity_type!r}")
            _require_non_empty_str(self.assertion_id, field_name="assertion_id")
            if self.value is not None:
                raise ProtocolShapeError("value must be omitted when op='retract'")
        object.__setattr__(self, "meta", _validate_json_mapping(self.meta, field_name="meta"))


@dataclass(frozen=True)
class EntityWritePlan:
    command: EntityWriteCommand
    resolved_target: EntityRef | None = None
    resolved_dependencies: tuple[EntityRef, ...] = ()
    planned_ops: tuple[PlannedOpDTO, ...] = ()
    can_apply: bool = False
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.command, EntityWriteCommand):
            raise ProtocolShapeError("command must be EntityWriteCommand")
        if self.resolved_target is not None:
            if not isinstance(self.resolved_target, EntityRef):
                raise ProtocolShapeError("resolved_target must be EntityRef when provided")
            if self.resolved_target.entity_type != self.command.target.entity_type:
                raise ProtocolShapeError(
                    f"resolved_target.entity_type must match command.target.entity_type={self.command.target.entity_type!r}"
                )
        _validate_tuple_items(self.resolved_dependencies, field_name="resolved_dependencies", item_type=EntityRef)
        _validate_tuple_items(self.planned_ops, field_name="planned_ops", item_type=PlannedOpDTO)
        _require_bool(self.can_apply, field_name="can_apply")
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)
        if self.can_apply and self.errors:
            raise ProtocolShapeError("errors must be empty when can_apply=True")


@dataclass(frozen=True)
class AppliedOpResultDTO:
    op_index: int
    status: Literal["applied", "skipped", "failed"]
    assertion_id: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.op_index, bool) or not isinstance(self.op_index, int) or self.op_index < 0:
            raise ProtocolShapeError("op_index must be non-negative int")
        _require_literal(self.status, field_name="status", allowed=("applied", "skipped", "failed"))
        if self.assertion_id is not None:
            _require_non_empty_str(self.assertion_id, field_name="assertion_id")


@dataclass(frozen=True)
class EntityWriteResult:
    resolved_target: EntityRef | None = None
    applied: tuple[AppliedOpResultDTO, ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if self.resolved_target is not None and not isinstance(self.resolved_target, EntityRef):
            raise ProtocolShapeError("resolved_target must be EntityRef when provided")
        _validate_tuple_items(self.applied, field_name="applied", item_type=AppliedOpResultDTO)
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)


# ---------- Slice 3a Step 2: fg.entities.create application protocol DTOs ----------


@dataclass(frozen=True)
class EntityCreateCommand:
    """Entity-create command — eager emission entry point per ADR-IC §4.2.

    Carries the **complete identity bundle**(per ADR-IC §4.2.1 emission input
    contract;Layer 2 fields API is NEVER an emission path)。 The SDK shell
    normalizes user-facing kwargs into this DTO and the application layer
    derives Identity Claims + ``:exists`` Claim via the shipped
    ``_materialization_ops`` path。
    """

    target: EntitySelector
    command_meta: dict[str, JSONValue] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, EntitySelector):
            raise ProtocolShapeError("target must be EntitySelector")
        if not self.target.identity:
            raise ProtocolShapeError(
                "EntityCreateCommand.target.identity must be non-empty "
                "(complete identity bundle required per ADR-IC §4.2.1)"
            )
        object.__setattr__(
            self,
            "command_meta",
            _validate_json_mapping(self.command_meta, field_name="command_meta"),
        )


@dataclass(frozen=True)
class EntityCreatePlan:
    """Planned eager-emission ops for ``fg.entities.create``."""

    command: EntityCreateCommand
    resolved_target: EntityRef | None = None
    planned_ops: tuple[PlannedOpDTO, ...] = ()
    can_apply: bool = False
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.command, EntityCreateCommand):
            raise ProtocolShapeError("command must be EntityCreateCommand")
        if self.resolved_target is not None:
            if not isinstance(self.resolved_target, EntityRef):
                raise ProtocolShapeError(
                    "resolved_target must be EntityRef when provided"
                )
            if self.resolved_target.entity_type != self.command.target.entity_type:
                raise ProtocolShapeError(
                    "resolved_target.entity_type must match "
                    f"command.target.entity_type={self.command.target.entity_type!r}"
                )
        _validate_tuple_items(
            self.planned_ops, field_name="planned_ops", item_type=PlannedOpDTO
        )
        _require_bool(self.can_apply, field_name="can_apply")
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)
        if self.can_apply and self.errors:
            raise ProtocolShapeError("errors must be empty when can_apply=True")


@dataclass(frozen=True)
class EntityCreateResult:
    """Result of applying an ``EntityCreatePlan`` —  atomic emission outcome."""

    resolved_target: EntityRef | None = None
    applied: tuple[AppliedOpResultDTO, ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if self.resolved_target is not None and not isinstance(self.resolved_target, EntityRef):
            raise ProtocolShapeError(
                "resolved_target must be EntityRef when provided"
            )
        _validate_tuple_items(
            self.applied, field_name="applied", item_type=AppliedOpResultDTO
        )
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)


# ---------- Slice 3a Step 3: fg.entities.delete whole-entity revoke DTOs ----------


@dataclass(frozen=True)
class EntityDeleteCommand:
    """Whole-entity revoke command per ADR-IC §4.1 强制点 3 + Slice 3a §5.4。

    Identity Claims are immutable anchors(INV-7c)。``fg.entities.delete`` is
    the **唯一合法整批撤销 path** — implemented in the application layer as a
    path-bound private executor(per blueprint SF3 P1 amend:bypass of Slice 2
    retract guard is **structural via function isolation**,NOT a metadata
    marker;see ``_apply_entity_delete_retract`` private helper)。

    The SDK shell normalizes both PF-S2 discriminated signature forms into a
    single ``EntityDeleteCommand``:

    - Form A:``fg.entities.delete(e_ref: str, *, meta=None)``
    - Form B:``fg.entities.delete(EntityCls, *, meta=None, **identity)``

    Either form normalizes to ``EntitySelector(entity_type, identity_dict,
    encoded_ref=<e_ref>)`` — ``encoded_ref`` is **required** by this command
    DTO so the planner can directly enumerate Active Claims under that e_ref。
    """

    target: EntitySelector
    command_meta: dict[str, JSONValue] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, EntitySelector):
            raise ProtocolShapeError("target must be EntitySelector")
        if not self.target.encoded_ref:
            raise ProtocolShapeError(
                "EntityDeleteCommand.target.encoded_ref is required "
                "(SDK normalizes both PF-S2 forms into encoded_ref-bearing selector)"
            )
        object.__setattr__(
            self,
            "command_meta",
            _validate_json_mapping(self.command_meta, field_name="command_meta"),
        )


@dataclass(frozen=True)
class EntityDeletePlan:
    """Planned whole-entity retract ops for ``fg.entities.delete``.

    Each ``planned_retracts`` element is a ``PlannedOpDTO(op="retract", ...)``
    carrying an Active Claim asrt_id under the target e_ref(Identity Claims +
    ``:exists`` Claim + Field Claims)。 The executor(``apply_delete_plan``)
    invokes the application-private ``_apply_entity_delete_retract`` helper
    directly — NEVER routing through the generic ``_apply_op`` dispatcher。
    This is the path-bound guard-bypass per SF3 P1 amend(2026-05-30):any
    caller that builds a ``PlannedOpDTO(op="retract")`` and goes through
    ``_apply_op`` still hits ``check_retract_allowed``,so generic
    application-level callers cannot forge bypass。
    """

    command: EntityDeleteCommand
    resolved_target: EntityRef | None = None
    planned_retracts: tuple[PlannedOpDTO, ...] = ()
    can_apply: bool = False
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.command, EntityDeleteCommand):
            raise ProtocolShapeError("command must be EntityDeleteCommand")
        if self.resolved_target is not None:
            if not isinstance(self.resolved_target, EntityRef):
                raise ProtocolShapeError(
                    "resolved_target must be EntityRef when provided"
                )
            if self.resolved_target.entity_type != self.command.target.entity_type:
                raise ProtocolShapeError(
                    "resolved_target.entity_type must match "
                    f"command.target.entity_type={self.command.target.entity_type!r}"
                )
        _validate_tuple_items(
            self.planned_retracts,
            field_name="planned_retracts",
            item_type=PlannedOpDTO,
        )
        for idx, op in enumerate(self.planned_retracts):
            if op.op != "retract":
                raise ProtocolShapeError(
                    f"planned_retracts[{idx}].op must be 'retract'; got {op.op!r}"
                )
        _require_bool(self.can_apply, field_name="can_apply")
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)
        if self.can_apply and self.errors:
            raise ProtocolShapeError("errors must be empty when can_apply=True")


@dataclass(frozen=True)
class EntityDeleteResult:
    """Result of applying an ``EntityDeletePlan``."""

    resolved_target: EntityRef | None = None
    applied: tuple[AppliedOpResultDTO, ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if self.resolved_target is not None and not isinstance(self.resolved_target, EntityRef):
            raise ProtocolShapeError(
                "resolved_target must be EntityRef when provided"
            )
        _validate_tuple_items(
            self.applied, field_name="applied", item_type=AppliedOpResultDTO
        )
        _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO)
        _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO)


__all__ = [
    "AppliedOpResultDTO",
    "EntityCreateCommand",
    "EntityCreatePlan",
    "EntityCreateResult",
    "EntityDeleteCommand",
    "EntityDeletePlan",
    "EntityDeleteResult",
    "EntityWriteCommand",
    "EntityWritePlan",
    "EntityWriteResult",
    "FieldMutation",
    "PlannedOpDTO",
    "WriteValue",
]
