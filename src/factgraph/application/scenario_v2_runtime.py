"""Trusted normalization helpers for the parallel Scenario V2 values.

The existing V1 resolver remains the owner of schema validation, conflict
resolution, exact-local closure and effective tuple computation.  This module
does not duplicate that evaluator-facing algebra.  It supplies the narrow V2
handoff around it:

``resolved V1 tuple -> selected V2 metadata -> EffectiveWorldFactV2 ->
normalize scenario duplicates -> EffectiveWorldV2``.

That boundary lets a caller attach strict semantic/provenance/display material
without passing a generic metadata dictionary into V1 or a ledger.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .protocol.common import ProtocolShapeError
from .protocol.provenance_v1 import canonical_provenance_refs_v1
from .protocol.scenario_v1 import (
    EffectiveWorldV1,
    ResolvedScenarioOperationV1,
    ResolvedScenarioV1,
    ScenarioEnsureMemberV1,
    ScenarioSetEffectiveValueV1,
    ScenarioSetExactMembersV1,
    ScenarioValueV1,
    ScenarioWithoutFieldV1,
    ScenarioWithoutValueV1,
)
from .protocol.scenario_v2 import (
    EffectiveWorldFactV2,
    EffectiveWorldV2,
    ResolvedScenarioOperationEvidenceV2,
    ScenarioDisplayV2,
    ScenarioMetaV2,
    ScenarioOperationMetaBindingV2,
    ScenarioOperationV2,
    ScenarioSpecV2,
    _token,
    lower_scenario_meta_v2,
)
from .protocol.schema_runtime import EntityRef, FieldPath


class ScenarioResolutionErrorV2(ValueError):
    """A fail-closed V2 metadata/materialization error with a stable code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedScenarioV2:
    """Sealed pair of V2 worlds produced from one Scenario V2 request.

    A caller normally resolves the V1 grammar first, then captures both V2
    world sides through :func:`build_effective_world_v2`.  This carrier only
    validates their relationship and intentionally has no Store/engine handle.
    """

    spec: ScenarioSpecV2
    baseline_world: EffectiveWorldV2
    effective_world: EffectiveWorldV2
    resolution_evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.spec, ScenarioSpecV2):
            raise ProtocolShapeError("ResolvedScenarioV2.spec must be ScenarioSpecV2")
        if not isinstance(self.baseline_world, EffectiveWorldV2) or not isinstance(
            self.effective_world, EffectiveWorldV2
        ):
            raise ProtocolShapeError("ResolvedScenarioV2 worlds must be EffectiveWorldV2")
        if self.baseline_world.schema_digest != self.effective_world.schema_digest:
            raise ProtocolShapeError("ResolvedScenarioV2 worlds must share schema digest")
        if self.baseline_world.base_view_digest != self.effective_world.base_view_digest:
            raise ProtocolShapeError("ResolvedScenarioV2 worlds must share base view digest")
        if self.baseline_world.admissibility_digest != self.effective_world.admissibility_digest:
            raise ProtocolShapeError("ResolvedScenarioV2 worlds must share admission digest")
        object.__setattr__(
            self,
            "resolution_evidence_digest",
            _token(
                "resolved_scenario_v2",
                {
                    "spec_digest": self.spec.spec_digest,
                    "baseline_semantic_world_digest": self.baseline_world.semantic_world_digest,
                    "effective_semantic_world_digest": self.effective_world.semantic_world_digest,
                    "baseline_resolution_evidence_digest": self.baseline_world.resolution_evidence_digest,
                    "effective_resolution_evidence_digest": self.effective_world.resolution_evidence_digest,
                },
            ),
        )


def _assert_v2_spec_wraps_v1(spec: ScenarioSpecV2, resolved: ResolvedScenarioV1) -> None:
    expected = {item.statement_digest for item in resolved.spec.operations}
    actual = {item.operation.statement_digest for item in spec.operations}
    if actual != expected:
        raise ScenarioResolutionErrorV2(
            "ScenarioSpecV2 does not exactly wrap the resolved Scenario V1 request",
            code="SCENARIO_V2_SPEC_V1_MISMATCH",
        )


