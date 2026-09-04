"""Resolve the bounded, query-dependency EffectiveSnapshot v1 foundation.

The resolver deliberately consumes only the existing Q7/Q11 replacement input
DTOs.  It returns an identity-only public snapshot plus private immutable
relations used by the old Scenario adapters.  It never claims a global or
historical ledger snapshot.  Resolution captures the legacy active-identity
membership and one relation projection up front; later admission checks consume
those captures rather than re-reading the live Store.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms
from factgraph.core.store._evaluate import (
    _immutable_effective_relation_copy,
    _native_where_dependency_predicates,
    _NativeEffectiveRelationSnapshot,
)
from factgraph.core.store._support import ProjectedFact
from factgraph.core.store.runtime import Store
from factgraph.core.view.projector import project_view_facts_with_witness

from .evaluation_query_runtime import CompiledEvaluationQueryV0
from .protocol.evaluation_scenario import (
    ScenarioFieldSubstitutionOperationV0,
    ScenarioFieldSubstitutionSetV0,
    ScenarioFieldSubstitutionV0,
    ScenarioScalarValueV0,
)
from .protocol.query_effective_snapshot import (
    QueryEffectiveSnapshotNormalizationProfileV1,
    QueryEffectiveSnapshotV1,
    ResolvedExistingVisibleScalarReplacementV1,
)
from .protocol.schema_runtime import EntityRef
from .schema_runtime import (
    EntityTypeInfo,
    SchemaIndex,
    SchemaResolutionError,
    encode_entity_ref,
    entity_info,
    field_predicate,
    materialize_identity,
)
from .value_validation import FieldValueValidationError, validate_field_value


class QueryEffectiveSnapshotResolutionError(ValueError):
    """A bounded Scenario admission failure before native evaluation."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _ScenarioBaselineContextV1:
    """One read-only relation projection shared by an admitted operation set."""

    projected_relation: Mapping[str, Sequence[ProjectedFact]]
    active_identity_requirements: frozenset[
        tuple[str, str, tuple[tuple[str, Any], ...]]
    ]
    dependency_predicates: tuple[str, ...]
    baseline_relation: _NativeEffectiveRelationSnapshot
    baseline_relation_digest: str
    base_view_digest: str


@dataclass(frozen=True)
class ResolvedQueryEffectiveSnapshotMemberV1:
    """Trusted-schema target information retained only by the runtime result."""

    source: ScenarioFieldSubstitutionV0
    entity_ref: str
    pred_id: str
    target: ProjectedFact
    normalized_value: Any
    baseline_value: ScenarioScalarValueV0
    effective_value: ScenarioScalarValueV0

    @property
    def canonical_target_key(self) -> tuple[str, str, str]:
        return (
            self.entity_ref,
            self.source.field.entity_type,
            self.source.field.field_name,
        )


@dataclass(frozen=True)
class ResolvedQueryEffectiveSnapshotV1:
    """Private relation pair paired with one public pre-evaluation identity."""

    snapshot: QueryEffectiveSnapshotV1
    baseline_relation: _NativeEffectiveRelationSnapshot
    effective_relation: _NativeEffectiveRelationSnapshot
    members: tuple[ResolvedQueryEffectiveSnapshotMemberV1, ...]
    legacy_set_operations: tuple[ScenarioFieldSubstitutionOperationV0, ...]


