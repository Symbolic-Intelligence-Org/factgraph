from __future__ import annotations

from typing import Any

from factgraph.core.evidence.write_protocol import add_field, retract_by_asrt, set_field
from factgraph.core.store import Store
from factgraph.core.view.projector import project_view_facts

from .protocol import (
    AppliedOpResultDTO,
    EntityRef,
    EntitySelector,
    EntityWriteCommand,
    EntityWritePlan,
    EntityWriteResult,
    ErrorDTO,
    FieldMutation,
    FieldPath,
    PlannedOpDTO,
    WarningDTO,
    WriteValue,
)
from .schema_runtime import (
    SchemaIndex,
    SchemaResolutionError,
    encode_entity_ref,
    entity_info,
    field_predicate,
    field_value_type,
    resolve_selector,
)
from .retract_guard import RetractGuardError, check_retract_allowed
from .value_validation import FieldValueValidationError, validate_field_value


class EntityWriteError(ValueError):
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

    def to_warning_dto(self) -> WarningDTO:
        return WarningDTO(
            code=self.code,
            message=str(self),
            path=self.path,
            details=self.details,
        )


def plan_write_command(
    command: EntityWriteCommand,
    *,
    store: Store,
    index: SchemaIndex,
) -> EntityWritePlan:
    resolved_target: EntityRef | None = None
    try:
        resolved_target = resolve_selector(command.target, index=index)
        view_facts = project_view_facts(store.ledger, store.schema_ir)
        target_e_ref = _encoded_ref(resolved_target, index=index)
        target_visible = _entity_visible(resolved_target, view_facts=view_facts, index=index)

        planned_ops: list[PlannedOpDTO] = []
        resolved_dependencies: list[EntityRef] = []
        materialized_refs: set[str] = set()

        dependency_plan = _plan_dependencies_and_mutations(
            command,
            resolved_target=resolved_target,
            store=store,
            index=index,
            view_facts=view_facts,
            materialized_refs=materialized_refs,
        )
        resolved_dependencies.extend(dependency_plan["resolved_dependencies"])
        planned_ops.extend(dependency_plan["dependency_ops"])

        if not target_visible:
            if not command.create_if_missing:
                raise EntityWriteError(
                    f"target entity does not exist: {resolved_target.entity_type}",
                    code="ENTITY_NOT_FOUND",
                    path=("target",),
                    details={"entity_type": resolved_target.entity_type, "e_ref": target_e_ref},
                )
            planned_ops.extend(
                _materialization_ops(
                    resolved_target,
                    index=index,
                    meta=dict(command.command_meta),
                    materialized_refs=materialized_refs,
                )
            )

        planned_ops.extend(dependency_plan["mutation_ops"])
        return EntityWritePlan(
            command=command,
            resolved_target=resolved_target,
            resolved_dependencies=tuple(resolved_dependencies),
            planned_ops=tuple(planned_ops),
            can_apply=True,
        )
    except (SchemaResolutionError, EntityWriteError) as exc:
        error = _to_error_dto(exc)
        return EntityWritePlan(
            command=command,
            resolved_target=resolved_target,
            can_apply=False,
            errors=(error,),
        )


def apply_write_plan(
    plan: EntityWritePlan,
    *,
    store: Store,
    index: SchemaIndex,
) -> EntityWriteResult:
    if not plan.can_apply:
        return EntityWriteResult(
            resolved_target=plan.resolved_target,
            errors=plan.errors,
            warnings=plan.warnings,
        )

    applied: list[AppliedOpResultDTO] = []
    for op_index, op in enumerate(plan.planned_ops):
        try:
            assertion_id = _apply_op(op, store=store, index=index)
            applied.append(
                AppliedOpResultDTO(
                    op_index=op_index,
                    status="applied",
                    assertion_id=assertion_id,
                )
            )
        except (SchemaResolutionError, EntityWriteError, Exception) as exc:
            error = _to_error_dto(exc)
            applied.append(AppliedOpResultDTO(op_index=op_index, status="failed"))
            return EntityWriteResult(
                resolved_target=plan.resolved_target,
                applied=tuple(applied),
                errors=(error,),
                warnings=plan.warnings,
            )

    return EntityWriteResult(
        resolved_target=plan.resolved_target,
        applied=tuple(applied),
        warnings=plan.warnings,
    )