def _v2_operations_by_premise(spec: ScenarioSpecV2) -> dict[str, ScenarioOperationV2]:
    return {operation.premise_id: operation for operation in spec.operations}


def _metadata_bindings_for_source(
    source: ScenarioOperationV2,
) -> tuple[ScenarioOperationMetaBindingV2, ...]:
    if not isinstance(source.operation, ScenarioSetExactMembersV1):
        return (
            ScenarioOperationMetaBindingV2(
                premise_id=source.premise_id,
                source_operation_digest=source.operation_digest,
                meta=source.meta,
            ),
        )
    bindings = [
        ScenarioOperationMetaBindingV2(
            premise_id=source.premise_id,
            source_operation_digest=source.operation_digest,
            meta=source.meta,
        )
    ]
    for index, value in enumerate(source.operation.values):
        bindings.append(
            ScenarioOperationMetaBindingV2(
                premise_id=source.premise_id,
                source_operation_digest=source.operation_digest,
                meta=metadata_for_scenario_member_v2(source, member_index=index),
                member_value_digest=value.value_digest,
            )
        )
    return tuple(bindings)


def _operation_evidence_from_v1(
    *,
    resolved_v1: ResolvedScenarioV1,
    operation_by_premise: Mapping[str, ScenarioOperationV2],
) -> tuple[ResolvedScenarioOperationEvidenceV2, ...]:
    evidence: list[ResolvedScenarioOperationEvidenceV2] = []
    for resolved in resolved_v1.effective_world.operations:
        bindings: list[ScenarioOperationMetaBindingV2] = []
        for premise_id in resolved.premise_ids:
            source = operation_by_premise.get(premise_id)
            if source is None:
                raise ScenarioResolutionErrorV2(
                    "Scenario V1 resolved operation names unknown V2 premise",
                    code="SCENARIO_V2_PREMISE_UNMAPPED",
                )
            bindings.extend(_metadata_bindings_for_source(source))
        evidence.append(
            ResolvedScenarioOperationEvidenceV2(
                kind=resolved.kind,
                resolved_operation_digest=resolved.operation_digest,
                metadata_bindings=tuple(bindings),
                masked_witness_ids=resolved.masked_witness_ids,
                synthetic_witness_ids=resolved.synthetic_witness_ids,
            )
        )
    return tuple(evidence)


def _assert_semantic_bindings_materialized(
    operation_evidence: tuple[ResolvedScenarioOperationEvidenceV2, ...],
    facts: tuple[EffectiveWorldFactV2, ...],
) -> None:
    for operation in operation_evidence:
        for binding in operation.metadata_bindings:
            if binding.meta.fact_semantics is None:
                continue
            matches = (
                fact
                for fact in facts
                if fact.origin == "scenario_synthetic"
                and binding.source_operation_digest in fact.scenario_operation_digests
                and (
                    binding.member_value_digest is None
                    or bool(fact.values)
                    and fact.values[-1].value_digest == binding.member_value_digest
                )
            )
            if not any(matches):
                raise ScenarioResolutionErrorV2(
                    "Scenario semantic metadata did not materialize into an exact synthetic fact",
                    code="SCENARIO_V2_SEMANTICS_NOT_MATERIALIZED",
                )


def _meta_for_resolved_fact(
    operation: ScenarioOperationV2,
    *,
    fact_values: tuple[ScenarioValueV1, ...],
) -> ScenarioMetaV2:
    """Select the operation/member metadata that produced one V1 synthetic fact."""

    if not isinstance(operation.operation, ScenarioSetExactMembersV1):
        return metadata_for_scenario_member_v2(operation)
    # V1 field member facts end in the exact member value.  Never infer an
    # index from operation ordering: the V1 resolver canonicalizes values.
    if not fact_values:
        raise ScenarioResolutionErrorV2(
            "exact-member synthetic fact is missing a value",
            code="SCENARIO_V2_MEMBER_METADATA_UNRESOLVED",
        )
    member = fact_values[-1]
    matching_indices = tuple(
        index for index, candidate in enumerate(operation.operation.values) if candidate == member
    )
    if len(matching_indices) != 1:
        raise ScenarioResolutionErrorV2(
            "exact-member synthetic fact cannot be matched to a declared member",
            code="SCENARIO_V2_MEMBER_METADATA_UNRESOLVED",
        )
    return metadata_for_scenario_member_v2(operation, member_index=matching_indices[0])