def resolve_query_effective_snapshot_v1(
    scenario: ScenarioFieldSubstitutionV0 | ScenarioFieldSubstitutionSetV0,
    *,
    compiled_query: CompiledEvaluationQueryV0,
    materialized_body: Sequence[Any],
    store: Store,
    schema_index: SchemaIndex,
    base_view_digest: str,
    _projector: Callable[[Any, dict[str, Any]], Mapping[str, Sequence[ProjectedFact]]] = (
        project_view_facts_with_witness
    ),
) -> ResolvedQueryEffectiveSnapshotV1:
    """Resolve one existing Q7/Q11 input into a pre-evaluation relation pair.

    The public snapshot contains no result rows or diff.  It is caller-pinned
    identity only; SDK execution remains responsible for checking the live
    full-view digest after this function returns.
    """

    substitutions, profile = _scenario_input(
        scenario,
    )
    if len({item.premise_id for item in substitutions}) != len(substitutions):
        raise QueryEffectiveSnapshotResolutionError(
            "Scenario substitution set contains duplicate premise_id",
            code="SCENARIO_DUPLICATE_PREMISE_ID",
        )
    context = _resolve_baseline_context_v1(
        compiled_query=compiled_query,
        materialized_body=materialized_body,
        substitutions=substitutions,
        store=store,
        schema_index=schema_index,
        base_view_digest=base_view_digest,
        projector=_projector,
    )
    members = tuple(
        _resolve_member_v1(
            item,
            context=context,
            schema_index=schema_index,
        )
        for item in substitutions
    )
    if len({item.canonical_target_key for item in members}) != len(members):
        raise QueryEffectiveSnapshotResolutionError(
            "Scenario substitution set contains duplicate canonical field target",
            code="SCENARIO_DUPLICATE_TARGET",
        )
    ordered_members = tuple(sorted(members, key=lambda item: item.canonical_target_key))
    legacy_set_operations = _legacy_set_operations(ordered_members, profile=profile)
    public_operations, replacements = _snapshot_operations_and_replacements(
        ordered_members,
        legacy_set_operations=legacy_set_operations,
        profile=profile,
        base_view_digest=base_view_digest,
        baseline_relation_digest=context.baseline_relation_digest,
    )
    effective_relation = _replace_relation_rows(
        context.baseline_relation,
        replacements=replacements,
    )
    snapshot = QueryEffectiveSnapshotV1(
        query_digest=compiled_query.query_digest,
        policy_digest=compiled_query.policy_digest,
        address_space_digest=compiled_query.address_space_digest,
        schema_digest=compiled_query.schema_digest,
        base_view_digest=base_view_digest,
        dependency_predicate_ids=context.dependency_predicates,
        baseline_relation_digest=context.baseline_relation_digest,
        effective_relation_digest=_relation_digest(effective_relation),
        operations=public_operations,
        normalization_profile=profile,
    )
    resolved = ResolvedQueryEffectiveSnapshotV1(
        snapshot=snapshot,
        baseline_relation=context.baseline_relation,
        effective_relation=effective_relation,
        members=ordered_members,
        legacy_set_operations=legacy_set_operations,
    )
    assert_resolved_query_effective_snapshot_current(resolved)
    return resolved


