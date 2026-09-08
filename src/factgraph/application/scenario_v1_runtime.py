"""Trusted resolver for the narrow, portable Scenario v1 algebra.

The resolver works over a caller-supplied *projected relation*.  It deliberately
does not reach into a ledger, invoke a premise filter, lower a ``NotAtom``, or
rewrite a Policy.  This leaves a clean handoff for every engine:

``full projected relation -> EvidenceScope admission -> dependency subset ->
resolve_scenario_v1 -> sealed EffectiveWorldV1 -> engine-specific execution``.

``without_*`` is implemented as removal from the sealed effective relation plus
an exact local closure target.  ``EvidenceScopeV1`` merely removes evidence;
it can never create such a closure target.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, TypeAlias, cast

from factgraph.core.store._support import ProjectedFact

from .protocol.common import ProtocolShapeError
from .protocol.scenario_v1 import (
    ClosureScopeV1,
    EffectiveWorldFactV1,
    EffectiveWorldV1,
    EvidenceScopeV1,
    ExactLocalClosureTargetV1,
    ResolvedScenarioOperationV1,
    ResolvedScenarioV1,
    ScenarioCreateEphemeralEntityV1,
    ScenarioEnsureMemberV1,
    ScenarioEnsureRelationV1,
    ScenarioOperationV1,
    ScenarioSetEffectiveValueV1,
    ScenarioSetExactMembersV1,
    ScenarioSpecV1,
    ScenarioValueTagV1,
    ScenarioValueV1,
    ScenarioWithoutAssertionV1,
    ScenarioWithoutEntityV1,
    ScenarioWithoutFieldV1,
    ScenarioWithoutRelationV1,
    ScenarioWithoutValueV1,
    _token,
)
from .protocol.schema_runtime import EntityRef, FieldPath
from .schema_runtime import (
    EntityTypeInfo,
    PredicateInfo,
    SchemaIndex,
    encode_entity_ref,
    entity_info,
    entity_type_from_ref,
    field_predicate,
    is_scenario_relation_predicate_v1,
    materialize_identity,
)
from .value_validation import FieldValueValidationError, validate_field_value

ProjectedRelationV1: TypeAlias = Mapping[str, Sequence[ProjectedFact]]
ImmutableProjectedRelationV1: TypeAlias = Mapping[str, tuple[ProjectedFact, ...]]


class ScenarioResolutionErrorV1(ValueError):
    """A fail-closed scenario resolution error with a stable machine code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EvidenceScopeApplicationV1:
    """Result of evidence admission, intentionally without a closure field."""

    scope: EvidenceScopeV1
    relation: ImmutableProjectedRelationV1 = field(repr=False, compare=False)
    admissibility_digest: str
    excluded_assertion_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scope, EvidenceScopeV1):
            raise ProtocolShapeError("EvidenceScopeApplicationV1.scope must be EvidenceScopeV1")
        _require_relation(self.relation, code="EVIDENCE_SCOPE_RELATION_INVALID")
        if not isinstance(
            self.admissibility_digest, str
        ) or not self.admissibility_digest.startswith("sha256:"):
            raise ProtocolShapeError(
                "EvidenceScopeApplicationV1.admissibility_digest must be sha256 token"
            )
        if tuple(sorted(set(self.excluded_assertion_ids))) != self.excluded_assertion_ids:
            raise ProtocolShapeError(
                "EvidenceScopeApplicationV1.excluded_assertion_ids must be canonical"
            )


def _require_relation(relation: object, *, code: str) -> None:
    if not isinstance(relation, Mapping):
        raise ScenarioResolutionErrorV1("projected relation must be a mapping", code=code)
    seen_witnesses: set[str] = set()
    for predicate_id, rows in relation.items():
        if not isinstance(predicate_id, str) or not predicate_id:
            raise ScenarioResolutionErrorV1("projected relation predicate id is invalid", code=code)
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            raise ScenarioResolutionErrorV1("projected relation rows must be a sequence", code=code)
        if not all(isinstance(row, ProjectedFact) for row in rows):
            raise ScenarioResolutionErrorV1(
                "projected relation rows must be ProjectedFact", code=code
            )
        for row in rows:
            if row.asrt_id in seen_witnesses:
                raise ScenarioResolutionErrorV1(
                    f"projected relation repeats assertion id {row.asrt_id!r}",
                    code="SCENARIO_ASSERTION_DUPLICATE",
                )
            seen_witnesses.add(row.asrt_id)


def _freeze_relation(relation: ProjectedRelationV1) -> ImmutableProjectedRelationV1:
    _require_relation(relation, code="SCENARIO_RELATION_INVALID")
    return MappingProxyType(
        {
            predicate_id: tuple(
                ProjectedFact(asrt_id=row.asrt_id, fact_tuple=tuple(row.fact_tuple)) for row in rows
            )
            for predicate_id, rows in sorted(relation.items())
        }
    )


def apply_evidence_scope_v1(
    relation: ProjectedRelationV1,
    scope: EvidenceScopeV1,
) -> EvidenceScopeApplicationV1:
    """Apply admission exclusion without claiming any absence or closure.

    The operation is useful before a Query narrows a full-schema projected
    relation to its dependency predicates.  An unknown assertion id is rejected
    rather than silently turning a typo into a no-op admission policy.
    """

    if not isinstance(scope, EvidenceScopeV1):
        raise ScenarioResolutionErrorV1(
            "scope must be EvidenceScopeV1", code="EVIDENCE_SCOPE_INVALID"
        )
    frozen = _freeze_relation(relation)
    available = {row.asrt_id for rows in frozen.values() for row in rows}
    unknown = sorted(set(scope.ignored_assertion_ids) - available)
    if unknown:
        raise ScenarioResolutionErrorV1(
            f"evidence scope names unknown assertion ids: {unknown!r}",
            code="EVIDENCE_SCOPE_ASSERTION_UNKNOWN",
        )
    ignored = frozenset(scope.ignored_assertion_ids)
    filtered = MappingProxyType(
        {
            predicate_id: tuple(row for row in rows if row.asrt_id not in ignored)
            for predicate_id, rows in frozen.items()
        }
    )
    digest = _token(
        "evidence_scope_application_v1",
        {
            "scope_digest": scope.scope_digest,
            "included": tuple(
                (predicate_id, tuple(row.asrt_id for row in rows))
                for predicate_id, rows in filtered.items()
            ),
        },
    )
    return EvidenceScopeApplicationV1(
        scope=scope,
        relation=filtered,
        admissibility_digest=digest,
        excluded_assertion_ids=scope.ignored_assertion_ids,
    )


def select_dependency_relation_v1(
    relation: ProjectedRelationV1,
    *,
    dependency_predicate_ids: tuple[str, ...],
) -> ImmutableProjectedRelationV1:
    """Make a sealed dependency subset after evidence admission.

    The caller must pass the complete Query dependency set.  Missing predicates
    are an error even when they would be empty: otherwise an omitted relation
    could be confused with a relation proven empty by Scenario.
    """

    frozen = _freeze_relation(relation)
    if not isinstance(dependency_predicate_ids, tuple) or not dependency_predicate_ids:
        raise ScenarioResolutionErrorV1(
            "dependency_predicate_ids must be a non-empty tuple", code="SCENARIO_DEPENDENCY_INVALID"
        )
    if tuple(sorted(set(dependency_predicate_ids))) != dependency_predicate_ids:
        raise ScenarioResolutionErrorV1(
            "dependency_predicate_ids must be sorted unique", code="SCENARIO_DEPENDENCY_INVALID"
        )
    missing = tuple(
        predicate_id for predicate_id in dependency_predicate_ids if predicate_id not in frozen
    )
    if missing:
        raise ScenarioResolutionErrorV1(
            f"projected relation omits required dependency predicates: {missing!r}",
            code="SCENARIO_DEPENDENCY_MISSING",
        )
    return MappingProxyType(
        {predicate_id: frozen[predicate_id] for predicate_id in dependency_predicate_ids}
    )