def _synthetic_metadata_for_witness(
    *,
    resolved_operations: tuple[ResolvedScenarioOperationV1, ...],
    operation_by_premise: Mapping[str, ScenarioOperationV2],
    witness_id: str,
    fact_values: tuple[ScenarioValueV1, ...],
) -> tuple[tuple[ScenarioOperationV2, ScenarioMetaV2], ...]:
    matching = tuple(
        resolved for resolved in resolved_operations if witness_id in resolved.synthetic_witness_ids
    )
    if not matching:
        raise ScenarioResolutionErrorV2(
            "Scenario V1 synthetic witness lacks a resolved operation mapping",
            code="SCENARIO_V2_SYNTHETIC_WITNESS_UNMAPPED",
        )
    output: list[tuple[ScenarioOperationV2, ScenarioMetaV2]] = []
    for resolved in matching:
        for premise_id in resolved.premise_ids:
            source = operation_by_premise.get(premise_id)
            if source is None:
                raise ScenarioResolutionErrorV2(
                    "Scenario V1 resolved operation names unknown V2 premise",
                    code="SCENARIO_V2_PREMISE_UNMAPPED",
                )
            output.append((source, _meta_for_resolved_fact(source, fact_values=fact_values)))
    if not output:
        raise ScenarioResolutionErrorV2(
            "Scenario V1 synthetic witness has no V2 source operation",
            code="SCENARIO_V2_SYNTHETIC_WITNESS_UNMAPPED",
        )
    return tuple(output)


def _world_v2_from_v1(
    world: EffectiveWorldV1,
    *,
    v1_resolved: ResolvedScenarioV1,
    operation_by_premise: Mapping[str, ScenarioOperationV2],
    baseline_metadata_by_witness_id: Mapping[str, ScenarioMetaV2],
    operation_evidence: tuple[ResolvedScenarioOperationEvidenceV2, ...],
) -> EffectiveWorldV2:
    if not isinstance(world, EffectiveWorldV1):
        raise ScenarioResolutionErrorV2(
            "world must be EffectiveWorldV1", code="SCENARIO_V2_WORLD_INVALID"
        )
    facts: list[EffectiveWorldFactV2] = []
    for source_fact in world.facts:
        if source_fact.source_kind == "baseline":
            metadata = baseline_metadata_by_witness_id.get(source_fact.witness_id, ScenarioMetaV2())
            facts.append(
                EffectiveWorldFactV2(
                    predicate_id=source_fact.predicate_id,
                    witness_id=source_fact.witness_id,
                    values=source_fact.values,
                    origin="baseline_support",
                    fact_semantics=metadata.fact_semantics,
                    provenance=metadata.provenance,
                    display=metadata.display,
                )
            )
            continue
        source_pairs = _synthetic_metadata_for_witness(
            resolved_operations=v1_resolved.effective_world.operations,
            operation_by_premise=operation_by_premise,
            witness_id=source_fact.witness_id,
            fact_values=source_fact.values,
        )
        # Preserve every normalized source operation until the dedicated merge
        # step can prove equal fact semantics and preserve the witness id.
        for source_operation, metadata in source_pairs:
            facts.append(
                EffectiveWorldFactV2(
                    predicate_id=source_fact.predicate_id,
                    witness_id=source_fact.witness_id,
                    values=source_fact.values,
                    origin="scenario_synthetic",
                    fact_semantics=metadata.fact_semantics,
                    provenance=metadata.provenance,
                    display=metadata.display,
                    premise_ids=(source_operation.premise_id,),
                    scenario_operation_digests=(source_operation.operation_digest,),
                )
            )
    return build_effective_world_v2(
        schema_digest=world.schema_digest,
        base_view_digest=world.base_view_digest,
        admissibility_digest=world.admissibility_digest,
        dependency_predicate_ids=world.dependency_predicate_ids,
        facts=tuple(facts),
        closure_target_digests=tuple(item.target_digest for item in world.closure.targets),
        operation_evidence=operation_evidence,
    )