def assert_resolved_query_effective_snapshot_current(
    resolved: ResolvedQueryEffectiveSnapshotV1,
) -> None:
    """Recheck the internal sealed relation pair without consulting a Store.

    This is an integrity check, not authentication.  It detects accidental or
    in-process hybrid relations before legacy Scenario adapters hand either
    relation to the evaluator.
    """

    if not isinstance(resolved, ResolvedQueryEffectiveSnapshotV1):
        raise ValueError("resolved snapshot must be ResolvedQueryEffectiveSnapshotV1")
    snapshot = resolved.snapshot
    if not isinstance(snapshot, QueryEffectiveSnapshotV1):
        raise ValueError("resolved snapshot has invalid public identity")
    QueryEffectiveSnapshotV1.__post_init__(snapshot)
    predicate_ids = tuple(sorted(resolved.baseline_relation))
    if predicate_ids != snapshot.dependency_predicate_ids:
        raise ValueError("resolved snapshot baseline relation keyset does not match dependencies")
    if tuple(sorted(resolved.effective_relation)) != snapshot.dependency_predicate_ids:
        raise ValueError("resolved snapshot effective relation keyset does not match dependencies")
    if _relation_digest(resolved.baseline_relation) != snapshot.baseline_relation_digest:
        raise ValueError("resolved snapshot baseline relation digest does not match")
    if _relation_digest(resolved.effective_relation) != snapshot.effective_relation_digest:
        raise ValueError("resolved snapshot effective relation digest does not match")
    if len(resolved.members) != len(snapshot.operations):
        raise ValueError("resolved snapshot member/operation inventories differ")
    if snapshot.normalization_profile == "single_field_replacement_v0":
        if len(resolved.members) != 1 or resolved.legacy_set_operations:
            raise ValueError("single snapshot has incompatible operation inventory")
    elif len(resolved.legacy_set_operations) != len(resolved.members):
        raise ValueError("set snapshot has incompatible legacy operation inventory")
    replacements: dict[tuple[str, str], ProjectedFact] = {}
    for index, (member, operation) in enumerate(
        zip(resolved.members, snapshot.operations, strict=True)
    ):
        _assert_operation_matches_member(member, operation)
        baseline_rows = tuple(
            row
            for row in resolved.baseline_relation[operation.predicate_id]
            if row.asrt_id == operation.baseline_assertion_id
        )
        if len(baseline_rows) != 1 or baseline_rows[0] != member.target:
            raise ValueError("resolved snapshot baseline target no longer matches operation")
        if _scenario_scalar_from_native(operation.baseline_value.tag, member.target.fact_tuple[1]) != operation.baseline_value:
            raise ValueError("resolved snapshot baseline target value no longer matches operation")
        if _scenario_scalar_from_native(operation.effective_value.tag, member.normalized_value) != operation.effective_value:
            raise ValueError("resolved snapshot effective operation value no longer matches member")
        replacements[(operation.predicate_id, operation.baseline_assertion_id)] = ProjectedFact(
            asrt_id=operation.synthetic_witness_id,
            fact_tuple=(operation.entity_ref, member.normalized_value),
        )
        if snapshot.normalization_profile == "atomic_field_replacement_set_v0":
            legacy = resolved.legacy_set_operations[index]
            if (
                legacy.premise_id,
                legacy.entity_ref,
                legacy.field,
                legacy.baseline_value,
                legacy.effective_value,
                legacy.semantic_value_changed,
            ) != (
                operation.premise_id,
                operation.entity_ref,
                operation.field,
                operation.baseline_value,
                operation.effective_value,
                operation.semantic_value_changed,
            ):
                raise ValueError("resolved snapshot legacy set operation does not match public operation")
    expected_effective = _replace_relation_rows(
        resolved.baseline_relation,
        replacements=replacements,
    )
    if dict(expected_effective) != dict(resolved.effective_relation):
        raise ValueError("resolved snapshot effective relation has an undeclared delta")


def _scenario_input(
    scenario: ScenarioFieldSubstitutionV0 | ScenarioFieldSubstitutionSetV0,
) -> tuple[
    tuple[ScenarioFieldSubstitutionV0, ...],
    QueryEffectiveSnapshotNormalizationProfileV1,
]:
    if isinstance(scenario, ScenarioFieldSubstitutionV0):
        return (scenario,), "single_field_replacement_v0"
    if isinstance(scenario, ScenarioFieldSubstitutionSetV0):
        return scenario.substitutions, "atomic_field_replacement_set_v0"
    raise QueryEffectiveSnapshotResolutionError(
        "scenario must be ScenarioFieldSubstitutionV0 or ScenarioFieldSubstitutionSetV0",
        code="SCENARIO_PROTOCOL_SHAPE",
    )


