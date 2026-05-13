"""Application-layer query runtime executor.

Commit 1 scope: entity-slot return + scalar field return only.
Aggregate / advanced row format are intentionally not implemented — unsupported
return slots raise QueryRuntimeError("QUERY_UNSUPPORTED_SLOT") rather than
silently degrading.

Commit 2a parity:
- Slot-level expected ``entity_type`` enables on_type_mismatch policy enforcement
- on_missing / on_type_mismatch literals support {"error", "skip", "null"}
- entity_view errors during hydrate are translated through the configured policies
"""
from __future__ import annotations

from typing import Any

from factpy.core.rules.ruleref_substrate import evaluate_native_where
from factpy.core.store.runtime import Store
from factpy.core.view.projector import project_view_facts

from .entity_view import EntityViewError, hydrate_entity
from .protocol import (
    EntitySnapshotDTO,
    ErrorDTO,
    WarningDTO,
)
from .protocol.query import (
    QueryReturnContract,
    QueryReturnSlot,
    QueryRowValue,
    QueryRuntimeRequest,
    QueryRuntimeResponse,
)
from .schema_runtime import SchemaIndex, SchemaResolutionError


class QueryRuntimeError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        path: tuple[str, ...] = (),
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = tuple(path)
        self.details = dict(details or {})

    def to_error_dto(self) -> ErrorDTO:
        return ErrorDTO(
            code=self.code,
            message=str(self),
            path=self.path,
            details=self.details,
        )


def execute_query(
    request: QueryRuntimeRequest,
    *,
    store: Store,
    index: SchemaIndex,
    registry: Any | None = None,
) -> QueryRuntimeResponse:
    """Execute a runtime-normalized query against the given store.

    The where_ir is passed through to factpy.core.rules.ruleref_substrate.evaluate_native_where;
    SDK adapters or future neutral authoring lowerers are responsible for producing
    a runtime-normalized where_ir from authoring DSL.

    Return slots are resolved per row:
    - kind="entity": var binding -> EntitySnapshotDTO via hydrate_entity, with optional
      slot.entity_type type-mismatch enforcement
    - kind="scalar": var binding -> FieldValue (literal / EntityRef pass-through)
    - other kinds: raises QueryRuntimeError(code="QUERY_UNSUPPORTED_SLOT")
    """
    view_facts = project_view_facts(store.ledger, store.schema_ir)
    bindings = evaluate_native_where(view_facts, request.where_ir, registry=registry).bindings

    rows: list[dict[str, QueryRowValue]] = []
    errors: list[ErrorDTO] = []
    warnings: list[WarningDTO] = []

    for binding in bindings:
        row, row_error = _build_row(
            binding,
            request.return_contract,
            store=store,
            index=index,
            request=request,
        )
        if row_error is not None:
            errors.append(row_error)
            break
        if row is not None:
            rows.append(row)

    return QueryRuntimeResponse(
        rows=tuple(rows),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _build_row(
    binding: dict[str, Any],
    return_contract: QueryReturnContract,
    *,
    store: Store,
    index: SchemaIndex,
    request: QueryRuntimeRequest,
) -> tuple[dict[str, QueryRowValue] | None, ErrorDTO | None]:
    row: dict[str, QueryRowValue] = {}
    skip_row = False
    for slot in return_contract.slots:
        try:
            resolved, outcome = _resolve_slot(
                slot,
                binding,
                store=store,
                index=index,
                request=request,
            )
        except QueryRuntimeError as exc:
            return None, exc.to_error_dto()

        if outcome == "ok":
            row[slot.alias] = resolved
            continue

        policy = request.on_type_mismatch if outcome == "type_mismatch" else request.on_missing
        decision_path = ("return_contract", "slots", slot.alias)
        if policy == "error":
            error_code = (
                "QUERY_TYPE_MISMATCH" if outcome == "type_mismatch" else "QUERY_MISSING_BINDING"
            )
            message = (
                f"slot {slot.alias!r} type mismatch (expected entity_type={slot.entity_type!r})"
                if outcome == "type_mismatch"
                else f"slot {slot.alias!r} missing binding for var {slot.var!r}"
            )
            details: dict[str, Any] = {"var": slot.var}
            if outcome == "type_mismatch":
                details["expected_entity_type"] = slot.entity_type
            return None, ErrorDTO(
                code=error_code,
                message=message,
                path=decision_path,
                details=details,
            )
        if policy == "skip":
            skip_row = True
            break
        # policy == "null"
        row[slot.alias] = None

    if skip_row:
        return None, None
    return row, None


def _resolve_slot(
    slot: QueryReturnSlot,
    binding: dict[str, Any],
    *,
    store: Store,
    index: SchemaIndex,
    request: QueryRuntimeRequest,
) -> tuple[QueryRowValue, str]:
    """Return (resolved_value, outcome) where outcome ∈ {"ok", "missing", "type_mismatch"}."""
    if slot.kind == "entity":
        return _resolve_entity_slot(slot, binding, store=store, index=index)
    if slot.kind == "scalar":
        return _resolve_scalar_slot(slot, binding)
    raise QueryRuntimeError(
        f"unsupported return slot kind: {slot.kind!r}",
        code="QUERY_UNSUPPORTED_SLOT",
        path=("return_contract", "slots", slot.alias),
        details={"kind": slot.kind},
    )


def _resolve_entity_slot(
    slot: QueryReturnSlot,
    binding: dict[str, Any],
    *,
    store: Store,
    index: SchemaIndex,
) -> tuple[EntitySnapshotDTO | None, str]:
    e_ref_value = binding.get(slot.var)
    if e_ref_value is None:
        return None, "missing"
    if not isinstance(e_ref_value, str):
        return None, "type_mismatch"
    if slot.entity_type is not None:
        ref_entity_type = _entity_type_from_ref(e_ref_value)
        if ref_entity_type is None or ref_entity_type != slot.entity_type:
            return None, "type_mismatch"
    try:
        snapshot = hydrate_entity(
            e_ref=e_ref_value,
            store=store,
            index=index,
            include_assertions=False,
            include_history=False,
        )
    except (EntityViewError, SchemaResolutionError):
        return None, "missing"
    if snapshot is None:
        return None, "missing"
    return snapshot, "ok"


def _resolve_scalar_slot(
    slot: QueryReturnSlot,
    binding: dict[str, Any],
) -> tuple[QueryRowValue, str]:
    value = binding.get(slot.var)
    if value is None:
        return None, "missing"
    return value, "ok"


def _entity_type_from_ref(value: str) -> str | None:
    if not value.startswith("idref_v1:"):
        return None
    parts = value.split(":", 2)
    if len(parts) != 3:
        return None
    _, entity_type, digest = parts
    if not entity_type or not digest:
        return None
    return entity_type


__all__ = [
    "QueryRuntimeError",
    "execute_query",
]