def resolve_scenario_v2_from_v1(
    *,
    spec: ScenarioSpecV2,
    resolved_v1: ResolvedScenarioV1,
    baseline_metadata_by_witness_id: Mapping[str, ScenarioMetaV2] | None = None,
) -> ResolvedScenarioV2:
    """Lift a trusted V1 scenario resolution into V2 metadata/replay worlds.

    ``resolved_v1`` must already come from the existing trusted Scenario V1
    resolver.  This helper does not re-resolve field/schema conflicts.  It
    only attaches V2 metadata by exact premise/witness links and therefore
    cannot relabel baseline support as a Scenario premise.
    """

    if not isinstance(spec, ScenarioSpecV2) or not isinstance(resolved_v1, ResolvedScenarioV1):
        raise ScenarioResolutionErrorV2(
            "spec/resolved_v1 have invalid protocol types", code="SCENARIO_V2_INPUT_INVALID"
        )
    _assert_v2_spec_wraps_v1(spec, resolved_v1)
    metadata = (
        {} if baseline_metadata_by_witness_id is None else dict(baseline_metadata_by_witness_id)
    )
    baseline_ids = {fact.witness_id for fact in resolved_v1.baseline_world.facts}
    unknown = set(metadata) - baseline_ids
    if unknown:
        raise ScenarioResolutionErrorV2(
            "baseline metadata names uncaptured baseline witness",
            code="SCENARIO_V2_BASELINE_WITNESS_UNKNOWN",
        )
    if not all(isinstance(item, ScenarioMetaV2) for item in metadata.values()):
        raise ScenarioResolutionErrorV2(
            "baseline metadata values must be ScenarioMetaV2",
            code="SCENARIO_V2_BASELINE_METADATA_INVALID",
        )
    operation_by_premise = _v2_operations_by_premise(spec)
    operation_evidence = _operation_evidence_from_v1(
        resolved_v1=resolved_v1,
        operation_by_premise=operation_by_premise,
    )
    baseline_world = _world_v2_from_v1(
        resolved_v1.baseline_world,
        v1_resolved=resolved_v1,
        operation_by_premise=operation_by_premise,
        baseline_metadata_by_witness_id=metadata,
        operation_evidence=operation_evidence,
    )
    effective_world = _world_v2_from_v1(
        resolved_v1.effective_world,
        v1_resolved=resolved_v1,
        operation_by_premise=operation_by_premise,
        baseline_metadata_by_witness_id=metadata,
        operation_evidence=operation_evidence,
    )
    _assert_semantic_bindings_materialized(operation_evidence, effective_world.facts)
    return ResolvedScenarioV2(
        spec=spec,
        baseline_world=baseline_world,
        effective_world=effective_world,
    )


def metadata_for_scenario_member_v2(
    operation: ScenarioOperationV2,
    *,
    member_index: int | None = None,
) -> ScenarioMetaV2:
    """Return the precise metadata lane for one materialized synthetic fact.

    For exact-member operations callers must name a member index.  This is the
    guard that prevents one probability from being accidentally copied onto an
    arbitrary number of members.  For all other operations passing an index is
    rejected; their one operation-level metadata value is returned.
    """

    if not isinstance(operation, ScenarioOperationV2):
        raise ScenarioResolutionErrorV2(
            "operation must be ScenarioOperationV2", code="SCENARIO_V2_OPERATION_INVALID"
        )
    if isinstance(operation.operation, ScenarioSetExactMembersV1):
        if member_index is None:
            raise ScenarioResolutionErrorV2(
                "exact-member operation requires explicit member metadata index",
                code="SCENARIO_V2_MEMBER_METADATA_REQUIRED",
            )
        if isinstance(member_index, bool) or not isinstance(member_index, int):
            raise ScenarioResolutionErrorV2(
                "member metadata index must be int", code="SCENARIO_V2_MEMBER_METADATA_INVALID"
            )
        if not operation.member_meta:
            return ScenarioMetaV2()
        if member_index < 0 or member_index >= len(operation.member_meta):
            raise ScenarioResolutionErrorV2(
                "member metadata index is outside exact-member operation",
                code="SCENARIO_V2_MEMBER_METADATA_INVALID",
            )
        return operation.member_meta[member_index]
    if member_index is not None:
        raise ScenarioResolutionErrorV2(
            "member metadata index is only valid for exact-member operation",
            code="SCENARIO_V2_MEMBER_METADATA_INVALID",
        )
    return operation.meta