def _resolve_baseline_context_v1(
    *,
    compiled_query: CompiledEvaluationQueryV0,
    materialized_body: Sequence[Any],
    substitutions: tuple[ScenarioFieldSubstitutionV0, ...],
    store: Store,
    schema_index: SchemaIndex,
    base_view_digest: str,
    projector: Callable[[Any, dict[str, Any]], Mapping[str, Sequence[ProjectedFact]]],
) -> _ScenarioBaselineContextV1:
    if not isinstance(compiled_query, CompiledEvaluationQueryV0):
        raise QueryEffectiveSnapshotResolutionError(
            "scenario requires a trusted CompiledEvaluationQueryV0",
            code="SCENARIO_QUERY_REQUIRED",
        )
    if not isinstance(schema_index, SchemaIndex) or not isinstance(store, Store):
        raise QueryEffectiveSnapshotResolutionError(
            "scenario resolution requires trusted Store and SchemaIndex",
            code="SCENARIO_RUNTIME_CONTEXT",
        )
    try:
        dependency_predicates = _native_where_dependency_predicates(list(materialized_body))
    except ValueError as exc:
        raise QueryEffectiveSnapshotResolutionError(
            "scenario Query dependency analysis is unsupported",
            code="SCENARIO_QUERY_DEPENDENCY_UNSUPPORTED",
        ) from exc
    # Q7/Q11 identity admission means "any matching active Identity Claim",
    # not "the currently chosen Identity Claim". Capture only the exact
    # identity requirements named by this Scenario before the relation
    # projection, then make no further live Store reads while resolving
    # individual Scenario targets.
    active_identity_requirements = _capture_active_identity_requirements(
        store=store,
        schema_index=schema_index,
        substitutions=substitutions,
    )
    projected = projector(store.ledger, store.schema_ir)
    missing = tuple(pred_id for pred_id in dependency_predicates if pred_id not in projected)
    if missing:
        raise QueryEffectiveSnapshotResolutionError(
            "scenario Query dependencies are absent from current projection",
            code="SCENARIO_QUERY_DEPENDENCY_MISSING",
        )
    baseline_relation = _immutable_effective_relation_copy(
        {pred_id: projected[pred_id] for pred_id in dependency_predicates}
    )
    return _ScenarioBaselineContextV1(
        # The full projection is private. It establishes entity visibility and
        # supplies the exact copied dependency relation below; the evaluator
        # never receives unrelated projected relations.
        projected_relation=projected,
        active_identity_requirements=active_identity_requirements,
        dependency_predicates=dependency_predicates,
        baseline_relation=baseline_relation,
        baseline_relation_digest=_relation_digest(baseline_relation),
        base_view_digest=base_view_digest,
    )


