"""Ergonomic application-layer helpers for shipped capability surfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from kernel.core.store import Store
from kernel.core.store._support import BindingItems, normalize_binding_items
from kernel.core.view.projector import project_view_facts, project_view_facts_with_witness

from .protocol import (
    CompiledDerivationPlan,
    EntityRef,
    EvaluationOverlay,
    FactOverlayAction,
    FactRemoveAction,
    FactValueOverride,
    FieldPath,
)
from .schema_runtime import (
    SchemaIndex,
    entity_type_from_ref,
    field_predicate,
    field_value_type,
)


class CapabilityHelperError(ValueError):
    """Raised when an ergonomic helper cannot build a valid capability input."""


def build_fact_value_override(
    store: Store,
    index: SchemaIndex,
    *,
    e_ref: str,
    field: FieldPath,
    new_value: Any,
    note: str | None = None,
) -> FactValueOverride:
    """Build a Fact Overlay value override from a current active field fact."""

    if not isinstance(store, Store):
        raise CapabilityHelperError("store must be Store")
    if not isinstance(field, FieldPath):
        raise CapabilityHelperError("field must be FieldPath")
    if not isinstance(e_ref, str) or not e_ref:
        raise CapabilityHelperError("e_ref must be non-empty str")

    entity_type = entity_type_from_ref(e_ref)
    if entity_type is None:
        raise CapabilityHelperError("e_ref must be an encoded idref_v1 entity reference")
    if entity_type != field.entity_type:
        raise CapabilityHelperError(
            f"field entity_type {field.entity_type!r} does not match e_ref entity_type {entity_type!r}"
        )

    field_type = field_value_type(index, field.entity_type, field.field_name)
    if field_type.value_kind != "scalar":
        raise CapabilityHelperError("build_fact_value_override supports scalar fields only")
    if field_type.cardinality != "single":
        raise CapabilityHelperError("build_fact_value_override supports single fields only")

    pred_info = field_predicate(index, field.entity_type, field.field_name)
    projected = project_view_facts_with_witness(store.ledger, store.schema_ir)
    matches = [
        row
        for row in projected.get(pred_info.pred_id, [])
        if row.fact_tuple and row.fact_tuple[0] == e_ref
    ]
    if not matches:
        raise CapabilityHelperError(
            f"no active projected fact for {field.entity_type}.{field.field_name}"
        )
    if len(matches) > 1:
        raise CapabilityHelperError(
            f"multiple active projected facts for {field.entity_type}.{field.field_name}"
        )

    current = matches[0]
    if len(current.fact_tuple) != 2:
        raise CapabilityHelperError("field fact must have exactly one value term")

    normalized_value = _normalize_scalar_value(
        field_type.scalar_domain,
        new_value,
        field=field,
    )
    return FactValueOverride(
        asrt_id=current.asrt_id,
        pred_id=pred_info.pred_id,
        e_ref=e_ref,
        old_fact_tuple=current.fact_tuple,
        new_fact_tuple=(e_ref, normalized_value),
        note=note,
    )


def build_fact_remove_action(
    store: Store,
    index: SchemaIndex,
    *,
    e_ref: str,
    field: FieldPath,
    current_value: Any | None = None,
    note: str | None = None,
) -> FactRemoveAction:
    """Build a Fact Overlay remove action from a current active field fact."""

    if not isinstance(store, Store):
        raise CapabilityHelperError("store must be Store")
    if not isinstance(field, FieldPath):
        raise CapabilityHelperError("field must be FieldPath")
    if not isinstance(e_ref, str) or not e_ref:
        raise CapabilityHelperError("e_ref must be non-empty str")

    entity_type = entity_type_from_ref(e_ref)
    if entity_type is None:
        raise CapabilityHelperError("e_ref must be an encoded idref_v1 entity reference")
    if entity_type != field.entity_type:
        raise CapabilityHelperError(
            f"field entity_type {field.entity_type!r} does not match e_ref entity_type {entity_type!r}"
        )

    field_type = field_value_type(index, field.entity_type, field.field_name)
    if field_type.value_kind != "scalar":
        raise CapabilityHelperError("build_fact_remove_action supports scalar fields only")
    normalized_current = None
    if current_value is not None:
        normalized_current = _normalize_scalar_value(
            field_type.scalar_domain,
            current_value,
            field=field,
        )

    pred_info = field_predicate(index, field.entity_type, field.field_name)
    projected = project_view_facts_with_witness(store.ledger, store.schema_ir)
    matches = []
    for row in projected.get(pred_info.pred_id, []):
        if not row.fact_tuple or row.fact_tuple[0] != e_ref:
            continue
        if len(row.fact_tuple) != 2:
            raise CapabilityHelperError("field fact must have exactly one value term")
        if normalized_current is not None and row.fact_tuple[1] != normalized_current:
            continue
        matches.append(row)

    if not matches:
        raise CapabilityHelperError(
            f"no matching projected fact for {field.entity_type}.{field.field_name}"
        )
    if len(matches) > 1:
        raise CapabilityHelperError(
            f"multiple matching projected facts for {field.entity_type}.{field.field_name}"
        )

    current = matches[0]
    return FactRemoveAction(
        asrt_id=current.asrt_id,
        pred_id=pred_info.pred_id,
        e_ref=e_ref,
        old_fact_tuple=current.fact_tuple,
        note=note,
    )


def build_evaluation_overlay(*actions: FactOverlayAction) -> EvaluationOverlay:
    """Build an EvaluationOverlay from fact overlay actions."""

    if not actions:
        raise CapabilityHelperError("build_evaluation_overlay requires at least one action")
    return EvaluationOverlay(fact_actions=actions)


def build_why_not_candidate_universe(
    plan: CompiledDerivationPlan,
    candidates: Sequence[Mapping[str, Any] | Sequence[Any]],
) -> tuple[BindingItems, ...]:
    """Normalize candidate rows against the plan's single head variable order."""

    if not isinstance(plan, CompiledDerivationPlan):
        raise CapabilityHelperError("plan must be CompiledDerivationPlan")
    if len(plan.heads) != 1:
        raise CapabilityHelperError("plan must contain exactly one head")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise CapabilityHelperError("candidates must be a sequence of rows")

    head_vars = plan.heads[0].head_var_names
    universe: list[BindingItems] = []
    for idx, row in enumerate(candidates):
        values = _candidate_values(row, head_vars=head_vars, row_index=idx)
        universe.append(normalize_binding_items(tuple(zip(head_vars, values, strict=True))))
    return tuple(universe)


