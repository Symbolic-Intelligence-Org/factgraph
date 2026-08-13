"""Resolution of deliberately narrow direct-field Scenario substitutions.

The v0 single substitution and F5B2 atomic substitution-set forms both build
immutable, dependency-complete projected relations.  Neither mutates the
ledger nor delegates to the public FactOverlay API, whose assertion-oriented
semantics are not this Scenario contract.
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
    ScenarioFieldSubstitutionOperationV0,
    ScenarioFieldSubstitutionSetResolutionV0,
    ScenarioFieldSubstitutionSetV0,
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
    """A non-inferential Scenario admission or resolution failure."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedScenarioFieldSubstitutionV0:
    """Internal evaluator-ready relations plus one public Scenario resolution."""

    resolution: ScenarioResolutionV0
    baseline_relation: _NativeEffectiveRelationSnapshot
    effective_relation: _NativeEffectiveRelationSnapshot


@dataclass(frozen=True)
class ResolvedScenarioFieldSubstitutionSetV0:
    """Internal evaluator-ready relations plus one public atomic set resolution."""

    resolution: ScenarioFieldSubstitutionSetResolutionV0
    baseline_relation: _NativeEffectiveRelationSnapshot
    effective_relation: _NativeEffectiveRelationSnapshot


@dataclass(frozen=True)
class _ScenarioBaselineContextV0:
    """One read-only projected baseline shared by all admitted set members."""

    projected_relation: Mapping[str, Sequence[ProjectedFact]]
    dependency_predicates: tuple[str, ...]
    baseline_relation: _NativeEffectiveRelationSnapshot
    baseline_relation_digest: str
    base_view_digest: str


@dataclass(frozen=True)
class _ResolvedScenarioMemberV0:
    """Trusted-schema-normalized target and replacement before effective build."""

    source: ScenarioFieldSubstitutionV0
    entity_ref: str
    pred_id: str
    target: ProjectedFact
    normalized_value: Any
    baseline_value: ScenarioScalarValueV0
    effective_value: ScenarioScalarValueV0

    @property
    def canonical_target_key(self) -> tuple[str, str]:
        return (self.entity_ref, self.pred_id)

    @property
    def canonical_operation_order(self) -> tuple[str, str, str]:
        return (
            self.entity_ref,
            self.source.field.entity_type,
            self.source.field.field_name,
        )


def resolve_scenario_field_substitution_v0(
    scenario: ScenarioFieldSubstitutionV0,
    *,
    compiled_query: CompiledEvaluationQueryV0,
    materialized_body: Sequence[Any],
    store: Store,
    schema_index: SchemaIndex,
    base_view_digest: str,
) -> ResolvedScenarioFieldSubstitutionV0:
    """Resolve the original one-member Q7 contract without changing its DTO/digest."""

    if not isinstance(scenario, ScenarioFieldSubstitutionV0):
        raise ScenarioResolutionError(
            "scenario must be ScenarioFieldSubstitutionV0",
            code="SCENARIO_PROTOCOL_SHAPE",
        )
    context = _resolve_scenario_baseline_context_v0(
        compiled_query=compiled_query,
        materialized_body=materialized_body,
        store=store,
        schema_index=schema_index,
        base_view_digest=base_view_digest,
    )
    member = _resolve_scenario_member_v0(
        scenario,
        context=context,
        store=store,
        schema_index=schema_index,
    )
    witness_id = "scenario_hypothesis_v0:" + sha256_hex(
        _canonical_bytes(
            "scenario_field_substitution_witness_v0",
            {
                "premise_id": scenario.premise_id,
                "entity_ref": member.entity_ref,
                "pred_id": member.pred_id,
                "base_view_digest": base_view_digest,
                "baseline_relation_digest": context.baseline_relation_digest,
                "replaced_asrt_id": member.target.asrt_id,
                "effective_value": member.normalized_value,
            },
        )
    )
    effective_relation = _replace_relation_row(
        context.baseline_relation,
        pred_id=member.pred_id,
        original=member.target,
        replacement=ProjectedFact(
            asrt_id=witness_id,
            fact_tuple=(member.entity_ref, member.normalized_value),
        ),
    )
    effective_relation_digest = _relation_digest(effective_relation)
    resolution = ScenarioResolutionV0(
        premise_id=scenario.premise_id,
        entity_ref=member.entity_ref,
        field=scenario.field,
        baseline_value=member.baseline_value,
        effective_value=member.effective_value,
        base_view_digest=base_view_digest,
        baseline_relation_digest=context.baseline_relation_digest,
        effective_relation_digest=effective_relation_digest,
        semantic_value_changed=member.baseline_value != member.effective_value,
        effective_source_changed=True,
    )
    return ResolvedScenarioFieldSubstitutionV0(
        resolution=resolution,
        baseline_relation=context.baseline_relation,
        effective_relation=effective_relation,
    )