def _resolve_member_v1(
    scenario: ScenarioFieldSubstitutionV0,
    *,
    context: _ScenarioBaselineContextV1,
    schema_index: SchemaIndex,
) -> ResolvedQueryEffectiveSnapshotMemberV1:
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
        raise QueryEffectiveSnapshotResolutionError(
            "scenario entity or field is not available in the active schema",
            code="SCENARIO_SCHEMA_TARGET_INVALID",
        ) from exc
    if scenario.field.entity_type != scenario.entity.entity_type:
        raise QueryEffectiveSnapshotResolutionError(
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
        raise QueryEffectiveSnapshotResolutionError(
            "scenario supports only non-identity, single scalar schema fields",
            code="SCENARIO_FIELD_UNSUPPORTED",
        )
    if not _identity_bundle_is_active_in_capture(
        active_identity_requirements=context.active_identity_requirements,
        info=info,
        e_ref=entity_ref,
        identity_values=identity,
    ):
        raise QueryEffectiveSnapshotResolutionError(
            "scenario entity does not have a complete active identity bundle",
            code="SCENARIO_ENTITY_IDENTITY_INACTIVE",
        )
    if pred_info.pred_id not in context.dependency_predicates:
        raise QueryEffectiveSnapshotResolutionError(
            "scenario field is outside the exact Query dependency relation",
            code="SCENARIO_TARGET_OUTSIDE_QUERY",
        )
    if not any(
        row.fact_tuple == (entity_ref,)
        for row in context.projected_relation.get(info.exists_predicate_id, ())
    ):
        raise QueryEffectiveSnapshotResolutionError(
            "scenario entity is not visible in the current projection",
            code="SCENARIO_ENTITY_NOT_VISIBLE",
        )
    target_rows = tuple(
        row
        for row in context.baseline_relation[pred_info.pred_id]
        if len(row.fact_tuple) == 2 and row.fact_tuple[0] == entity_ref
    )
    if len(target_rows) != 1:
        raise QueryEffectiveSnapshotResolutionError(
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
        baseline_value = _scenario_scalar_from_native(value_type, target.fact_tuple[1])
        effective_value = _scenario_scalar_from_native(value_type, normalized_value)
    except (FieldValueValidationError, TypeError, ValueError) as exc:
        raise QueryEffectiveSnapshotResolutionError(
            "scenario value is incompatible with its schema field",
            code="SCENARIO_VALUE_TYPE_MISMATCH",
        ) from exc
    return ResolvedQueryEffectiveSnapshotMemberV1(
        source=scenario,
        entity_ref=entity_ref,
        pred_id=pred_info.pred_id,
        target=target,
        normalized_value=normalized_value,
        baseline_value=baseline_value,
        effective_value=effective_value,
    )


def _capture_active_identity_requirements(
    *,
    store: Store,
    schema_index: SchemaIndex,
    substitutions: tuple[ScenarioFieldSubstitutionV0, ...],
) -> frozenset[tuple[str, str, tuple[tuple[str, Any], ...]]]:
    """Capture only this Scenario's Q7/Q11 active-identity requirements.

    A single-cardinality projection may retain only one of several active
    identity claims.  Q7/Q11 deliberately admitted any active matching claim,
    so this narrow admission capture is separate from the Query dependency
    relation. It never stores unrelated identity values and is not a public
    EffectiveSnapshot claim.
    """

    requirements: set[tuple[str, str, tuple[tuple[str, Any], ...]]] = set()
    for substitution in substitutions:
        try:
            identity = materialize_identity(
                substitution.entity.entity_type,
                substitution.entity.identity,
                index=schema_index,
            )
            entity_ref = encode_entity_ref(
                EntityRef(substitution.entity.entity_type, identity),
                index=schema_index,
            )
            info = entity_info(schema_index, substitution.entity.entity_type)
        except SchemaResolutionError as exc:
            raise QueryEffectiveSnapshotResolutionError(
                "scenario entity is not available in the active schema",
                code="SCENARIO_SCHEMA_TARGET_INVALID",
            ) from exc
        for identity_field in info.identity_fields:
            requirements.add(
                (
                    info.identity_predicates[identity_field.name].pred_id,
                    entity_ref,
                    ((identity_field.type_domain, identity[identity_field.name]),),
                )
            )

    captured: set[tuple[str, str, tuple[tuple[str, Any], ...]]] = set()
    for predicate_id, entity_ref, expected_terms in requirements:
        for claim in store.ledger.find_claims(pred_id=predicate_id, e_ref=entity_ref):
            if store.ledger.has_active_revocation(claim.asrt_id):
                continue
            if tuple(claim.rest_terms) == expected_terms:
                captured.add((predicate_id, entity_ref, expected_terms))
                break
    return frozenset(captured)


def _identity_bundle_is_active_in_capture(
    *,
    active_identity_requirements: frozenset[
        tuple[str, str, tuple[tuple[str, Any], ...]]
    ],
    info: EntityTypeInfo,
    e_ref: str,
    identity_values: Mapping[str, Any],
) -> bool:
    """Apply the old active-bundle admission semantics to the captured set."""

    for identity_field in info.identity_fields:
        try:
            # Q7's active-claim predicate compares the stored rest terms,
            # rather than the canonical claim-arg atom.  Keep this exact for
            # float64 (and every other identity domain) while the v1 resolver
            # retains its same admission semantics.
            expected_terms = ((identity_field.type_domain, identity_values[identity_field.name]),)
        except (KeyError, TypeError, ValueError):
            return False
        predicate = info.identity_predicates[identity_field.name]
        if (predicate.pred_id, e_ref, expected_terms) not in active_identity_requirements:
            return False
    return True


def _legacy_set_operations(
    members: tuple[ResolvedQueryEffectiveSnapshotMemberV1, ...],
    *,
    profile: QueryEffectiveSnapshotNormalizationProfileV1,
) -> tuple[ScenarioFieldSubstitutionOperationV0, ...]:
    if profile == "single_field_replacement_v0":
        return ()
    return tuple(
        ScenarioFieldSubstitutionOperationV0(
            premise_id=item.source.premise_id,
            entity_ref=item.entity_ref,
            field=item.source.field,
            baseline_value=item.baseline_value,
            effective_value=item.effective_value,
            semantic_value_changed=item.baseline_value != item.effective_value,
            effective_source_changed=True,
        )
        for item in members
    )


def _snapshot_operations_and_replacements(
    members: tuple[ResolvedQueryEffectiveSnapshotMemberV1, ...],
    *,
    legacy_set_operations: tuple[ScenarioFieldSubstitutionOperationV0, ...],
    profile: QueryEffectiveSnapshotNormalizationProfileV1,
    base_view_digest: str,
    baseline_relation_digest: str,
) -> tuple[
    tuple[ResolvedExistingVisibleScalarReplacementV1, ...],
    dict[tuple[str, str], ProjectedFact],
]:
    operations: list[ResolvedExistingVisibleScalarReplacementV1] = []
    replacements: dict[tuple[str, str], ProjectedFact] = {}
    for index, member in enumerate(members):
        if profile == "single_field_replacement_v0":
            witness_id = "scenario_hypothesis_v0:" + sha256_hex(
                _canonical_bytes(
                    "scenario_field_substitution_witness_v0",
                    {
                        "premise_id": member.source.premise_id,
                        "entity_ref": member.entity_ref,
                        "pred_id": member.pred_id,
                        "base_view_digest": base_view_digest,
                        "baseline_relation_digest": baseline_relation_digest,
                        "replaced_asrt_id": member.target.asrt_id,
                        "effective_value": member.normalized_value,
                    },
                )
            )
        else:
            legacy = legacy_set_operations[index]
            witness_id = "scenario_hypothesis_set_v0:" + sha256_hex(
                _canonical_bytes(
                    "scenario_field_substitution_set_witness_v0",
                    {
                        "operation_digest": legacy.operation_digest,
                        "base_view_digest": base_view_digest,
                        "baseline_relation_digest": baseline_relation_digest,
                        "replaced_asrt_id": member.target.asrt_id,
                    },
                )
            )
        operation = ResolvedExistingVisibleScalarReplacementV1(
            premise_id=member.source.premise_id,
            entity_ref=member.entity_ref,
            field=member.source.field,
            predicate_id=member.pred_id,
            baseline_assertion_id=member.target.asrt_id,
            synthetic_witness_id=witness_id,
            baseline_value=member.baseline_value,
            effective_value=member.effective_value,
            semantic_value_changed=member.baseline_value != member.effective_value,
        )
        operations.append(operation)
        replacements[(member.pred_id, member.target.asrt_id)] = ProjectedFact(
            asrt_id=witness_id,
            fact_tuple=(member.entity_ref, member.normalized_value),
        )
    return tuple(operations), replacements


def _assert_operation_matches_member(
    member: ResolvedQueryEffectiveSnapshotMemberV1,
    operation: ResolvedExistingVisibleScalarReplacementV1,
) -> None:
    if (
        member.source.premise_id,
        member.entity_ref,
        member.source.field,
        member.pred_id,
        member.target.asrt_id,
        member.baseline_value,
        member.effective_value,
        member.baseline_value != member.effective_value,
    ) != (
        operation.premise_id,
        operation.entity_ref,
        operation.field,
        operation.predicate_id,
        operation.baseline_assertion_id,
        operation.baseline_value,
        operation.effective_value,
        operation.semantic_value_changed,
    ):
        raise ValueError("resolved snapshot operation does not match normalized member")


def _scenario_scalar_from_native(tag: str, value: Any) -> ScenarioScalarValueV0:
    normalized = claim_args_from_rest_terms([(tag, value)])[0][1]
    return ScenarioScalarValueV0(tag, normalized)


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
        raise QueryEffectiveSnapshotResolutionError(
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
    # Preserve the Q7/Q11 relation domain: ScenarioRun v0 recomputes it from
    # captured sides, so changing the label would silently break compatibility.
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
    "QueryEffectiveSnapshotResolutionError",
    "ResolvedQueryEffectiveSnapshotMemberV1",
    "ResolvedQueryEffectiveSnapshotV1",
    "assert_resolved_query_effective_snapshot_current",
    "resolve_query_effective_snapshot_v1",
]