def _merge_display(left: ScenarioDisplayV2, right: ScenarioDisplayV2) -> ScenarioDisplayV2:
    if left.note is not None and right.note is not None and left.note != right.note:
        raise ScenarioResolutionErrorV2(
            "same synthetic tuple has incompatible display notes",
            code="SCENARIO_V2_DISPLAY_CONFLICT",
        )
    return ScenarioDisplayV2(
        note=left.note if left.note is not None else right.note,
        labels=tuple(sorted(set(left.labels) | set(right.labels))),
    )


def merge_scenario_synthetic_facts_v2(
    facts: tuple[EffectiveWorldFactV2, ...],
) -> tuple[EffectiveWorldFactV2, ...]:
    """Merge same-tuple same-semantics Scenario support without relabeling it.

    The caller must supply a stable synthetic witness id for a tuple before
    calling this function.  Differing ids are rejected rather than choosing
    one: a V2 metadata merge may enrich provenance/display evidence but must
    never change witness identity.  Baseline support is left untouched so it
    cannot accidentally become a Scenario source.
    """

    if not isinstance(facts, tuple) or not all(
        isinstance(item, EffectiveWorldFactV2) for item in facts
    ):
        raise ScenarioResolutionErrorV2(
            "facts must be EffectiveWorldFactV2 tuple", code="SCENARIO_V2_FACTS_INVALID"
        )
    grouped: dict[tuple[str, tuple[tuple[str, object], ...]], list[EffectiveWorldFactV2]] = {}
    passthrough: list[EffectiveWorldFactV2] = []
    for fact in facts:
        if fact.origin == "scenario_synthetic":
            grouped.setdefault(fact.tuple_identity, []).append(fact)
        else:
            passthrough.append(fact)
    merged: list[EffectiveWorldFactV2] = list(passthrough)
    for key in sorted(grouped, key=repr):
        group = grouped[key]
        first = group[0]
        semantics = {
            None if item.fact_semantics is None else item.fact_semantics.semantics_digest
            for item in group
        }
        if len(semantics) != 1:
            raise ScenarioResolutionErrorV2(
                "same synthetic tuple has conflicting fact semantics",
                code="SCENARIO_V2_SEMANTIC_CONFLICT",
            )
        witness_ids = {item.witness_id for item in group}
        if len(witness_ids) != 1:
            raise ScenarioResolutionErrorV2(
                "same synthetic tuple has non-identical witness identities",
                code="SCENARIO_V2_SYNTHETIC_WITNESS_CONFLICT",
            )
        provenance = canonical_provenance_refs_v1(
            tuple(reference for item in group for reference in item.provenance),
            field_name="merged Scenario V2 provenance",
        )
        display = first.display
        for item in group[1:]:
            display = _merge_display(display, item.display)
        merged.append(
            EffectiveWorldFactV2(
                predicate_id=first.predicate_id,
                witness_id=first.witness_id,
                values=first.values,
                origin="scenario_synthetic",
                fact_semantics=first.fact_semantics,
                provenance=provenance,
                display=display,
                premise_ids=tuple(
                    sorted({premise_id for item in group for premise_id in item.premise_ids})
                ),
                scenario_operation_digests=tuple(
                    sorted({digest for item in group for digest in item.scenario_operation_digests})
                ),
            )
        )
    return tuple(sorted(merged, key=lambda item: item.evidence_fact_digest))


