"""Application-layer query runtime executor.

Commit 1 scope: entity-slot return + scalar field return only.
Aggregate / advanced row format are intentionally not implemented — unsupported
return slots raise QueryRuntimeError("QUERY_UNSUPPORTED_SLOT") rather than
silently degrading.
"""
from __future__ import annotations

from typing import Any

from kernel.core.rules.ruleref_substrate import evaluate_native_where
from kernel.core.store.runtime import Store
from kernel.core.view.projector import project_view_facts

from .entity_view import hydrate_entity
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
from .schema_runtime import SchemaIndex


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

    The where_ir is passed through to kernel.core.rules.ruleref_substrate.evaluate_native_where;
    SDK adapters or future neutral authoring lowerers are responsible for producing
    a runtime-normalized where_ir from authoring DSL.

    Return slots are resolved per row:
    - kind="entity": var binding -> EntitySnapshotDTO via hydrate_entity
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
            resolved, missing = _resolve_slot(
                slot,
                binding,
                store=store,
                index=index,
                request=request,
            )
        except QueryRuntimeError as exc:
            return None, exc.to_error_dto()
        if missing:
            if request.on_missing == "error":
                return None, ErrorDTO(
                    code="QUERY_MISSING_BINDING",
                    message=f"binding missing for var {slot.var!r} in slot {slot.alias!r}",
                    path=("return_contract", "slots", slot.alias),
                    details={"var": slot.var},
                )
            if request.on_missing == "skip":
                skip_row = True
                break
            # include_null
            row[slot.alias] = None
            continue
        row[slot.alias] = resolved
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
) -> tuple[QueryRowValue, bool]:
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
) -> tuple[EntitySnapshotDTO | None, bool]:
    e_ref_value = binding.get(slot.var)
    if e_ref_value is None:
        return None, True
    snapshot = hydrate_entity(
        e_ref=str(e_ref_value),
        store=store,
        index=index,
        include_assertions=False,
        include_history=False,
    )
    if snapshot is None:
        return None, True
    return snapshot, False


def _resolve_scalar_slot(
    slot: QueryReturnSlot,
    binding: dict[str, Any],
) -> tuple[QueryRowValue, bool]:
    value = binding.get(slot.var)
    if value is None:
        return None, True
    return value, False


__all__ = [
    "QueryRuntimeError",
    "execute_query",
]