def build_frontier_view_facts(store: Store) -> dict[str, list[tuple[Any, ...]]]:
    """Project a Store into the view_facts shape expected by native frontier."""

    if not isinstance(store, Store):
        raise CapabilityHelperError("store must be Store")
    return project_view_facts(store.ledger, store.schema_ir)


def _candidate_values(
    row: Mapping[str, Any] | Sequence[Any],
    *,
    head_vars: tuple[str, ...],
    row_index: int,
) -> tuple[Any, ...]:
    if isinstance(row, Mapping):
        missing = [name for name in head_vars if name not in row]
        if missing:
            raise CapabilityHelperError(
                f"candidate row {row_index} missing head variables: {missing}"
            )
        return tuple(row[name] for name in head_vars)

    if isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
        if len(row) != len(head_vars):
            raise CapabilityHelperError(
                f"candidate row {row_index} must have {len(head_vars)} values"
            )
        return tuple(row)

    raise CapabilityHelperError(
        f"candidate row {row_index} must be mapping or non-string sequence"
    )


def _normalize_scalar_value(
    scalar_domain: str | None,
    value: Any,
    *,
    field: FieldPath,
) -> Any:
    field_name = f"{field.entity_type}.{field.field_name}"
    if isinstance(value, EntityRef):
        raise CapabilityHelperError(f"{field_name} expects scalar value")
    if scalar_domain == "string":
        if not isinstance(value, str):
            raise CapabilityHelperError(f"{field_name} expects string value")
        return value
    if scalar_domain == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise CapabilityHelperError(f"{field_name} expects int value")
        return value
    if scalar_domain == "bool":
        if not isinstance(value, bool):
            raise CapabilityHelperError(f"{field_name} expects bool value")
        return value
    if scalar_domain == "float64":
        if isinstance(value, bool) or not isinstance(value, (float, str)):
            raise CapabilityHelperError(f"{field_name} expects float64 value")
        if isinstance(value, str) and not _is_float64_hex(value):
            raise CapabilityHelperError(f"{field_name} expects float or canonical float64 hex string")
        return value
    if scalar_domain == "time":
        if isinstance(value, bool) or not isinstance(value, int):
            raise CapabilityHelperError(f"{field_name} expects epoch-nanos int value")
        return value
    if scalar_domain == "uuid":
        if not isinstance(value, str) or not value:
            raise CapabilityHelperError(f"{field_name} expects uuid string value")
        return value.lower()
    raise CapabilityHelperError(f"{field_name} uses unsupported field domain: {scalar_domain!r}")


def _is_float64_hex(value: str) -> bool:
    if len(value) != 18 or not value.startswith("0x"):
        return False
    return all(char in "0123456789abcdef" for char in value[2:])


__all__ = [
    "CapabilityHelperError",
    "build_evaluation_overlay",
    "build_fact_remove_action",
    "build_fact_value_override",
    "build_frontier_view_facts",
    "build_why_not_candidate_universe",
]