def resolve_scenario_field_substitution_set_v0(
    scenario: ScenarioFieldSubstitutionSetV0,
    *,
    compiled_query: CompiledEvaluationQueryV0,
    materialized_body: Sequence[Any],
    store: Store,
    schema_index: SchemaIndex,
    base_view_digest: str,
) -> ResolvedScenarioFieldSubstitutionSetV0:
    """Resolve all direct members atomically before either evaluator call."""

    if not isinstance(scenario, ScenarioFieldSubstitutionSetV0):
        raise ScenarioResolutionError(
            "scenario must be ScenarioFieldSubstitutionSetV0",
            code="SCENARIO_PROTOCOL_SHAPE",
        )
    premise_ids = tuple(item.premise_id for item in scenario.substitutions)
    if len(set(premise_ids)) != len(premise_ids):
        raise ScenarioResolutionError(
            "Scenario substitution set contains duplicate premise_id",
            code="SCENARIO_DUPLICATE_PREMISE_ID",
        )
    context = _resolve_scenario_baseline_context_v0(
        compiled_query=compiled_query,
        materialized_body=materialized_body,
        store=store,
        schema_index=schema_index,
        base_view_digest=base_view_digest,
    )
    members = tuple(
        _resolve_scenario_member_v0(
            item,
            context=context,
            store=store,
            schema_index=schema_index,
        )
        for item in scenario.substitutions
    )
    target_keys = tuple(item.canonical_target_key for item in members)
    if len(set(target_keys)) != len(target_keys):
        raise ScenarioResolutionError(
            "Scenario substitution set contains duplicate canonical field target",
            code="SCENARIO_DUPLICATE_TARGET",
        )
    ordered_members = tuple(sorted(members, key=lambda item: item.canonical_operation_order))
    operations = tuple(
        ScenarioFieldSubstitutionOperationV0(
            premise_id=item.source.premise_id,
            entity_ref=item.entity_ref,
            field=item.source.field,
            baseline_value=item.baseline_value,
            effective_value=item.effective_value,
            semantic_value_changed=item.baseline_value != item.effective_value,
            effective_source_changed=True,
        )
        for item in ordered_members
    )
    replacements: dict[tuple[str, str], ProjectedFact] = {}
    for item, operation in zip(ordered_members, operations, strict=True):
        witness_id = "scenario_hypothesis_set_v0:" + sha256_hex(
            _canonical_bytes(
                "scenario_field_substitution_set_witness_v0",
                {
                    "operation_digest": operation.operation_digest,
                    "base_view_digest": base_view_digest,
                    "baseline_relation_digest": context.baseline_relation_digest,
                    "replaced_asrt_id": item.target.asrt_id,
                },
            )
        )
        replacements[(item.pred_id, item.target.asrt_id)] = ProjectedFact(
            asrt_id=witness_id,
            fact_tuple=(item.entity_ref, item.normalized_value),
        )
    effective_relation = _replace_relation_rows(
        context.baseline_relation,
        replacements=replacements,
    )
    effective_relation_digest = _relation_digest(effective_relation)
    resolution = ScenarioFieldSubstitutionSetResolutionV0(
        operations=operations,
        base_view_digest=base_view_digest,
        baseline_relation_digest=context.baseline_relation_digest,
        effective_relation_digest=effective_relation_digest,
    )
    return ResolvedScenarioFieldSubstitutionSetV0(
        resolution=resolution,
        baseline_relation=context.baseline_relation,
        effective_relation=effective_relation,
    )