def _plan_dependencies_and_mutations(
    command: EntityWriteCommand,
    *,
    resolved_target: EntityRef,
    store: Store,
    index: SchemaIndex,
    view_facts: dict[str, list[tuple[Any, ...]]],
    materialized_refs: set[str],
) -> dict[str, list[Any]]:
    resolved_dependencies: list[EntityRef] = []
    dependency_ops: list[PlannedOpDTO] = []
    mutation_ops: list[PlannedOpDTO] = []
    seen_dependencies: set[str] = set()

    for idx, mutation in enumerate(command.mutations):
        pred_info = field_predicate(index, mutation.field.entity_type, mutation.field.field_name)
        if pred_info.is_identity_field:
            raise EntityWriteError(
                f"identity field mutation is not supported: {mutation.field.entity_type}.{mutation.field.field_name}",
                code="IDENTITY_FIELD_MUTATION_NOT_SUPPORTED",
                path=("mutations", str(idx), "field"),
                details={"entity_type": mutation.field.entity_type, "field_name": mutation.field.field_name},
            )

        effective_meta = _merge_meta(command.command_meta, mutation.meta)
        if mutation.op in {"set", "add"}:
            expected_cardinality = "single" if mutation.op == "set" else "multi"
            if pred_info.cardinality != expected_cardinality:
                raise EntityWriteError(
                    f"op={mutation.op!r} requires cardinality={expected_cardinality!r} field; "
                    f"{mutation.field.entity_type}.{mutation.field.field_name} has cardinality={pred_info.cardinality!r}",
                    code="FIELD_CARDINALITY_MISMATCH",
                    path=("mutations", str(idx), "op"),
                    details={
                        "entity_type": mutation.field.entity_type,
                        "field_name": mutation.field.field_name,
                        "op": mutation.op,
                        "cardinality": pred_info.cardinality,
                    },
                )
            resolved_value = _resolve_mutation_value(
                mutation,
                mutation_index=idx,
                command=command,
                store=store,
                index=index,
                view_facts=view_facts,
                resolved_dependencies=resolved_dependencies,
                seen_dependencies=seen_dependencies,
                dependency_ops=dependency_ops,
                materialized_refs=materialized_refs,
            )
            mutation_ops.append(
                PlannedOpDTO(
                    op=mutation.op,
                    target=resolved_target,
                    field=mutation.field,
                    value=resolved_value,
                    meta=effective_meta,
                )
            )
            continue

        _validate_retract_target(mutation, resolved_target=resolved_target, store=store, index=index, mutation_index=idx)
        mutation_ops.append(
            PlannedOpDTO(
                op="retract",
                target=resolved_target,
                field=mutation.field,
                assertion_id=mutation.assertion_id,
                meta=effective_meta,
            )
        )

    return {
        "resolved_dependencies": resolved_dependencies,
        "dependency_ops": dependency_ops,
        "mutation_ops": mutation_ops,
    }


def _resolve_mutation_value(
    mutation: FieldMutation,
    *,
    mutation_index: int,
    command: EntityWriteCommand,
    store: Store,
    index: SchemaIndex,
    view_facts: dict[str, list[tuple[Any, ...]]],
    resolved_dependencies: list[EntityRef],
    seen_dependencies: set[str],
    dependency_ops: list[PlannedOpDTO],
    materialized_refs: set[str],
) -> Any:
    assert mutation.value is not None
    field_type = field_value_type(index, mutation.field.entity_type, mutation.field.field_name)
    if field_type.value_kind == "entity_ref":
        if not isinstance(mutation.value, (EntitySelector, EntityRef)):
            raise EntityWriteError(
                f"entity_ref field expects EntitySelector or EntityRef: {mutation.field.entity_type}.{mutation.field.field_name}",
                code="FIELD_VALUE_TYPE_MISMATCH",
                path=("mutations", str(mutation_index), "value"),
                details={"entity_type": mutation.field.entity_type, "field_name": mutation.field.field_name},
            )
        dependency_ref = _resolve_dependency_ref(mutation.value, index=index)
        encoded = _encoded_ref(dependency_ref, index=index)
        if encoded not in seen_dependencies:
            seen_dependencies.add(encoded)
            resolved_dependencies.append(dependency_ref)
        dependency_visible = _entity_visible(dependency_ref, view_facts=view_facts, index=index)
        if not dependency_visible:
            if not command.include_dependencies:
                raise EntityWriteError(
                    f"dependency entity does not exist and include_dependencies=False: {dependency_ref.entity_type}",
                    code="DEPENDENCY_NOT_FOUND",
                    path=("mutations", str(mutation_index), "value"),
                    details={"entity_type": dependency_ref.entity_type, "e_ref": encoded},
                )
            dependency_ops.extend(
                _materialization_ops(
                    dependency_ref,
                    index=index,
                    meta=_merge_meta(command.command_meta, mutation.meta),
                    materialized_refs=materialized_refs,
                )
            )
        return dependency_ref

    if isinstance(mutation.value, (EntitySelector, EntityRef)):
        raise EntityWriteError(
            f"scalar field does not accept entity references: {mutation.field.entity_type}.{mutation.field.field_name}",
            code="FIELD_VALUE_TYPE_MISMATCH",
            path=("mutations", str(mutation_index), "value"),
            details={"entity_type": mutation.field.entity_type, "field_name": mutation.field.field_name},
        )
    return _normalize_scalar_field_value(
        field_type.scalar_domain,
        mutation.value,
        mutation=mutation,
        mutation_index=mutation_index,
    )