def build_effective_world_v2(
    *,
    schema_digest: str,
    base_view_digest: str,
    admissibility_digest: str,
    dependency_predicate_ids: tuple[str, ...],
    facts: tuple[EffectiveWorldFactV2, ...],
    closure_target_digests: tuple[str, ...] = (),
    operation_evidence: tuple[ResolvedScenarioOperationEvidenceV2, ...] = (),
) -> EffectiveWorldV2:
    """Normalize Scenario support metadata and seal one independently replayable world."""

    return EffectiveWorldV2(
        schema_digest=schema_digest,
        base_view_digest=base_view_digest,
        admissibility_digest=admissibility_digest,
        dependency_predicate_ids=dependency_predicate_ids,
        facts=merge_scenario_synthetic_facts_v2(facts),
        closure_target_digests=closure_target_digests,
        operation_evidence=operation_evidence,
    )


def world_has_probabilistic_semantics_v2(world: EffectiveWorldV2) -> bool:
    """Whether an explicit V2 ProbLog point-semantics profile is required."""

    if not isinstance(world, EffectiveWorldV2):
        raise ScenarioResolutionErrorV2(
            "world must be EffectiveWorldV2", code="SCENARIO_V2_WORLD_INVALID"
        )
    return any(item.fact_semantics is not None for item in world.facts)


def scenario_requires_probabilistic_semantics_v2(spec: ScenarioSpecV2) -> bool:
    """Inspect a not-yet-materialized V2 Scenario request without evaluating it."""

    if not isinstance(spec, ScenarioSpecV2):
        raise ScenarioResolutionErrorV2(
            "spec must be ScenarioSpecV2", code="SCENARIO_V2_SPEC_INVALID"
        )
    return any(
        item.meta.fact_semantics is not None
        or any(member.fact_semantics is not None for member in item.member_meta)
        for item in spec.operations
    )


def effective_world_v2_relation(
    world: EffectiveWorldV2,
) -> Mapping[str, tuple[EffectiveWorldFactV2, ...]]:
    """Return a sealed relation handoff for a future materializer.

    This only groups already captured facts.  It deliberately does not lower
    probability semantics or execute a closure/negation rule.
    """

    if not isinstance(world, EffectiveWorldV2):
        raise ScenarioResolutionErrorV2(
            "world must be EffectiveWorldV2", code="SCENARIO_V2_WORLD_INVALID"
        )
    grouped: dict[str, list[EffectiveWorldFactV2]] = {
        predicate_id: [] for predicate_id in world.dependency_predicate_ids
    }
    for fact in world.facts:
        grouped[fact.predicate_id].append(fact)
    return MappingProxyType(
        {
            predicate_id: tuple(sorted(facts, key=lambda item: item.evidence_fact_digest))
            for predicate_id, facts in sorted(grouped.items())
        }
    )


