"""Resolution of the deliberately narrow Scenario field-substitution v0.

The resolver constructs two immutable, dependency-complete projected relations.
It never mutates the ledger and never delegates to the public FactOverlay API:
that API has assertion-oriented semantics which are not this Scenario contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Any

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms
from factgraph.core.store._evaluate import (
    _NativeEffectiveRelationSnapshot,
    _immutable_effective_relation_copy,
    _native_where_dependency_predicates,
)
from factgraph.core.store._support import ProjectedFact
from factgraph.core.store.runtime import Store
from factgraph.core.view.projector import project_view_facts_with_witness

from .entity_visibility import is_entity_identity_bundle_active
from .evaluation_query_runtime import CompiledEvaluationQueryV0
from .protocol.evaluation_scenario import (
    ScenarioFieldSubstitutionV0,
    ScenarioResolutionV0,
    ScenarioScalarValueV0,
)
from .protocol.schema_runtime import EntityRef
from .schema_runtime import (
    SchemaIndex,
    SchemaResolutionError,
    encode_entity_ref,
    entity_info,
    field_predicate,
    materialize_identity,
)
from .value_validation import FieldValueValidationError, validate_field_value


class ScenarioResolutionError(ValueError):
    """A non-inferential v0 Scenario admission or resolution failure."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedScenarioFieldSubstitutionV0:
    """Internal evaluator-ready relations plus public Scenario metadata."""

    resolution: ScenarioResolutionV0
    baseline_relation: _NativeEffectiveRelationSnapshot
    effective_relation: _NativeEffectiveRelationSnapshot


def resolve_scenario_field_substitution_v0(
    scenario: ScenarioFieldSubstitutionV0,
    *,
    compiled_query: CompiledEvaluationQueryV0,
    materialized_body: Sequence[Any],
    store: Store,
    schema_index: SchemaIndex,
    base_view_digest: str,
) -> ResolvedScenarioFieldSubstitutionV0:
    """Resolve one safe field replacement into immutable evaluator relations."""

    if not isinstance(scenario, ScenarioFieldSubstitutionV0):
        raise ScenarioResolutionError(
            "scenario must be ScenarioFieldSubstitutionV0",
            code="SCENARIO_PROTOCOL_SHAPE",
        )
    if not isinstance(compiled_query, CompiledEvaluationQueryV0):
        raise ScenarioResolutionError(
            "scenario requires a trusted CompiledEvaluationQueryV0",
            code="SCENARIO_QUERY_REQUIRED",
        )
    if not isinstance(schema_index, SchemaIndex) or not isinstance(store, Store):
        raise ScenarioResolutionError(
            "scenario resolution requires trusted Store and SchemaIndex",
            code="SCENARIO_RUNTIME_CONTEXT",
        )

    try:
        identity = materialize_identity(
            scenario.entity.entity_type,
            scenario.entity.identity,
            index=schema_index,
        )
        e_ref = encode_entity_ref(
            EntityRef(scenario.entity.entity_type, identity),
            index=schema_index,
        )
        info = entity_info(schema_index, scenario.entity.entity_type)
        pred_info = field_predicate(
            schema_index,
            scenario.field.entity_type,
            scenario.field.field_name,
        )
    except SchemaResolutionError as exc:
        raise ScenarioResolutionError(
            "scenario entity or field is not available in the active schema",
            code="SCENARIO_SCHEMA_TARGET_INVALID",
        ) from exc

    if scenario.field.entity_type != scenario.entity.entity_type:
        raise ScenarioResolutionError(
            "scenario entity and field types must agree",
            code="SCENARIO_ENTITY_FIELD_MISMATCH",
        )
    if (
        pred_info.owner_type != scenario.entity.entity_type
        or pred_info.py_field_name != scenario.field.field_name
        or pred_info.is_entity_exists
        or pred_info.is_identity_field
        or pred_info.cardinality != "single"
        or pred_info.value_type_domain not in {"string", "int", "float64", "bool", "bytes", "time", "uuid"}
    ):
        raise ScenarioResolutionError(
            "scenario supports only non-identity, single scalar schema fields",
            code="SCENARIO_FIELD_UNSUPPORTED",
        )
    if not is_entity_identity_bundle_active(
        store=store,
        schema_index=schema_index,
        entity_type=scenario.entity.entity_type,
        e_ref=e_ref,
        identity_values=identity,
    ):
        raise ScenarioResolutionError(
            "scenario entity does not have a complete active identity bundle",
            code="SCENARIO_ENTITY_IDENTITY_INACTIVE",
        )

    try:
        dependency_predicates = _native_where_dependency_predicates(list(materialized_body))
    except ValueError as exc:
        raise ScenarioResolutionError(
            "scenario Query dependency analysis is unsupported",
            code="SCENARIO_QUERY_DEPENDENCY_UNSUPPORTED",
        ) from exc
    if pred_info.pred_id not in dependency_predicates:
        raise ScenarioResolutionError(
            "scenario field is outside the exact Query dependency relation",
            code="SCENARIO_TARGET_OUTSIDE_QUERY",
        )

    projected = project_view_facts_with_witness(store.ledger, store.schema_ir)
    if not any(row.fact_tuple == (e_ref,) for row in projected.get(info.exists_predicate_id, ())):
        raise ScenarioResolutionError(
            "scenario entity is not visible in the current projection",
            code="SCENARIO_ENTITY_NOT_VISIBLE",
        )
    missing = tuple(pred_id for pred_id in dependency_predicates if pred_id not in projected)
    if missing:
        raise ScenarioResolutionError(
            "scenario Query dependencies are absent from current projection",
            code="SCENARIO_QUERY_DEPENDENCY_MISSING",
        )
    baseline_relation = _immutable_effective_relation_copy(
        {pred_id: projected[pred_id] for pred_id in dependency_predicates}
    )
    target_rows = tuple(
        row
        for row in baseline_relation[pred_info.pred_id]
        if len(row.fact_tuple) == 2 and row.fact_tuple[0] == e_ref
    )
    if len(target_rows) != 1:
        raise ScenarioResolutionError(
            "scenario target must resolve to exactly one visible scalar field fact",
            code="SCENARIO_TARGET_UNAVAILABLE",
        )
    target = target_rows[0]

    value_type = pred_info.value_type_domain
    assert value_type is not None
    raw_value: Any = scenario.value
    if value_type == "uuid" and isinstance(raw_value, str):
        raw_value = raw_value.lower()
    try:
        normalized_value = claim_args_from_rest_terms([(value_type, raw_value)])[0][1]
        validate_field_value(normalized_value, pred_info=pred_info)
        baseline_value = ScenarioScalarValueV0(value_type, target.fact_tuple[1])
        effective_value = ScenarioScalarValueV0(value_type, normalized_value)
    except (FieldValueValidationError, TypeError, ValueError) as exc:
        raise ScenarioResolutionError(
            "scenario value is incompatible with its schema field",
            code="SCENARIO_VALUE_TYPE_MISMATCH",
        ) from exc

    baseline_relation_digest = _relation_digest(baseline_relation)
    witness_id = "scenario_hypothesis_v0:" + sha256_hex(
        _canonical_bytes(
            "scenario_field_substitution_witness_v0",
            {
                "premise_id": scenario.premise_id,
                "entity_ref": e_ref,
                "pred_id": pred_info.pred_id,
                "base_view_digest": base_view_digest,
                "baseline_relation_digest": baseline_relation_digest,
                "replaced_asrt_id": target.asrt_id,
                "effective_value": normalized_value,
            },
        )
    )
    effective_relation = _replace_relation_row(
        baseline_relation,
        pred_id=pred_info.pred_id,
        original=target,
        replacement=ProjectedFact(
            asrt_id=witness_id,
            fact_tuple=(e_ref, normalized_value),
        ),
    )
    effective_relation_digest = _relation_digest(effective_relation)
    resolution = ScenarioResolutionV0(
        premise_id=scenario.premise_id,
        entity_ref=e_ref,
        field=scenario.field,
        baseline_value=baseline_value,
        effective_value=effective_value,
        base_view_digest=base_view_digest,
        baseline_relation_digest=baseline_relation_digest,
        effective_relation_digest=effective_relation_digest,
        semantic_value_changed=baseline_value != effective_value,
        effective_source_changed=True,
    )
    return ResolvedScenarioFieldSubstitutionV0(
        resolution=resolution,
        baseline_relation=baseline_relation,
        effective_relation=effective_relation,
    )