def _resolve_dependency_ref(value: WriteValue, *, index: SchemaIndex) -> EntityRef:
    if isinstance(value, EntityRef):
        if value.encoded_ref is not None:
            return value
        encoded = encode_entity_ref(value, index=index)
        return EntityRef(entity_type=value.entity_type, identity=value.identity, encoded_ref=encoded)
    if isinstance(value, EntitySelector):
        return resolve_selector(value, index=index)
    raise AssertionError("unreachable")


def _materialization_ops(
    ref: EntityRef,
    *,
    index: SchemaIndex,
    meta: dict[str, Any],
    materialized_refs: set[str],
) -> list[PlannedOpDTO]:
    encoded = _encoded_ref(ref, index=index)
    if encoded in materialized_refs:
        return []
    materialized_refs.add(encoded)

    info = entity_info(index, ref.entity_type)
    ops: list[PlannedOpDTO] = []
    for identity_field in info.identity_fields:
        ops.append(
            PlannedOpDTO(
                op="set",
                target=ref,
                field=FieldPath(entity_type=ref.entity_type, field_name=identity_field.name),
                value=ref.identity[identity_field.name],
                meta=dict(meta),
            )
        )
    ops.append(PlannedOpDTO(op="record_exists", target=ref, meta=dict(meta)))
    return ops


def _validate_retract_target(
    mutation: FieldMutation,
    *,
    resolved_target: EntityRef,
    store: Store,
    index: SchemaIndex,
    mutation_index: int,
) -> None:
    assert mutation.assertion_id is not None
    claim = store.ledger.get_claim(mutation.assertion_id)
    if claim is None:
        raise EntityWriteError(
            f"assertion does not exist: {mutation.assertion_id}",
            code="ASSERTION_NOT_FOUND",
            path=("mutations", str(mutation_index), "assertion_id"),
            details={"assertion_id": mutation.assertion_id},
        )
    pred_info = field_predicate(index, mutation.field.entity_type, mutation.field.field_name)
    if claim.pred_id != pred_info.pred_id or claim.e_ref != _encoded_ref(resolved_target, index=index):
        raise EntityWriteError(
            f"assertion does not belong to target field: {mutation.assertion_id}",
            code="ASSERTION_TARGET_MISMATCH",
            path=("mutations", str(mutation_index), "assertion_id"),
            details={
                "assertion_id": mutation.assertion_id,
                "expected_pred_id": pred_info.pred_id,
                "expected_e_ref": _encoded_ref(resolved_target, index=index),
            },
        )


def _apply_op(
    op: PlannedOpDTO,
    *,
    store: Store,
    index: SchemaIndex,
) -> str | None:
    target_e_ref = _encoded_ref(op.target, index=index)
    if op.op == "record_exists":
        info = entity_info(index, op.target.entity_type)
        return set_field(store.ledger, info.exists_predicate_id, target_e_ref, [], dict(op.meta) if op.meta else None)
    if op.op in {"set", "add"}:
        assert op.field is not None
        pred_info = field_predicate(index, op.field.entity_type, op.field.field_name)
        field_type = field_value_type(index, op.field.entity_type, op.field.field_name)
        assert op.value is not None
        try:
            validate_field_value(op.value, pred_info=pred_info)
        except FieldValueValidationError as exc:
            raise EntityWriteError(
                str(exc),
                code=exc.code,
                path=exc.path,
                details=exc.details,
            ) from exc
        rest_terms = [_rest_term_for_value(op.value, field_type=field_type, index=index)]
        if op.op == "set":
            return set_field(store.ledger, pred_info.pred_id, target_e_ref, rest_terms, dict(op.meta) if op.meta else None)
        return add_field(store.ledger, pred_info.pred_id, target_e_ref, rest_terms, dict(op.meta) if op.meta else None)
    assert op.assertion_id is not None
    # Slice 2 Step 5: application entity_write path leg of three-layer retract guard.
    # check_retract_allowed raises RetractGuardError for INV-7c-protected Identity
    # Claims or :exists Claims (existence-claim transitional guard).
    # Field Claims and unknown asrt pass-through to retract_by_asrt unchanged.
    try:
        check_retract_allowed(
            op.assertion_id,
            ledger=store.ledger,
            schema_index=index,
        )
    except RetractGuardError as guard_exc:
        if guard_exc.classification == "identity":
            message = (
                f"Identity Claim {guard_exc.asrt_id} "
                f"(pred_id={guard_exc.pred_id}) is immutable per INV-7c; "
                "Identity bundle modification requires delete + recreate of the entity. "
                "See ADR-IC §4.1."
            )
        else:  # classification == "exists"
            message = (
                f"<EntityType>:exists Claim {guard_exc.asrt_id} "
                f"(pred_id={guard_exc.pred_id}) cannot be retracted independently; "
                ":exists is co-emitted atomically with Identity Claims (existence-claim "
                "transitional guard). See ADR-IC §4.4."
            )
        raise EntityWriteError(
            message,
            code=guard_exc.code,  # propagated directly, NOT swallowed
            path=("planned_ops", "assertion_id"),
            details={
                "assertion_id": guard_exc.asrt_id,
                "pred_id": guard_exc.pred_id,
                "classification": guard_exc.classification,
            },
        ) from guard_exc
    return retract_by_asrt(store.ledger, op.assertion_id, dict(op.meta) if op.meta else None)