class ScenarioBuilderV2:
    """Small SDK-facing builder over V1's ground operation grammar.

    It intentionally takes resolved ``EntityRef``/``FieldPath``/typed values;
    a higher SDK façade may resolve ergonomic model fields and Python values
    before calling it.  Crucially, every public ``meta=`` flows through
    :func:`lower_scenario_meta_v2` immediately and never becomes ledger meta.
    """

    def __init__(self) -> None:
        self._operations: list[ScenarioOperationV2] = []

    @property
    def operations(self) -> tuple[ScenarioOperationV2, ...]:
        return tuple(self._operations)

    def add_operation(
        self,
        operation: object,
        *,
        meta: object = None,
        member_meta: tuple[object, ...] = (),
    ) -> ScenarioBuilderV2:
        if not isinstance(member_meta, tuple):
            raise ScenarioResolutionErrorV2(
                "member_meta must be tuple", code="SCENARIO_V2_MEMBER_METADATA_INVALID"
            )
        self._operations.append(
            ScenarioOperationV2(
                operation=operation,  # type: ignore[arg-type]
                meta=lower_scenario_meta_v2(meta),
                member_meta=tuple(lower_scenario_meta_v2(item) for item in member_meta),
            )
        )
        return self

    def set(
        self,
        *,
        premise_id: str,
        entity: EntityRef,
        field: FieldPath,
        value: ScenarioValueV1,
        meta: object = None,
        origin_refs: tuple[str, ...] = (),
    ) -> ScenarioBuilderV2:
        return self.add_operation(
            ScenarioSetEffectiveValueV1(
                premise_id=premise_id,
                entity=entity,
                field=field,
                value=value,
                origin_refs=origin_refs,
            ),
            meta=meta,
        )

    def add(
        self,
        *,
        premise_id: str,
        entity: EntityRef,
        field: FieldPath,
        value: ScenarioValueV1,
        meta: object = None,
        origin_refs: tuple[str, ...] = (),
    ) -> ScenarioBuilderV2:
        return self.add_operation(
            ScenarioEnsureMemberV1(
                premise_id=premise_id,
                entity=entity,
                field=field,
                value=value,
                origin_refs=origin_refs,
            ),
            meta=meta,
        )

    def clear(
        self,
        *,
        premise_id: str,
        entity: EntityRef,
        field: FieldPath,
        meta: object = None,
        origin_refs: tuple[str, ...] = (),
    ) -> ScenarioBuilderV2:
        return self.add_operation(
            ScenarioWithoutFieldV1(
                premise_id=premise_id,
                entity=entity,
                field=field,
                origin_refs=origin_refs,
            ),
            meta=meta,
        )

    def remove(
        self,
        *,
        premise_id: str,
        entity: EntityRef,
        field: FieldPath,
        value: ScenarioValueV1,
        meta: object = None,
        origin_refs: tuple[str, ...] = (),
    ) -> ScenarioBuilderV2:
        return self.add_operation(
            ScenarioWithoutValueV1(
                premise_id=premise_id,
                entity=entity,
                field=field,
                value=value,
                origin_refs=origin_refs,
            ),
            meta=meta,
        )

    def exact_members(
        self,
        *,
        premise_id: str,
        entity: EntityRef,
        field: FieldPath,
        values: tuple[ScenarioValueV1, ...],
        meta: object = None,
        member_meta: tuple[object, ...] = (),
        origin_refs: tuple[str, ...] = (),
    ) -> ScenarioBuilderV2:
        if not isinstance(member_meta, tuple):
            raise ScenarioResolutionErrorV2(
                "member_meta must be tuple", code="SCENARIO_V2_MEMBER_METADATA_INVALID"
            )
        if member_meta and len(member_meta) != len(values):
            raise ScenarioResolutionErrorV2(
                "member_meta must cover every declared exact member",
                code="SCENARIO_V2_MEMBER_METADATA_INVALID",
            )
        # ScenarioSetExactMembersV1 canonicalizes its values.  Carry the
        # aligned metadata through that same ordering rather than making the
        # caller know a private value-sort convention.
        if member_meta:
            pairs = sorted(
                zip(values, member_meta, strict=True),
                key=lambda item: (item[0].tag, str(item[0].value)),
            )
            canonical_member_meta = tuple(lower_scenario_meta_v2(item[1]) for item in pairs)
        else:
            canonical_member_meta = ()
        return self.add_operation(
            ScenarioSetExactMembersV1(
                premise_id=premise_id,
                entity=entity,
                field=field,
                values=values,
                origin_refs=origin_refs,
            ),
            meta=meta,
            member_meta=canonical_member_meta,
        )

    def build(self) -> ScenarioSpecV2:
        return ScenarioSpecV2(operations=tuple(self._operations))


__all__ = [
    "ResolvedScenarioV2",
    "ScenarioBuilderV2",
    "ScenarioResolutionErrorV2",
    "build_effective_world_v2",
    "effective_world_v2_relation",
    "merge_scenario_synthetic_facts_v2",
    "metadata_for_scenario_member_v2",
    "resolve_scenario_v2_from_v1",
    "scenario_requires_probabilistic_semantics_v2",
    "world_has_probabilistic_semantics_v2",
]