def _resolve_scenario_baseline_context_v0(
    *,
    compiled_query: CompiledEvaluationQueryV0,
    materialized_body: Sequence[Any],
    store: Store,
    schema_index: SchemaIndex,
    base_view_digest: str,
) -> _ScenarioBaselineContextV0:
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
        dependency_predicates = _native_where_dependency_predicates(list(materialized_body))
    except ValueError as exc:
        raise ScenarioResolutionError(
            "scenario Query dependency analysis is unsupported",
            code="SCENARIO_QUERY_DEPENDENCY_UNSUPPORTED",
        ) from exc
    projected = project_view_facts_with_witness(store.ledger, store.schema_ir)
    missing = tuple(pred_id for pred_id in dependency_predicates if pred_id not in projected)
    if missing:
        raise ScenarioResolutionError(
            "scenario Query dependencies are absent from current projection",
            code="SCENARIO_QUERY_DEPENDENCY_MISSING",
        )
    baseline_relation = _immutable_effective_relation_copy(
        {pred_id: projected[pred_id] for pred_id in dependency_predicates}
    )
    return _ScenarioBaselineContextV0(
        # This private resolver-local projection is used only to establish
        # entity visibility.  The evaluator receives the separately copied,
        # dependency-complete baseline relation below; copying every unrelated
        # predicate here would make an otherwise bounded Scenario scale with
        # the entire ledger.
        projected_relation=projected,
        dependency_predicates=dependency_predicates,
        baseline_relation=baseline_relation,
        baseline_relation_digest=_relation_digest(baseline_relation),
        base_view_digest=base_view_digest,
    )


def _resolve_scenario_member_v0(
    scenario: ScenarioFieldSubstitutionV0,
    *,
    context: _ScenarioBaselineContextV0,
    store: Store,
    schema_index: SchemaIndex,
) -> _ResolvedScenarioMemberV0:
    try:
        identity = materialize_identity(
            scenario.entity.entity_type,
            scenario.entity.identity,
            index=schema_index,
        )
        entity_ref = encode_entity_ref(
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
        or pred_info.value_type_domain
        not in {"string", "int", "float64", "bool", "bytes", "time", "uuid"}
    ):
        raise ScenarioResolutionError(
            "scenario supports only non-identity, single scalar schema fields",
            code="SCENARIO_FIELD_UNSUPPORTED",
        )
    if not is_entity_identity_bundle_active(
        store=store,
        schema_index=schema_index,
        entity_type=scenario.entity.entity_type,
        e_ref=entity_ref,
        identity_values=identity,
    ):
        raise ScenarioResolutionError(
            "scenario entity does not have a complete active identity bundle",
            code="SCENARIO_ENTITY_IDENTITY_INACTIVE",
        )
    if pred_info.pred_id not in context.dependency_predicates:
        raise ScenarioResolutionError(
            "scenario field is outside the exact Query dependency relation",
            code="SCENARIO_TARGET_OUTSIDE_QUERY",
        )
    if not any(
        row.fact_tuple == (entity_ref,)
        for row in context.projected_relation.get(info.exists_predicate_id, ())
    ):
        raise ScenarioResolutionError(
            "scenario entity is not visible in the current projection",
            code="SCENARIO_ENTITY_NOT_VISIBLE",
        )
    target_rows = tuple(
        row
        for row in context.baseline_relation[pred_info.pred_id]
        if len(row.fact_tuple) == 2 and row.fact_tuple[0] == entity_ref
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
    return _ResolvedScenarioMemberV0(
        source=scenario,
        entity_ref=entity_ref,
        pred_id=pred_info.pred_id,
        target=target,
        normalized_value=normalized_value,
        baseline_value=baseline_value,
        effective_value=effective_value,
    )


def _replace_relation_row(
    relation: Mapping[str, Sequence[ProjectedFact]],
    *,
    pred_id: str,
    original: ProjectedFact,
    replacement: ProjectedFact,
) -> _NativeEffectiveRelationSnapshot:
    return _replace_relation_rows(
        relation,
        replacements={(pred_id, original.asrt_id): replacement},
    )


def _replace_relation_rows(
    relation: Mapping[str, Sequence[ProjectedFact]],
    *,
    replacements: Mapping[tuple[str, str], ProjectedFact],
) -> _NativeEffectiveRelationSnapshot:
    replacement_counts = {key: 0 for key in replacements}
    copied: dict[str, tuple[ProjectedFact, ...]] = {}
    for current_pred_id, rows in relation.items():
        output: list[ProjectedFact] = []
        for row in rows:
            key = (current_pred_id, row.asrt_id)
            replacement = replacements.get(key)
            if replacement is not None:
                output.append(replacement)
                replacement_counts[key] += 1
            else:
                output.append(ProjectedFact(asrt_id=row.asrt_id, fact_tuple=tuple(row.fact_tuple)))
        copied[current_pred_id] = tuple(output)
    if any(count != 1 for count in replacement_counts.values()):
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
    "ResolvedScenarioFieldSubstitutionSetV0",
    "ResolvedScenarioFieldSubstitutionV0",
    "ScenarioResolutionError",
    "resolve_scenario_field_substitution_set_v0",
    "resolve_scenario_field_substitution_v0",
]