def scenario_dependency_predicate_ids_v1(
    spec: ScenarioSpecV1,
    *,
    schema_index: SchemaIndex,
    admitted_relation: ProjectedRelationV1,
) -> tuple[str, ...]:
    """Return the finite extra input inventory required by a Scenario v1.

    Query compilation provides the predicates a Rule/Policy reads.  Scenario
    resolution has a second, deliberately explicit dependency surface: an
    entity mutation must see its ``:exists`` witness; an ephemeral entity
    needs its complete identity anchors; relation arguments must be grounded
    against sealed existence facts; and the SDK/debug ``without_assertion``
    form must find its one admitted witness before the view is narrowed.

    This helper consumes only the caller-provided admitted projected relation.
    It never opens a Ledger or chooses ``latest`` facts.  Consequently the
    GoalPlan runtime can union its result with program dependencies, capture
    one finite world, and still reject any target not visible in that world.
    """

    if not isinstance(spec, ScenarioSpecV1):
        raise ScenarioResolutionErrorV1("spec must be ScenarioSpecV1", code="SCENARIO_SPEC_INVALID")
    if not isinstance(schema_index, SchemaIndex):
        raise ScenarioResolutionErrorV1(
            "schema_index must be SchemaIndex", code="SCENARIO_SCHEMA_INVALID"
        )
    relation = _freeze_relation(admitted_relation)
    required: set[str] = set()

    def add_entity_anchors(entity: EntityRef, *, identities: bool) -> str:
        _canonical, entity_ref, info = _canonical_entity_ref(entity, index=schema_index)
        required.add(info.exists_predicate_id)
        if identities:
            required.update(predicate.pred_id for predicate in info.identity_predicates.values())
        return entity_ref

    def add_encoded_entity_visibility(entity_ref: str) -> None:
        entity_type = entity_type_from_ref(entity_ref)
        if entity_type is None:
            raise ScenarioResolutionErrorV1(
                "relation entity reference is not a canonical idref",
                code="SCENARIO_RELATION_ENTITY_REFERENCE_INVALID",
            )
        try:
            required.add(entity_info(schema_index, entity_type).exists_predicate_id)
        except ValueError as exc:
            raise ScenarioResolutionErrorV1(
                "relation entity reference names an unknown schema entity",
                code="SCENARIO_RELATION_ENTITY_REFERENCE_INVALID",
            ) from exc

    for operation in spec.operations:
        if isinstance(operation, ScenarioCreateEphemeralEntityV1):
            add_entity_anchors(operation.entity, identities=True)
            continue
        if isinstance(operation, ScenarioWithoutEntityV1):
            target_ref = add_entity_anchors(operation.entity, identities=False)
            # Entity removal is exact only over the finite Scenario world.  Add
            # every admitted schema predicate that actually mentions the
            # entity, rather than pretending an unrelated, uncaptured field is
            # closed or reading the Store again after capture.
            for predicate_id, rows in relation.items():
                domains = _predicate_domains(schema_index, predicate_id)
                if any(
                    any(
                        domain == "entity_ref" and value == target_ref
                        for domain, value in zip(domains, row.fact_tuple, strict=True)
                    )
                    for row in rows
                ):
                    required.add(predicate_id)
            continue
        if isinstance(operation, ScenarioWithoutAssertionV1):
            matches = tuple(
                predicate_id
                for predicate_id, rows in relation.items()
                for row in rows
                if row.asrt_id == operation.assertion_id
            )
            if len(matches) != 1:
                raise ScenarioResolutionErrorV1(
                    f"Scenario assertion {operation.assertion_id!r} is not uniquely admitted",
                    code="SCENARIO_ASSERTION_NOT_VISIBLE",
                )
            required.add(matches[0])
            continue
        if isinstance(operation, (ScenarioEnsureRelationV1, ScenarioWithoutRelationV1)):
            intent = _relation_intent(operation, index=schema_index)
            assert intent.info is not None
            required.add(intent.info.pred_id)
            if isinstance(operation, ScenarioEnsureRelationV1):
                for value in operation.values:
                    if value.tag == "entity_ref":
                        raw = value.to_raw()
                        assert isinstance(raw, str)
                        add_encoded_entity_visibility(raw)
            continue
        # The remaining operation family is a protected typed field operation.
        assert isinstance(
            operation,
            (
                ScenarioSetEffectiveValueV1,
                ScenarioEnsureMemberV1,
                ScenarioSetExactMembersV1,
                ScenarioWithoutFieldV1,
                ScenarioWithoutValueV1,
            ),
        )
        field = _field_info(operation.field, index=schema_index)
        required.add(field.pred_id)
        add_entity_anchors(operation.entity, identities=False)
    return tuple(sorted(required))


def effective_world_to_relation_v1(world: EffectiveWorldV1) -> ImmutableProjectedRelationV1:
    """Reconstruct the sealed exact relation without a Store or evaluator.

    This is the portable handoff for native, Soufflé, and ProbLog adapters.  It
    is intentionally just a relation reconstruction: it does not execute
    ``ClosureScopeV1`` as generic negation and does not add a replay contract.
    """

    if not isinstance(world, EffectiveWorldV1):
        raise ScenarioResolutionErrorV1(
            "world must be EffectiveWorldV1", code="SCENARIO_WORLD_INVALID"
        )
    try:
        resealed = EffectiveWorldV1(
            schema_digest=world.schema_digest,
            base_view_digest=world.base_view_digest,
            admissibility_digest=world.admissibility_digest,
            dependency_predicate_ids=world.dependency_predicate_ids,
            facts=world.facts,
            operations=world.operations,
            closure=world.closure,
        )
    except ProtocolShapeError as exc:
        raise ScenarioResolutionErrorV1(str(exc), code="SCENARIO_WORLD_INVALID") from exc
    if (
        resealed.relation_digest != world.relation_digest
        or resealed.world_digest != world.world_digest
    ):
        raise ScenarioResolutionErrorV1(
            "effective world digest does not match its contents",
            code="SCENARIO_WORLD_DIGEST_MISMATCH",
        )
    result: dict[str, list[ProjectedFact]] = {
        predicate_id: [] for predicate_id in world.dependency_predicate_ids
    }
    for fact in world.facts:
        result[fact.predicate_id].append(
            ProjectedFact(asrt_id=fact.witness_id, fact_tuple=_canonical_raw_tuple(fact.values))
        )
    return MappingProxyType({predicate_id: tuple(rows) for predicate_id, rows in result.items()})


