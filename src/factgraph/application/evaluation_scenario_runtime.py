"""Q7/Q11 compatibility adapters over the query EffectiveSnapshot v1 resolver.

The public Scenario v0 values intentionally remain result-aware compatibility
records: their digests include an optional result diff and their synthetic
witness identities retain their old labels.  The shared v1 normalizer below
only resolves the pre-evaluation relation pair; these adapters reconstruct the
old DTOs without changing their wire/digest behavior.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from factgraph.core.store._evaluate import _NativeEffectiveRelationSnapshot
from factgraph.core.store.runtime import Store
from factgraph.core.view.projector import project_view_facts_with_witness

from .evaluation_query_runtime import CompiledEvaluationQueryV0
from .protocol.evaluation_scenario import (
    ScenarioFieldSubstitutionSetResolutionV0,
    ScenarioFieldSubstitutionSetV0,
    ScenarioFieldSubstitutionV0,
    ScenarioResolutionV0,
)
from .protocol.query_effective_snapshot import QueryEffectiveSnapshotV1
from .protocol.scenario_run import ScenarioPremiseBindingV0
from .query_effective_snapshot_runtime import (
    QueryEffectiveSnapshotResolutionError,
    ResolvedQueryEffectiveSnapshotV1,
    assert_resolved_query_effective_snapshot_current,
    resolve_query_effective_snapshot_v1,
)
from .schema_runtime import SchemaIndex


class ScenarioResolutionError(ValueError):
    """A non-inferential Q7/Q11 Scenario admission or resolution failure."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedScenarioFieldSubstitutionV0:
    """Old Q7 public resolution paired with v1's immutable relation inputs."""

    resolution: ScenarioResolutionV0
    baseline_relation: _NativeEffectiveRelationSnapshot
    effective_relation: _NativeEffectiveRelationSnapshot
    premise_bindings: tuple[ScenarioPremiseBindingV0, ...]
    effective_snapshot: QueryEffectiveSnapshotV1
    _effective_snapshot_runtime: ResolvedQueryEffectiveSnapshotV1 = field(
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class ResolvedScenarioFieldSubstitutionSetV0:
    """Old Q11 public resolution paired with v1's immutable relation inputs."""

    resolution: ScenarioFieldSubstitutionSetResolutionV0
    baseline_relation: _NativeEffectiveRelationSnapshot
    effective_relation: _NativeEffectiveRelationSnapshot
    premise_bindings: tuple[ScenarioPremiseBindingV0, ...]
    effective_snapshot: QueryEffectiveSnapshotV1
    _effective_snapshot_runtime: ResolvedQueryEffectiveSnapshotV1 = field(
        repr=False,
        compare=False,
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
    """Resolve the original Q7 contract without changing its DTO/digest."""

    if not isinstance(scenario, ScenarioFieldSubstitutionV0):
        raise ScenarioResolutionError(
            "scenario must be ScenarioFieldSubstitutionV0",
            code="SCENARIO_PROTOCOL_SHAPE",
        )
    snapshot = _resolve_compat_snapshot(
        scenario,
        compiled_query=compiled_query,
        materialized_body=materialized_body,
        store=store,
        schema_index=schema_index,
        base_view_digest=base_view_digest,
    )
    member = snapshot.members[0]
    operation = snapshot.snapshot.operations[0]
    resolution = ScenarioResolutionV0(
        premise_id=operation.premise_id,
        entity_ref=operation.entity_ref,
        field=operation.field,
        baseline_value=operation.baseline_value,
        effective_value=operation.effective_value,
        base_view_digest=snapshot.snapshot.base_view_digest,
        baseline_relation_digest=snapshot.snapshot.baseline_relation_digest,
        effective_relation_digest=snapshot.snapshot.effective_relation_digest,
        semantic_value_changed=operation.semantic_value_changed,
        effective_source_changed=True,
    )
    binding = ScenarioPremiseBindingV0(
        premise_id=operation.premise_id,
        operation_digest=resolution.operation_digest,
        origin_kind="scenario_hypothesis_v0",
        entity_ref=operation.entity_ref,
        field=operation.field,
        predicate_id=operation.predicate_id,
        baseline_assertion_id=operation.baseline_assertion_id,
        synthetic_witness_id=operation.synthetic_witness_id,
        baseline_value=operation.baseline_value,
        effective_value=operation.effective_value,
        semantic_value_changed=operation.semantic_value_changed,
    )
    # Keep a local use of the normalized member as an invariant against a
    # compatibility adapter accidentally losing target provenance.
    if member.target.asrt_id != binding.baseline_assertion_id:
        raise ScenarioResolutionError(
            "Scenario replacement target changed during compatibility adaptation",
            code="SCENARIO_TARGET_REPLACEMENT_FAILED",
        )
    return ResolvedScenarioFieldSubstitutionV0(
        resolution=resolution,
        baseline_relation=snapshot.baseline_relation,
        effective_relation=snapshot.effective_relation,
        premise_bindings=(binding,),
        effective_snapshot=snapshot.snapshot,
        _effective_snapshot_runtime=snapshot,
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
    """Resolve Q11's atomic set without changing its public DTO/digest."""

    if not isinstance(scenario, ScenarioFieldSubstitutionSetV0):
        raise ScenarioResolutionError(
            "scenario must be ScenarioFieldSubstitutionSetV0",
            code="SCENARIO_PROTOCOL_SHAPE",
        )
    snapshot = _resolve_compat_snapshot(
        scenario,
        compiled_query=compiled_query,
        materialized_body=materialized_body,
        store=store,
        schema_index=schema_index,
        base_view_digest=base_view_digest,
    )
    operations = snapshot.snapshot.operations
    legacy_operations = snapshot.legacy_set_operations
    if len(operations) != len(legacy_operations):
        raise ScenarioResolutionError(
            "Scenario set operation inventory changed during compatibility adaptation",
            code="SCENARIO_TARGET_REPLACEMENT_FAILED",
        )
    bindings = tuple(
        ScenarioPremiseBindingV0(
            premise_id=operation.premise_id,
            operation_digest=legacy.operation_digest,
            origin_kind="scenario_hypothesis_set_v0",
            entity_ref=operation.entity_ref,
            field=operation.field,
            predicate_id=operation.predicate_id,
            baseline_assertion_id=operation.baseline_assertion_id,
            synthetic_witness_id=operation.synthetic_witness_id,
            baseline_value=operation.baseline_value,
            effective_value=operation.effective_value,
            semantic_value_changed=operation.semantic_value_changed,
        )
        for operation, legacy in zip(operations, legacy_operations, strict=True)
    )
    resolution = ScenarioFieldSubstitutionSetResolutionV0(
        operations=legacy_operations,
        base_view_digest=snapshot.snapshot.base_view_digest,
        baseline_relation_digest=snapshot.snapshot.baseline_relation_digest,
        effective_relation_digest=snapshot.snapshot.effective_relation_digest,
    )
    return ResolvedScenarioFieldSubstitutionSetV0(
        resolution=resolution,
        baseline_relation=snapshot.baseline_relation,
        effective_relation=snapshot.effective_relation,
        premise_bindings=bindings,
        effective_snapshot=snapshot.snapshot,
        _effective_snapshot_runtime=snapshot,
    )


def _resolve_compat_snapshot(
    scenario: ScenarioFieldSubstitutionV0 | ScenarioFieldSubstitutionSetV0,
    *,
    compiled_query: CompiledEvaluationQueryV0,
    materialized_body: Sequence[Any],
    store: Store,
    schema_index: SchemaIndex,
    base_view_digest: str,
) -> ResolvedQueryEffectiveSnapshotV1:
    try:
        # Passing this module's name keeps pre-existing SDK tests able to patch
        # the projection boundary while the resolver itself remains shared.
        return resolve_query_effective_snapshot_v1(
            scenario,
            compiled_query=compiled_query,
            materialized_body=materialized_body,
            store=store,
            schema_index=schema_index,
            base_view_digest=base_view_digest,
            _projector=project_view_facts_with_witness,
        )
    except QueryEffectiveSnapshotResolutionError as exc:
        raise ScenarioResolutionError(str(exc), code=exc.code) from exc


def assert_resolved_scenario_compatibility_current(
    resolved: ResolvedScenarioFieldSubstitutionV0 | ResolvedScenarioFieldSubstitutionSetV0,
) -> None:
    """Reject a hybrid old-Scenario/v1-runtime adapter result.

    The public Q7/Q11 result fields and the private v1 runtime relation pair
    are deliberately parallel.  They must therefore be compared explicitly
    before an SDK caller evaluates the exposed relations or emits the old
    premise bindings.  This is integrity checking, not authentication.
    """

    if not isinstance(
        resolved,
        (ResolvedScenarioFieldSubstitutionV0, ResolvedScenarioFieldSubstitutionSetV0),
    ):
        raise ValueError("resolved Scenario must be one of the Q7/Q11 compatibility adapters")  # noqa: TRY004 - Integrity check; SDK wraps ValueError into SDKStoreError.
    runtime = resolved._effective_snapshot_runtime
    if not isinstance(runtime, ResolvedQueryEffectiveSnapshotV1):
        raise ValueError("resolved Scenario has invalid private v1 runtime state")  # noqa: TRY004 - Integrity check; SDK wraps ValueError into SDKStoreError.
    if not isinstance(resolved.effective_snapshot, QueryEffectiveSnapshotV1):
        raise ValueError("resolved Scenario has invalid public v1 snapshot")  # noqa: TRY004 - Integrity check; SDK wraps ValueError into SDKStoreError.
    assert_resolved_query_effective_snapshot_current(runtime)
    snapshot = runtime.snapshot
    if (
        resolved.effective_snapshot != snapshot
        or resolved.baseline_relation != runtime.baseline_relation
        or resolved.effective_relation != runtime.effective_relation
        or resolved.resolution.base_view_digest != snapshot.base_view_digest
        or resolved.resolution.baseline_relation_digest != snapshot.baseline_relation_digest
        or resolved.resolution.effective_relation_digest != snapshot.effective_relation_digest
    ):
        raise ValueError("resolved Scenario compatibility adapter does not match its v1 snapshot")
    operations = snapshot.operations
    bindings = resolved.premise_bindings
    if len(bindings) != len(operations):
        raise ValueError("resolved Scenario premise binding inventory does not match v1 snapshot")
    if isinstance(resolved, ResolvedScenarioFieldSubstitutionV0):
        resolution = resolved.resolution
        operation = operations[0] if len(operations) == 1 else None
        if (
            operation is None
            or resolution.result_diff is not None
            or resolution.origin_kind != "scenario_hypothesis_v0"
            or resolution.effective_source_changed is not True
            or (
                resolution.premise_id,
                resolution.entity_ref,
                resolution.field,
                resolution.baseline_value,
                resolution.effective_value,
                resolution.semantic_value_changed,
            )
            != (
                operation.premise_id,
                operation.entity_ref,
                operation.field,
                operation.baseline_value,
                operation.effective_value,
                operation.semantic_value_changed,
            )
            or bindings[0].operation_digest != resolution.operation_digest
        ):
            raise ValueError("resolved Q7 premise binding does not match old Scenario resolution")
        expected_origin = "scenario_hypothesis_v0"
    else:
        resolution = resolved.resolution
        legacy_operations = resolution.operations
        if (
            resolution.result_diff is not None
            or resolution.origin_kind != "scenario_hypothesis_set_v0"
            or len(legacy_operations) != len(operations)
        ):
            raise ValueError("resolved Q11 operation inventory does not match v1 snapshot")
        for legacy, operation in zip(legacy_operations, operations, strict=True):
            if (
                legacy.origin_kind != "scenario_hypothesis_set_v0"
                or legacy.effective_source_changed is not True
                or (
                    legacy.premise_id,
                    legacy.entity_ref,
                    legacy.field,
                    legacy.baseline_value,
                    legacy.effective_value,
                    legacy.semantic_value_changed,
                )
                != (
                    operation.premise_id,
                    operation.entity_ref,
                    operation.field,
                    operation.baseline_value,
                    operation.effective_value,
                    operation.semantic_value_changed,
                )
            ):
                raise ValueError("resolved Q11 operation does not match v1 snapshot")
        expected_origin = "scenario_hypothesis_set_v0"
    for index, (binding, operation) in enumerate(zip(bindings, operations, strict=True)):
        if isinstance(resolved, ResolvedScenarioFieldSubstitutionSetV0) and (
            binding.operation_digest != resolved.resolution.operations[index].operation_digest
        ):
            raise ValueError("resolved Q11 premise binding does not match old set operation")
        if (
            binding.origin_kind != expected_origin
            or binding.premise_id != operation.premise_id
            or binding.entity_ref != operation.entity_ref
            or binding.field != operation.field
            or binding.predicate_id != operation.predicate_id
            or binding.baseline_assertion_id != operation.baseline_assertion_id
            or binding.synthetic_witness_id != operation.synthetic_witness_id
            or binding.baseline_value != operation.baseline_value
            or binding.effective_value != operation.effective_value
            or binding.semantic_value_changed != operation.semantic_value_changed
        ):
            raise ValueError("resolved Scenario premise binding does not match v1 operation")


__all__ = [
    "ResolvedScenarioFieldSubstitutionSetV0",
    "ResolvedScenarioFieldSubstitutionV0",
    "ScenarioResolutionError",
    "assert_resolved_scenario_compatibility_current",
    "resolve_scenario_field_substitution_set_v0",
    "resolve_scenario_field_substitution_v0",
]