def _rest_term_for_value(
    value: Any,
    *,
    field_type: Any,
    index: SchemaIndex,
) -> tuple[str, Any]:
    if field_type.value_kind == "entity_ref":
        if not isinstance(value, EntityRef):
            raise EntityWriteError(
                "entity_ref planned value must be EntityRef",
                code="INVALID_PLANNED_VALUE",
                path=("planned_ops", "value"),
            )
        return ("entity_ref", _encoded_ref(value, index=index))
    return (str(field_type.scalar_domain), value)


def _normalize_scalar_field_value(
    scalar_domain: str | None,
    value: Any,
    *,
    mutation: FieldMutation,
    mutation_index: int,
) -> Any:
    path = ("mutations", str(mutation_index), "value")
    field_name = f"{mutation.field.entity_type}.{mutation.field.field_name}"
    if scalar_domain == "string":
        if not isinstance(value, str):
            raise EntityWriteError(
                f"{field_name} expects string value",
                code="FIELD_VALUE_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": scalar_domain},
            )
        return value
    if scalar_domain == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise EntityWriteError(
                f"{field_name} expects int value",
                code="FIELD_VALUE_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": scalar_domain},
            )
        return value
    if scalar_domain == "bool":
        if not isinstance(value, bool):
            raise EntityWriteError(
                f"{field_name} expects bool value",
                code="FIELD_VALUE_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": scalar_domain},
            )
        return value
    if scalar_domain == "float64":
        if isinstance(value, bool) or not isinstance(value, (float, str)):
            raise EntityWriteError(
                f"{field_name} expects float64 value",
                code="FIELD_VALUE_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": scalar_domain},
            )
        return value
    if scalar_domain == "time":
        if isinstance(value, bool) or not isinstance(value, int):
            raise EntityWriteError(
                f"{field_name} expects epoch-nanos int value",
                code="FIELD_VALUE_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": scalar_domain},
            )
        return value
    if scalar_domain == "uuid":
        if not isinstance(value, str) or not value:
            raise EntityWriteError(
                f"{field_name} expects uuid string value",
                code="FIELD_VALUE_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": scalar_domain},
            )
        return value.lower()
    if scalar_domain == "bytes":
        raise EntityWriteError(
            f"{field_name} uses unsupported protocol field domain: bytes",
            code="UNSUPPORTED_FIELD_DOMAIN",
            path=path,
            details={"expected_type_domain": scalar_domain},
        )
    raise EntityWriteError(
        f"{field_name} uses unsupported field domain: {scalar_domain!r}",
        code="UNSUPPORTED_FIELD_DOMAIN",
        path=path,
        details={"expected_type_domain": scalar_domain},
    )


def _entity_visible(
    ref: EntityRef,
    *,
    view_facts: dict[str, list[tuple[Any, ...]]],
    index: SchemaIndex,
) -> bool:
    info = entity_info(index, ref.entity_type)
    encoded = _encoded_ref(ref, index=index)
    for row in view_facts.get(info.exists_predicate_id, []):
        if row and row[0] == encoded:
            return True
    for (owner_type, _field_name), pred_info in index.field_predicates.items():
        if owner_type != ref.entity_type:
            continue
        for row in view_facts.get(pred_info.pred_id, []):
            if row and row[0] == encoded:
                return True
    return False


def _encoded_ref(ref: EntityRef, *, index: SchemaIndex) -> str:
    if isinstance(ref.encoded_ref, str) and ref.encoded_ref:
        return ref.encoded_ref
    return encode_entity_ref(ref, index=index)


def _merge_meta(*layers: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for layer in layers:
        if not layer:
            continue
        merged.update(layer)
    return merged


def _to_error_dto(exc: Exception) -> ErrorDTO:
    if isinstance(exc, SchemaResolutionError):
        return exc.to_error_dto()
    if isinstance(exc, EntityWriteError):
        return exc.to_error_dto()
    return ErrorDTO(code="WRITE_APPLY_FAILED", message=str(exc))


__all__ = [
    "EntityWriteError",
    "apply_write_plan",
    "plan_write_command",
]