def _sha_token(value: str, *, name: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ScenarioResolutionErrorV1(
            f"{name} must be sha256 token", code="SCENARIO_DIGEST_INVALID"
        )
    suffix = value[len("sha256:") :]
    if len(suffix) != 64 or any(char not in "0123456789abcdef" for char in suffix):
        raise ScenarioResolutionErrorV1(
            f"{name} must be sha256 token", code="SCENARIO_DIGEST_INVALID"
        )


def _canonical_entity_ref(
    entity: EntityRef, *, index: SchemaIndex
) -> tuple[EntityRef, str, EntityTypeInfo]:
    try:
        identity = materialize_identity(entity.entity_type, dict(entity.identity), index=index)
        canonical = EntityRef(entity.entity_type, identity)
        return (
            canonical,
            encode_entity_ref(canonical, index=index),
            entity_info(index, entity.entity_type),
        )
    except ValueError as exc:
        code = getattr(exc, "code", "SCENARIO_ENTITY_REFERENCE_INVALID")
        raise ScenarioResolutionErrorV1(str(exc), code=code) from exc


def _field_info(field: FieldPath, *, index: SchemaIndex) -> PredicateInfo:
    try:
        info = field_predicate(index, field.entity_type, field.field_name)
    except ValueError as exc:
        raise ScenarioResolutionErrorV1(
            str(exc), code=getattr(exc, "code", "SCENARIO_FIELD_UNKNOWN")
        ) from exc
    if info.is_identity_field or info.is_entity_exists:
        raise ScenarioResolutionErrorV1(
            f"Scenario v1 cannot mutate identity/existence field {info.pred_id}",
            code="SCENARIO_PROTECTED_FIELD",
        )
    if info.value_type_domain is None:
        raise ScenarioResolutionErrorV1(
            f"field {info.pred_id} has no value type domain", code="SCENARIO_FIELD_DOMAIN_UNKNOWN"
        )
    return info


def _checked_value(value: ScenarioValueV1, *, info: PredicateInfo) -> ScenarioValueV1:
    if info.value_type_domain != value.tag:
        raise ScenarioResolutionErrorV1(
            f"Scenario value tag {value.tag!r} does not match {info.pred_id} domain {info.value_type_domain!r}",
            code="SCENARIO_VALUE_DOMAIN_MISMATCH",
        )
    try:
        validate_field_value(value.to_raw(), pred_info=info)
    except FieldValueValidationError as exc:
        raise ScenarioResolutionErrorV1(str(exc), code=exc.code) from exc
    return value


def _predicate_domains(index: SchemaIndex, predicate_id: str) -> tuple[str, ...]:
    for predicate in index.schema_ir.get("predicates", []):
        if isinstance(predicate, dict) and predicate.get("pred_id") == predicate_id:
            arg_specs = predicate.get("arg_specs")
            if not isinstance(arg_specs, list) or not arg_specs:
                break
            domains: list[str] = []
            for spec in arg_specs:
                domain = spec.get("type_domain") if isinstance(spec, dict) else None
                if not isinstance(domain, str) or domain not in {
                    "string",
                    "int",
                    "float64",
                    "bool",
                    "bytes",
                    "time",
                    "uuid",
                    "entity_ref",
                }:
                    break
                domains.append(domain)
            else:
                return tuple(domains)
    raise ScenarioResolutionErrorV1(
        f"projected predicate {predicate_id!r} has no supported schema signature",
        code="SCENARIO_RELATION_SCHEMA_UNKNOWN",
    )


def _typed_facts(
    relation: ImmutableProjectedRelationV1,
    *,
    index: SchemaIndex,
    scenario_witness_ids: frozenset[str] = frozenset(),
) -> tuple[EffectiveWorldFactV1, ...]:
    facts: list[EffectiveWorldFactV1] = []
    for predicate_id, rows in relation.items():
        domains = _predicate_domains(index, predicate_id)
        for row in rows:
            if len(row.fact_tuple) != len(domains):
                raise ScenarioResolutionErrorV1(
                    f"projected row arity for {predicate_id!r} is inconsistent with schema",
                    code="SCENARIO_RELATION_ARITY_MISMATCH",
                )
            try:
                values = tuple(
                    ScenarioValueV1.from_raw(cast(ScenarioValueTagV1, domain), value)
                    for domain, value in zip(domains, row.fact_tuple, strict=True)
                )
            except ProtocolShapeError as exc:
                raise ScenarioResolutionErrorV1(
                    str(exc), code="SCENARIO_RELATION_VALUE_INVALID"
                ) from exc
            facts.append(
                EffectiveWorldFactV1(
                    predicate_id=predicate_id,
                    witness_id=row.asrt_id,
                    values=values,
                    source_kind="scenario" if row.asrt_id in scenario_witness_ids else "baseline",
                )
            )
    return tuple(facts)


@dataclass(frozen=True)
class _Intent:
    kind: str
    entity_ref: str | None
    entity_type: str | None
    field: FieldPath | None
    info: PredicateInfo | None
    values: tuple[ScenarioValueV1, ...]
    premise_ids: tuple[str, ...]
    origin_refs: tuple[str, ...]
    identity_values: tuple[tuple[str, ScenarioValueV1], ...] = ()
    # ``without_assertion`` deliberately has no entity target.  Keep its
    # opaque admitted-witness reference in a separate slot rather than
    # overloading ``entity_ref``: doing the latter makes a resolved assertion
    # removal look like an entity-scoped operation and defeats protocol shape
    # validation.
    assertion_id: str | None = None


def _op_origin(operation: ScenarioOperationV1) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (operation.premise_id,), operation.origin_refs


def _field_intent(operation: ScenarioOperationV1, *, index: SchemaIndex) -> _Intent:
    assert not isinstance(
        operation,
        (
            ScenarioCreateEphemeralEntityV1,
            ScenarioEnsureRelationV1,
            ScenarioWithoutRelationV1,
            ScenarioWithoutEntityV1,
            ScenarioWithoutAssertionV1,
        ),
    )
    _, entity_ref, _ = _canonical_entity_ref(operation.entity, index=index)
    info = _field_info(operation.field, index=index)
    premise_ids, origin_refs = _op_origin(operation)
    values: tuple[ScenarioValueV1, ...]
    if isinstance(operation, ScenarioSetEffectiveValueV1):
        if info.cardinality != "single":
            raise ScenarioResolutionErrorV1(
                "set_effective_value requires single field", code="SCENARIO_CARDINALITY_MISMATCH"
            )
        values = (_checked_value(operation.value, info=info),)
        kind = "set_effective_value"
    elif isinstance(operation, ScenarioEnsureMemberV1):
        if info.cardinality != "multi":
            raise ScenarioResolutionErrorV1(
                "ensure_member requires multi field", code="SCENARIO_CARDINALITY_MISMATCH"
            )
        values = (_checked_value(operation.value, info=info),)
        kind = "ensure_member"
    elif isinstance(operation, ScenarioSetExactMembersV1):
        if info.cardinality != "multi":
            raise ScenarioResolutionErrorV1(
                "set_exact_members requires multi field", code="SCENARIO_CARDINALITY_MISMATCH"
            )
        values = tuple(_checked_value(value, info=info) for value in operation.values)
        kind = "set_exact_members"
    elif isinstance(operation, ScenarioWithoutFieldV1):
        values = ()
        kind = "without_field"
    elif isinstance(operation, ScenarioWithoutValueV1):
        values = (_checked_value(operation.value, info=info),)
        kind = "without_value"
    else:  # pragma: no cover - closed union guard
        raise ScenarioResolutionErrorV1(
            "unsupported Scenario v1 operation", code="SCENARIO_OPERATION_UNKNOWN"
        )
    return _Intent(
        kind,
        entity_ref,
        operation.entity.entity_type,
        operation.field,
        info,
        values,
        premise_ids,
        origin_refs,
    )


def _schema_predicate_record(index: SchemaIndex, predicate_id: str) -> dict[str, Any]:
    for predicate in index.schema_ir.get("predicates", []):
        if isinstance(predicate, dict) and predicate.get("pred_id") == predicate_id:
            return predicate
    raise ScenarioResolutionErrorV1(
        f"predicate {predicate_id!r} is not declared by the active schema",
        code="SCENARIO_RELATION_SCHEMA_UNKNOWN",
    )


def _relation_group_key_indexes(index: SchemaIndex, predicate_id: str) -> tuple[int, ...]:
    """Return the schema-owned logical key for one extensional relation."""

    record = _schema_predicate_record(index, predicate_id)
    raw = record.get("group_key_indexes")
    if not isinstance(raw, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in raw
    ):
        raise ScenarioResolutionErrorV1(
            f"relation {predicate_id!r} has invalid group-key contract",
            code="SCENARIO_RELATION_SCHEMA_UNKNOWN",
        )
    arity = len(_predicate_domains(index, predicate_id))
    indexes = tuple(raw)
    if (
        not indexes
        or any(item < 0 or item >= arity for item in indexes)
        or tuple(sorted(set(indexes))) != indexes
    ):
        raise ScenarioResolutionErrorV1(
            f"relation {predicate_id!r} has invalid group-key contract",
            code="SCENARIO_RELATION_SCHEMA_UNKNOWN",
        )
    return indexes


def _visible_entity_refs(
    relation: Mapping[str, Sequence[ProjectedFact]], *, index: SchemaIndex
) -> frozenset[str]:
    """Resolve the finite entity universe exposed by this dependency slice.

    A relation operation may not fabricate a reference to an entity whose
    existence is outside the sealed Scenario input.  Requiring every relevant
    ``:exists`` relation to be present is intentionally stricter than looking
    at an arbitrary idref string: it prevents a later engine from acquiring a
    missing entity through a live Store fallback.
    """

    visible: set[str] = set()
    for info in index.entities.values():
        rows = relation.get(info.exists_predicate_id)
        if rows is None:
            continue
        for row in rows:
            if len(row.fact_tuple) != 1 or not isinstance(row.fact_tuple[0], str):
                raise ScenarioResolutionErrorV1(
                    f"entity visibility predicate {info.exists_predicate_id!r} is malformed",
                    code="SCENARIO_ENTITY_VISIBILITY_INVALID",
                )
            entity_ref = row.fact_tuple[0]
            if entity_type_from_ref(entity_ref) != info.entity_type:
                raise ScenarioResolutionErrorV1(
                    f"entity visibility predicate {info.exists_predicate_id!r} has wrong entity type",
                    code="SCENARIO_ENTITY_VISIBILITY_INVALID",
                )
            visible.add(entity_ref)
    return frozenset(visible)


def _assert_relation_entities_visible(
    intents: Sequence[_Intent],
    *,
    relation: Mapping[str, Sequence[ProjectedFact]],
    ephemeral_entity_refs: frozenset[str],
    index: SchemaIndex,
) -> None:
    """Require every entity-ref tuple value to name a sealed visible entity."""

    visible = _visible_entity_refs(relation, index=index) | ephemeral_entity_refs
    for intent in intents:
        for value in intent.values:
            if value.tag != "entity_ref":
                continue
            raw = value.to_raw()
            if not isinstance(raw, str) or entity_type_from_ref(raw) is None:
                raise ScenarioResolutionErrorV1(
                    "relation entity reference is not a canonical idref",
                    code="SCENARIO_RELATION_ENTITY_REFERENCE_INVALID",
                )
            entity_type = entity_type_from_ref(raw)
            assert entity_type is not None
            try:
                exists_predicate = entity_info(index, entity_type).exists_predicate_id
            except ValueError as exc:
                raise ScenarioResolutionErrorV1(
                    "relation entity reference names an unknown schema entity",
                    code="SCENARIO_RELATION_ENTITY_REFERENCE_INVALID",
                ) from exc
            if raw not in ephemeral_entity_refs and exists_predicate not in relation:
                raise ScenarioResolutionErrorV1(
                    f"relation entity {raw!r} lacks a sealed existence dependency",
                    code="SCENARIO_RELATION_ENTITY_VISIBILITY_UNAVAILABLE",
                )
            if raw not in visible:
                raise ScenarioResolutionErrorV1(
                    f"relation entity {raw!r} is not visible in this Scenario world",
                    code="SCENARIO_RELATION_ENTITY_NOT_VISIBLE",
                )


def _assert_relation_cardinality(
    intents: Sequence[_Intent],
    *,
    relation: Mapping[str, Sequence[ProjectedFact]],
    index: SchemaIndex,
) -> None:
    """Reject relation replacement ambiguity instead of inventing a priority.

    ``ENSURE_RELATION`` is add-or-no-op.  It never secretly becomes a replace
    when a schema's single-cardinality group already has another tuple.
    """

    by_predicate: dict[str, list[_Intent]] = {}
    for intent in intents:
        if intent.kind == "ensure_relation" and intent.info is not None:
            by_predicate.setdefault(intent.info.pred_id, []).append(intent)
    for predicate_id, group_intents in by_predicate.items():
        info = group_intents[0].info
        assert info is not None
        if info.cardinality != "single":
            continue
        key_indexes = _relation_group_key_indexes(index, predicate_id)
        if not key_indexes:
            raise ScenarioResolutionErrorV1(
                f"single relation {predicate_id!r} has no group key",
                code="SCENARIO_RELATION_SCHEMA_UNKNOWN",
            )
        known: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        for row in relation[predicate_id]:
            key = tuple(row.fact_tuple[index] for index in key_indexes)
            previous = known.setdefault(key, row.fact_tuple)
            if previous != row.fact_tuple:
                raise ScenarioResolutionErrorV1(
                    f"single relation {predicate_id!r} has conflicting baseline tuples",
                    code="SCENARIO_BASELINE_CARDINALITY_CONFLICT",
                )
        for intent in group_intents:
            candidate = _canonical_raw_tuple(intent.values)
            key = tuple(candidate[index] for index in key_indexes)
            previous = known.setdefault(key, candidate)
            if previous != candidate:
                raise ScenarioResolutionErrorV1(
                    f"ensure relation would replace a single relation tuple in {predicate_id!r}",
                    code="SCENARIO_OPERATION_CONFLICT",
                )


def _relation_intent(
    operation: ScenarioEnsureRelationV1 | ScenarioWithoutRelationV1, *, index: SchemaIndex
) -> _Intent:
    _schema_predicate_record(index, operation.predicate_id)
    info = index.predicates_by_id.get(operation.predicate_id)
    if info is None:
        raise ScenarioResolutionErrorV1(
            f"predicate {operation.predicate_id!r} is not indexed",
            code="SCENARIO_RELATION_SCHEMA_UNKNOWN",
        )
    # Relation v1 is deliberately for schema-declared extensional relations,
    # including an Entity-reference relationship field, but not a scalar
    # field, lowered head, compiled projection, or derived rule output.
    if not is_scenario_relation_predicate_v1(index, operation.predicate_id):
        raise ScenarioResolutionErrorV1(
            f"predicate {operation.predicate_id!r} is not an allowed extensional relation",
            code="SCENARIO_DERIVED_RELATION_UNSUPPORTED",
        )
    domains = _predicate_domains(index, operation.predicate_id)
    premise_ids, origin_refs = _op_origin(operation)
    if isinstance(operation, ScenarioEnsureRelationV1):
        if len(domains) != len(operation.values) or any(
            value.tag != domain for value, domain in zip(operation.values, domains, strict=True)
        ):
            raise ScenarioResolutionErrorV1(
                f"relation values do not match predicate signature for {operation.predicate_id!r}",
                code="SCENARIO_VALUE_DOMAIN_MISMATCH",
            )
        return _Intent(
            "ensure_relation", None, None, None, info, operation.values, premise_ids, origin_refs
        )
    return _Intent("without_relation", None, None, None, info, (), premise_ids, origin_refs)


def _without_entity_intent(operation: ScenarioWithoutEntityV1, *, index: SchemaIndex) -> _Intent:
    canonical, entity_ref, _ = _canonical_entity_ref(operation.entity, index=index)
    premise_ids, origin_refs = _op_origin(operation)
    return _Intent(
        "without_entity",
        entity_ref,
        canonical.entity_type,
        None,
        None,
        (),
        premise_ids,
        origin_refs,
    )


def _merge_metadata(intents: Sequence[_Intent]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        tuple(sorted({item for intent in intents for item in intent.premise_ids})),
        tuple(sorted({item for intent in intents for item in intent.origin_refs})),
    )


def _normalize_field_group(intents: Sequence[_Intent]) -> tuple[_Intent, ...]:
    """Order-independent set algebra for exactly one ``(entity, field)`` target."""

    assert intents
    info = intents[0].info
    assert info is not None
    if any(intent.info != info for intent in intents):  # pragma: no cover - keyed by predicate
        raise ScenarioResolutionErrorV1(
            "internal field target mismatch", code="SCENARIO_INTERNAL_TARGET_MISMATCH"
        )
    metadata = _merge_metadata(intents)
    sample = intents[0]
    exacts = [intent for intent in intents if intent.kind == "set_exact_members"]
    sets = [intent for intent in intents if intent.kind == "set_effective_value"]
    ensures = [intent for intent in intents if intent.kind == "ensure_member"]
    without_fields = [intent for intent in intents if intent.kind == "without_field"]
    without_values = [intent for intent in intents if intent.kind == "without_value"]

    if exacts:
        exact_values = exacts[0].values
        if any(intent.values != exact_values for intent in exacts[1:]):
            raise ScenarioResolutionErrorV1(
                "conflicting set_exact_members", code="SCENARIO_OPERATION_CONFLICT"
            )
        exact_set = set(exact_values)
        if any(value not in exact_set for intent in ensures for value in intent.values):
            raise ScenarioResolutionErrorV1(
                "ensure member conflicts with exact member set", code="SCENARIO_OPERATION_CONFLICT"
            )
        if any(value in exact_set for intent in without_values for value in intent.values):
            raise ScenarioResolutionErrorV1(
                "without value conflicts with exact member set", code="SCENARIO_OPERATION_CONFLICT"
            )
        return (
            _Intent(
                "set_exact_members",
                sample.entity_ref,
                sample.entity_type,
                sample.field,
                info,
                exact_values,
                metadata[0],
                metadata[1],
            ),
        )

    if sets:
        set_values = {intent.values[0] for intent in sets}
        if len(set_values) != 1:
            raise ScenarioResolutionErrorV1(
                "conflicting scalar replacement values", code="SCENARIO_OPERATION_CONFLICT"
            )
        selected = next(iter(set_values))
        if any(value == selected for intent in without_values for value in intent.values):
            raise ScenarioResolutionErrorV1(
                "without value conflicts with scalar replacement",
                code="SCENARIO_OPERATION_CONFLICT",
            )
        return (
            _Intent(
                "set_effective_value",
                sample.entity_ref,
                sample.entity_type,
                sample.field,
                info,
                (selected,),
                metadata[0],
                metadata[1],
            ),
        )

    # A field-wide remove followed by explicit member guarantees has one
    # deterministic set-algebra interpretation: an exact new member set.
    if without_fields and ensures:
        values = tuple(
            sorted(
                {value for intent in ensures for value in intent.values},
                key=lambda value: value.value_digest,
            )
        )
        if any(value in set(values) for intent in without_values for value in intent.values):
            raise ScenarioResolutionErrorV1(
                "ensure member conflicts with without value",
                code="SCENARIO_OPERATION_CONFLICT",
            )
        return (
            _Intent(
                "set_exact_members",
                sample.entity_ref,
                sample.entity_type,
                sample.field,
                info,
                values,
                metadata[0],
                metadata[1],
            ),
        )
    if without_fields:
        return (
            _Intent(
                "without_field",
                sample.entity_ref,
                sample.entity_type,
                sample.field,
                info,
                (),
                metadata[0],
                metadata[1],
            ),
        )
    if ensures:
        values = tuple(
            sorted(
                {value for intent in ensures for value in intent.values},
                key=lambda value: value.value_digest,
            )
        )
        if any(value in set(values) for intent in without_values for value in intent.values):
            raise ScenarioResolutionErrorV1(
                "ensure member conflicts with without value", code="SCENARIO_OPERATION_CONFLICT"
            )
        return (
            _Intent(
                "ensure_member",
                sample.entity_ref,
                sample.entity_type,
                sample.field,
                info,
                values,
                metadata[0],
                metadata[1],
            ),
        )
    if without_values:
        values = tuple(
            sorted(
                {value for intent in without_values for value in intent.values},
                key=lambda value: value.value_digest,
            )
        )
        return (
            _Intent(
                "without_value",
                sample.entity_ref,
                sample.entity_type,
                sample.field,
                info,
                values,
                metadata[0],
                metadata[1],
            ),
        )
    raise ScenarioResolutionErrorV1(
        "empty scenario field group", code="SCENARIO_INTERNAL_EMPTY_GROUP"
    )


def _normalize_relation_group(intents: Sequence[_Intent]) -> tuple[_Intent, ...]:
    """Canonicalize one extensional predicate without sequence semantics."""

    assert intents and intents[0].info is not None
    info = intents[0].info
    assert info is not None
    metadata = _merge_metadata(intents)
    removes = [intent for intent in intents if intent.kind == "without_relation"]
    ensures = [intent for intent in intents if intent.kind == "ensure_relation"]
    if removes and ensures:
        # Unlike a field-wide remove plus explicit member set, a relation-wide
        # remove can hide arbitrary tuple provenance.  Require the caller to
        # state one unambiguous operation rather than inventing an order.
        raise ScenarioResolutionErrorV1(
            "without relation conflicts with ensure relation", code="SCENARIO_OPERATION_CONFLICT"
        )
    if removes:
        return (_Intent("without_relation", None, None, None, info, (), metadata[0], metadata[1]),)
    values = tuple(
        sorted(
            {intent.values for intent in ensures},
            key=lambda group: tuple(value.value_digest for value in group),
        )
    )
    return tuple(
        _Intent("ensure_relation", None, None, None, info, value, metadata[0], metadata[1])
        for value in values
    )


def _normalize_entity_group(intents: Sequence[_Intent]) -> _Intent:
    assert intents
    entity_refs = {intent.entity_ref for intent in intents}
    entity_types = {intent.entity_type for intent in intents}
    if len(entity_refs) != 1 or len(entity_types) != 1:  # pragma: no cover - grouped by idref
        raise ScenarioResolutionErrorV1(
            "entity target mismatch", code="SCENARIO_INTERNAL_TARGET_MISMATCH"
        )
    premise_ids, origin_refs = _merge_metadata(intents)
    return _Intent(
        "without_entity",
        intents[0].entity_ref,
        intents[0].entity_type,
        None,
        None,
        (),
        premise_ids,
        origin_refs,
    )


def _entity_exists(
    relation: Mapping[str, Sequence[ProjectedFact]], *, info: EntityTypeInfo, entity_ref: str
) -> bool:
    rows = relation.get(info.exists_predicate_id)
    if rows is None:
        raise ScenarioResolutionErrorV1(
            f"entity visibility predicate {info.exists_predicate_id!r} is not in dependency relation",
            code="SCENARIO_ENTITY_VISIBILITY_UNAVAILABLE",
        )
    return any(row.fact_tuple == (entity_ref,) for row in rows)


def _assert_ephemeral_anchors_present(
    relation: Mapping[str, Sequence[ProjectedFact]], *, info: EntityTypeInfo
) -> None:
    required = (
        info.exists_predicate_id,
        *(predicate.pred_id for predicate in info.identity_predicates.values()),
    )
    missing = tuple(
        sorted(predicate_id for predicate_id in required if predicate_id not in relation)
    )
    if missing:
        raise ScenarioResolutionErrorV1(
            f"ephemeral entity requires existence/identity dependencies: {missing!r}",
            code="SCENARIO_EPHEMERAL_DEPENDENCY_UNAVAILABLE",
        )


def _synthetic_id(label: str, payload: object) -> str:
    return f"scenario_v1:{_token(label, payload)[len('sha256:') :]}"


def _canonical_raw_tuple(values: Sequence[ScenarioValueV1]) -> tuple[Any, ...]:
    return tuple(value.to_raw() for value in values)


def _make_resolved_operation(
    intent: _Intent, *, masked: tuple[str, ...] = (), synthetic: tuple[str, ...] = ()
) -> ResolvedScenarioOperationV1:
    predicate_id = None if intent.info is None else intent.info.pred_id
    return ResolvedScenarioOperationV1(
        kind=intent.kind,  # type: ignore[arg-type]
        entity_ref=intent.entity_ref,
        entity_type=intent.entity_type,
        predicate_id=predicate_id,
        field=intent.field,
        assertion_id=intent.assertion_id,
        values=intent.values,
        premise_ids=intent.premise_ids,
        origin_refs=intent.origin_refs,
        masked_witness_ids=masked,
        synthetic_witness_ids=synthetic,
    )


def _apply_field_intent(
    intent: _Intent,
    *,
    mutable: dict[str, list[ProjectedFact]],
    ephemeral_intents: Sequence[_Intent],
    synthetic_ids: set[str],
    index: SchemaIndex,
) -> ResolvedScenarioOperationV1:
    """Apply one normalized field intent to the run-local effective relation."""

    assert intent.info is not None
    assert intent.entity_type is not None and intent.entity_ref is not None
    info = entity_info(index, intent.entity_type)
    ephemeral = any(item.entity_ref == intent.entity_ref for item in ephemeral_intents)
    if not ephemeral and not _entity_exists(mutable, info=info, entity_ref=intent.entity_ref):
        raise ScenarioResolutionErrorV1(
            f"scenario target entity is not visible: {intent.entity_ref}",
            code="SCENARIO_ENTITY_NOT_VISIBLE",
        )
    pred_info = intent.info
    rows = mutable[pred_info.pred_id]
    target_rows = [
        row for row in rows if row.fact_tuple and row.fact_tuple[0] == intent.entity_ref
    ]
    field_masked: list[str] = []
    field_created: list[str] = []

    def remove_rows(predicate: Any) -> None:
        nonlocal rows
        kept: list[ProjectedFact] = []
        for row in rows:
            if predicate(row):
                field_masked.append(row.asrt_id)
            else:
                kept.append(row)
        rows = kept
        mutable[pred_info.pred_id] = kept

    def add_value(value: ScenarioValueV1) -> None:
        synthetic = _synthetic_id(
            "scenario_effective_fact_v1",
            {
                "premise_ids": intent.premise_ids,
                "predicate": pred_info.pred_id,
                "entity": intent.entity_ref,
                "value": value.value_digest,
            },
        )
        rows.append(ProjectedFact(synthetic, (intent.entity_ref, value.to_raw())))
        field_created.append(synthetic)
        synthetic_ids.add(synthetic)

    if intent.kind == "set_effective_value":
        baseline_values = {row.fact_tuple[1] for row in target_rows if len(row.fact_tuple) == 2}
        if len(baseline_values) > 1:
            raise ScenarioResolutionErrorV1(
                f"single field {pred_info.pred_id} has conflicting visible values",
                code="SCENARIO_BASELINE_CARDINALITY_CONFLICT",
            )
        remove_rows(lambda row: row.fact_tuple and row.fact_tuple[0] == intent.entity_ref)
        add_value(intent.values[0])
    elif intent.kind == "ensure_member":
        existing = {row.fact_tuple[1] for row in target_rows if len(row.fact_tuple) == 2}
        for value in intent.values:
            if value.to_raw() not in existing:
                add_value(value)
    elif intent.kind == "set_exact_members":
        remove_rows(lambda row: row.fact_tuple and row.fact_tuple[0] == intent.entity_ref)
        for value in intent.values:
            add_value(value)
    elif intent.kind == "without_field":
        remove_rows(lambda row: row.fact_tuple and row.fact_tuple[0] == intent.entity_ref)
    elif intent.kind == "without_value":
        values = {value.to_raw() for value in intent.values}
        remove_rows(
            lambda row: (
                len(row.fact_tuple) == 2
                and row.fact_tuple[0] == intent.entity_ref
                and row.fact_tuple[1] in values
            )
        )
    else:  # pragma: no cover - closed normalizer
        raise ScenarioResolutionErrorV1(
            "unsupported normalized scenario operation", code="SCENARIO_OPERATION_UNKNOWN"
        )
    return _make_resolved_operation(
        intent, masked=tuple(field_masked), synthetic=tuple(field_created)
    )


def _apply_intents(
    relation: ImmutableProjectedRelationV1,
    *,
    field_intents: Sequence[_Intent],
    ephemeral_intents: Sequence[_Intent],
    relation_intents: Sequence[_Intent],
    entity_without_intents: Sequence[_Intent],
    assertion_without_intents: Sequence[_Intent],
    index: SchemaIndex,
) -> tuple[ImmutableProjectedRelationV1, tuple[ResolvedScenarioOperationV1, ...], frozenset[str]]:
    mutable = {predicate_id: list(rows) for predicate_id, rows in relation.items()}
    resolved: list[ResolvedScenarioOperationV1] = []
    synthetic_ids: set[str] = set()

    # Assertion removal happens first and is bound to the exact frozen input
    # witness.  It is not evidence admission: it creates a Scenario operation
    # and a later exact closure target for this tuple only.
    for intent in sorted(assertion_without_intents, key=lambda item: item.assertion_id or ""):
        assert intent.assertion_id is not None
        witness_id = intent.assertion_id
        matches: list[tuple[str, ProjectedFact]] = []
        for predicate_id, rows in mutable.items():
            matches.extend((predicate_id, row) for row in rows if row.asrt_id == witness_id)
        if len(matches) != 1:
            raise ScenarioResolutionErrorV1(
                f"Scenario assertion {witness_id!r} is not uniquely admitted",
                code="SCENARIO_ASSERTION_NOT_VISIBLE",
            )
        predicate_id, row = matches[0]
        mutable[predicate_id] = [
            item for item in mutable[predicate_id] if item.asrt_id != witness_id
        ]
        operation = _Intent(
            "without_assertion",
            None,
            None,
            None,
            index.predicates_by_id[predicate_id],
            tuple(
                ScenarioValueV1.from_raw(cast(ScenarioValueTagV1, domain), value)
                for domain, value in zip(
                    _predicate_domains(index, predicate_id), row.fact_tuple, strict=True
                )
            ),
            intent.premise_ids,
            intent.origin_refs,
            assertion_id=witness_id,
        )
        resolved.append(_make_resolved_operation(operation, masked=(witness_id,)))

    for intent in sorted(
        entity_without_intents, key=lambda item: (item.entity_type or "", item.entity_ref or "")
    ):
        assert intent.entity_type is not None and intent.entity_ref is not None
        info = entity_info(index, intent.entity_type)
        if not _entity_exists(mutable, info=info, entity_ref=intent.entity_ref):
            raise ScenarioResolutionErrorV1(
                f"scenario entity is not visible: {intent.entity_ref}",
                code="SCENARIO_ENTITY_NOT_VISIBLE",
            )
        entity_masked: list[str] = []
        for predicate_id, rows in tuple(mutable.items()):
            domains = _predicate_domains(index, predicate_id)
            kept: list[ProjectedFact] = []
            for row in rows:
                mentions_entity = any(
                    domain == "entity_ref" and value == intent.entity_ref
                    for domain, value in zip(domains, row.fact_tuple, strict=True)
                )
                if mentions_entity:
                    entity_masked.append(row.asrt_id)
                else:
                    kept.append(row)
            mutable[predicate_id] = kept
        resolved.append(_make_resolved_operation(intent, masked=tuple(entity_masked)))

    for intent in sorted(
        relation_intents,
        key=lambda item: (
            item.info.pred_id if item.info else "",
            item.kind,
            tuple(value.value_digest for value in item.values),
        ),
    ):
        assert intent.info is not None
        rows = mutable[intent.info.pred_id]
        relation_masked: list[str] = []
        relation_created: list[str] = []
        if intent.kind == "without_relation":
            relation_masked = [row.asrt_id for row in rows]
            mutable[intent.info.pred_id] = []
        elif intent.kind == "ensure_relation":
            tuple_value = _canonical_raw_tuple(intent.values)
            if not any(row.fact_tuple == tuple_value for row in rows):
                synthetic = _synthetic_id(
                    "scenario_effective_relation_fact_v1",
                    {
                        "premise_ids": intent.premise_ids,
                        "predicate": intent.info.pred_id,
                        "values": tuple(value.value_digest for value in intent.values),
                    },
                )
                rows.append(ProjectedFact(synthetic, tuple_value))
                relation_created.append(synthetic)
                synthetic_ids.add(synthetic)
        else:  # pragma: no cover - normalizer guard
            raise ScenarioResolutionErrorV1(
                "unsupported relation operation", code="SCENARIO_OPERATION_UNKNOWN"
            )
        resolved.append(
            _make_resolved_operation(
                intent, masked=tuple(relation_masked), synthetic=tuple(relation_created)
            )
        )

    for intent in sorted(ephemeral_intents, key=lambda item: (item.entity_type, item.entity_ref)):
        assert intent.entity_type is not None and intent.entity_ref is not None
        info = entity_info(index, intent.entity_type)
        _assert_ephemeral_anchors_present(mutable, info=info)
        if _entity_exists(mutable, info=info, entity_ref=intent.entity_ref):
            raise ScenarioResolutionErrorV1(
                f"ephemeral entity already exists: {intent.entity_ref}",
                code="SCENARIO_EPHEMERAL_ENTITY_ALREADY_EXISTS",
            )
        ephemeral_created: list[str] = []
        exists_id = _synthetic_id(
            "scenario_ephemeral_exists_v1",
            {"operation": intent.premise_ids, "entity": intent.entity_ref},
        )
        mutable[info.exists_predicate_id].append(ProjectedFact(exists_id, (intent.entity_ref,)))
        ephemeral_created.append(exists_id)
        synthetic_ids.add(exists_id)
        # Identity values were validated while the EntityRef was canonicalized.
        # They are carried on the private, per-call intent; idref digests are
        # intentionally never treated as reversible identifiers.
        identity_values = dict(intent.identity_values)
        for identity in info.identity_fields:
            predicate = info.identity_predicates[identity.name]
            value = identity_values[identity.name]
            synthetic = _synthetic_id(
                "scenario_ephemeral_identity_v1",
                {
                    "operation": intent.premise_ids,
                    "predicate": predicate.pred_id,
                    "entity": intent.entity_ref,
                    "value": value.value_digest,
                },
            )
            mutable[predicate.pred_id].append(
                ProjectedFact(synthetic, (intent.entity_ref, value.to_raw()))
            )
            ephemeral_created.append(synthetic)
            synthetic_ids.add(synthetic)
        resolved.append(_make_resolved_operation(intent, synthetic=tuple(ephemeral_created)))

    for intent in sorted(
        field_intents,
        key=lambda item: (item.entity_ref, item.info.pred_id if item.info else "", item.kind),
    ):
        resolved.append(
            _apply_field_intent(
                intent,
                mutable=mutable,
                ephemeral_intents=ephemeral_intents,
                synthetic_ids=synthetic_ids,
                index=index,
            )
        )

    return _freeze_relation(mutable), tuple(resolved), frozenset(synthetic_ids)


def _closure_for_operations(operations: Sequence[ResolvedScenarioOperationV1]) -> ClosureScopeV1:
    targets: list[ExactLocalClosureTargetV1] = []
    for operation in operations:
        if operation.kind == "without_field":
            assert operation.predicate_id is not None
            targets.append(
                ExactLocalClosureTargetV1("field", operation.entity_ref, operation.predicate_id)
            )
        elif operation.kind == "set_exact_members":
            assert operation.predicate_id is not None
            targets.append(
                ExactLocalClosureTargetV1(
                    "exact_set",
                    operation.entity_ref,
                    operation.predicate_id,
                    members=operation.values,
                )
            )
        elif operation.kind == "without_value":
            assert operation.predicate_id is not None
            for value in operation.values:
                targets.append(
                    ExactLocalClosureTargetV1(
                        "member", operation.entity_ref, operation.predicate_id, value
                    )
                )
        elif operation.kind == "without_relation":
            assert operation.predicate_id is not None
            targets.append(ExactLocalClosureTargetV1("relation", None, operation.predicate_id))
        elif operation.kind == "without_entity":
            targets.append(ExactLocalClosureTargetV1("entity", operation.entity_ref, None))
        elif operation.kind == "without_assertion":
            assert operation.assertion_id is not None and operation.predicate_id is not None
            targets.append(
                ExactLocalClosureTargetV1(
                    "assertion", None, operation.predicate_id, assertion_id=operation.assertion_id
                )
            )
    return ClosureScopeV1(tuple(targets))


def resolve_scenario_v1(
    spec: ScenarioSpecV1,
    *,
    schema_index: SchemaIndex,
    baseline_relation: ProjectedRelationV1,
    base_view_digest: str,
    admissibility_digest: str,
) -> ResolvedScenarioV1:
    """Resolve a portable scenario against an already admitted dependency relation.

    This foundation accepts only schema predicates present in ``baseline_relation``.
    For an ephemeral entity, the relation must include that entity type's
    ``:exists`` and all identity predicates; this prevents accidental creation
    based on an incomplete dependency slice.  Relation operations are limited
    to schema-declared extensional predicates; engine execution is outside this
    narrow resolver.
    """

    if not isinstance(spec, ScenarioSpecV1):
        raise ScenarioResolutionErrorV1("spec must be ScenarioSpecV1", code="SCENARIO_SPEC_INVALID")
    if not isinstance(schema_index, SchemaIndex):
        raise ScenarioResolutionErrorV1(
            "schema_index must be SchemaIndex", code="SCENARIO_SCHEMA_INVALID"
        )
    _sha_token(base_view_digest, name="base_view_digest")
    _sha_token(admissibility_digest, name="admissibility_digest")
    relation = _freeze_relation(baseline_relation)
    if not relation:
        raise ScenarioResolutionErrorV1(
            "baseline relation must be non-empty", code="SCENARIO_RELATION_EMPTY"
        )
    for predicate_id in relation:
        _predicate_domains(schema_index, predicate_id)
    dependency_predicate_ids = tuple(sorted(relation))
    baseline_world = EffectiveWorldV1(
        schema_digest=schema_index.schema_digest,
        base_view_digest=base_view_digest,
        admissibility_digest=admissibility_digest,
        dependency_predicate_ids=dependency_predicate_ids,
        facts=_typed_facts(relation, index=schema_index),
    )

    field_groups: dict[tuple[str, str], list[_Intent]] = {}
    creates: dict[str, list[_Intent]] = {}
    relation_groups: dict[str, list[_Intent]] = {}
    without_entities: dict[str, list[_Intent]] = {}
    without_assertions: dict[str, list[_Intent]] = {}
    for operation in spec.operations:
        if isinstance(operation, ScenarioCreateEphemeralEntityV1):
            canonical, entity_ref, entity = _canonical_entity_ref(
                operation.entity, index=schema_index
            )
            premise_ids, origin_refs = _op_origin(operation)
            identity_values = tuple(
                (
                    identity.name,
                    ScenarioValueV1.from_raw(
                        cast(ScenarioValueTagV1, identity.type_domain),
                        canonical.identity[identity.name],
                    ),
                )
                for identity in entity.identity_fields
            )
            intent = _Intent(
                "create_ephemeral_entity",
                entity_ref,
                canonical.entity_type,
                None,
                None,
                (),
                premise_ids,
                origin_refs,
                identity_values,
            )
            creates.setdefault(entity_ref, []).append(intent)
        elif isinstance(operation, (ScenarioEnsureRelationV1, ScenarioWithoutRelationV1)):
            intent = _relation_intent(operation, index=schema_index)
            assert intent.info is not None
            if intent.info.pred_id not in relation:
                raise ScenarioResolutionErrorV1(
                    f"scenario relation {intent.info.pred_id!r} is outside the supplied dependency relation",
                    code="SCENARIO_TARGET_OUTSIDE_DEPENDENCY",
                )
            relation_groups.setdefault(intent.info.pred_id, []).append(intent)
        elif isinstance(operation, ScenarioWithoutEntityV1):
            intent = _without_entity_intent(operation, index=schema_index)
            assert intent.entity_ref is not None
            without_entities.setdefault(intent.entity_ref, []).append(intent)
        elif isinstance(operation, ScenarioWithoutAssertionV1):
            premise_ids, origin_refs = _op_origin(operation)
            without_assertions.setdefault(operation.assertion_id, []).append(
                _Intent(
                    "without_assertion",
                    None,
                    None,
                    None,
                    None,
                    (),
                    premise_ids,
                    origin_refs,
                    assertion_id=operation.assertion_id,
                )
            )
        else:
            intent = _field_intent(operation, index=schema_index)
            assert intent.info is not None
            assert intent.entity_ref is not None
            if intent.info.pred_id not in relation:
                raise ScenarioResolutionErrorV1(
                    f"scenario field {intent.info.pred_id!r} is outside the supplied dependency relation",
                    code="SCENARIO_TARGET_OUTSIDE_DEPENDENCY",
                )
            field_groups.setdefault((intent.entity_ref, intent.info.pred_id), []).append(intent)

    overlapping_entities = set(creates) & set(without_entities)
    if overlapping_entities:
        raise ScenarioResolutionErrorV1(
            f"create ephemeral conflicts with without entity: {sorted(overlapping_entities)!r}",
            code="SCENARIO_OPERATION_CONFLICT",
        )
    field_entities = {entity_ref for entity_ref, _ in field_groups}
    removed_with_fields = field_entities & set(without_entities)
    if removed_with_fields:
        raise ScenarioResolutionErrorV1(
            f"field operation conflicts with without entity: {sorted(removed_with_fields)!r}",
            code="SCENARIO_OPERATION_CONFLICT",
        )
    removed_entity_refs = set(without_entities)
    if removed_entity_refs:
        for predicate_id, intents in relation_groups.items():
            for intent in intents:
                if intent.kind != "ensure_relation":
                    continue
                if any(
                    value.tag == "entity_ref" and value.to_raw() in removed_entity_refs
                    for value in intent.values
                ):
                    raise ScenarioResolutionErrorV1(
                        "ensure relation conflicts with without entity",
                        code="SCENARIO_OPERATION_CONFLICT",
                    )

    normalized_creates: list[_Intent] = []
    for entity_ref, intents in creates.items():
        entity_types = {intent.entity_type for intent in intents}
        if len(entity_types) != 1:  # pragma: no cover - idref includes type
            raise ScenarioResolutionErrorV1(
                "conflicting ephemeral entity types", code="SCENARIO_OPERATION_CONFLICT"
            )
        premise_ids, origin_refs = _merge_metadata(intents)
        representative = intents[0]
        # All aliases resolve to exactly the same idref; coalescing preserves
        # every premise/origin in the one synthetic entity origin.
        merged = _Intent(
            "create_ephemeral_entity",
            entity_ref,
            representative.entity_type,
            None,
            None,
            (),
            premise_ids,
            origin_refs,
            representative.identity_values,
        )
        normalized_creates.append(merged)

    normalized_fields: list[_Intent] = []
    for _, intents in sorted(field_groups.items()):
        normalized_fields.extend(_normalize_field_group(intents))
    normalized_relations: list[_Intent] = []
    for _, intents in sorted(relation_groups.items()):
        normalized_relations.extend(_normalize_relation_group(intents))
    normalized_without_entities = [
        _normalize_entity_group(intents) for _, intents in sorted(without_entities.items())
    ]
    normalized_without_assertions = [
        _Intent(
            "without_assertion",
            None,
            None,
            None,
            None,
            (),
            _merge_metadata(intents)[0],
            _merge_metadata(intents)[1],
            assertion_id=assertion_id,
        )
        for assertion_id, intents in sorted(without_assertions.items())
    ]

    # Relation additions are grounded against the same finite Scenario world
    # before any engine sees it.  They cannot introduce an unpinned entity or
    # silently replace a schema-single relation group.
    _assert_relation_entities_visible(
        normalized_relations,
        relation=relation,
        ephemeral_entity_refs=frozenset(creates),
        index=schema_index,
    )
    _assert_relation_cardinality(
        normalized_relations,
        relation=relation,
        index=schema_index,
    )

    effective_relation, resolved_operations, scenario_witness_ids = _apply_intents(
        relation,
        field_intents=normalized_fields,
        ephemeral_intents=normalized_creates,
        relation_intents=normalized_relations,
        entity_without_intents=normalized_without_entities,
        assertion_without_intents=normalized_without_assertions,
        index=schema_index,
    )

    closure = _closure_for_operations(resolved_operations)
    effective_world = EffectiveWorldV1(
        schema_digest=schema_index.schema_digest,
        base_view_digest=base_view_digest,
        admissibility_digest=admissibility_digest,
        dependency_predicate_ids=dependency_predicate_ids,
        facts=_typed_facts(
            effective_relation, index=schema_index, scenario_witness_ids=scenario_witness_ids
        ),
        operations=resolved_operations,
        closure=closure,
    )
    return ResolvedScenarioV1(spec, baseline_world, effective_world)


__all__ = [
    "EvidenceScopeApplicationV1",
    "ImmutableProjectedRelationV1",
    "ProjectedRelationV1",
    "ScenarioResolutionErrorV1",
    "apply_evidence_scope_v1",
    "effective_world_to_relation_v1",
    "resolve_scenario_v1",
    "scenario_dependency_predicate_ids_v1",
    "select_dependency_relation_v1",
]