def _replace_relation_row(
    relation: Mapping[str, Sequence[ProjectedFact]],
    *,
    pred_id: str,
    original: ProjectedFact,
    replacement: ProjectedFact,
) -> _NativeEffectiveRelationSnapshot:
    replacement_count = 0
    copied: dict[str, tuple[ProjectedFact, ...]] = {}
    for current_pred_id, rows in relation.items():
        output: list[ProjectedFact] = []
        for row in rows:
            if current_pred_id == pred_id and row == original:
                output.append(replacement)
                replacement_count += 1
            else:
                output.append(ProjectedFact(asrt_id=row.asrt_id, fact_tuple=tuple(row.fact_tuple)))
        copied[current_pred_id] = tuple(output)
    if replacement_count != 1:
        raise ScenarioResolutionError(
            "scenario target relation changed while constructing its effective relation",
            code="SCENARIO_TARGET_REPLACEMENT_FAILED",
        )
    return _immutable_effective_relation_copy(copied)


def _relation_digest(relation: Mapping[str, Sequence[ProjectedFact]]) -> str:
    payload = tuple(
        (
            pred_id,
            tuple((row.asrt_id, tuple(row.fact_tuple)) for row in rows),
        )
        for pred_id, rows in sorted(relation.items())
    )
    return f"sha256:{sha256_hex(_canonical_bytes('scenario_effective_relation_v0', payload))}"


def _canonical_bytes(label: str, payload: object) -> bytes:
    return json.dumps(
        {"format": label, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


__all__ = [
    "ResolvedScenarioFieldSubstitutionV0",
    "ScenarioResolutionError",
    "resolve_scenario_field_substitution_v0",
]
