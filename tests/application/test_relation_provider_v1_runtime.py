from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from factgraph.application import build_schema_index, field_predicate, resolve_selector
from factgraph.application.protocol import EntitySelector
from factgraph.application.protocol.goal_plan_v1 import GoalValueV1
from factgraph.application.protocol.relation_provider_v1 import (
    ProviderMaterializationV1,
    ProviderRelationRowV1,
    ProviderRequestV1,
)
from factgraph.application.relation_provider_v1_runtime import (
    ProviderRelationMaterializationError,
    merge_provider_materialization_v1,
    provider_materialization_to_relation_v1,
)
from factgraph.core.store._support import ProjectedFact
from factgraph.sdk import Entity, Field, Identity, SDKStore


def _token(character: str) -> str:
    return f"sha256:{hashlib.sha256(character.encode('utf-8')).hexdigest()}"


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    skills: list[str] = Field()


def _fixture():
    graph = SDKStore([Person])
    schema_ir = deepcopy(graph.schema_ir)
    index = build_schema_index(schema_ir)
    alice = resolve_selector(
        EntitySelector(entity_type="Person", identity={"employee_id": "alice"}),
        index=index,
    )
    assert alice.encoded_ref is not None
    age = field_predicate(index, "Person", "age").pred_id
    skills = field_predicate(index, "Person", "skills").pred_id
    dependencies = tuple(sorted((age, skills)))
    baseline = {
        age: (ProjectedFact("baseline-age", (alice.encoded_ref, 22)),),
        skills: (ProjectedFact("baseline-skill", (alice.encoded_ref, "python")),),
    }
    request = ProviderRequestV1(
        provider_digest=_token("p"),
        query_digest=_token("q"),
        schema_digest=_token("s"),
        dependency_predicate_ids=dependencies,
        supplied_predicate_ids=(age,),
        bindings=(),
    )
    return schema_ir, alice.encoded_ref, age, skills, baseline, request


def _materialization(
    request: ProviderRequestV1,
    age_predicate: str,
    entity_ref: str,
    *,
    age: int | None = 30,
    tag: str = "int",
) -> ProviderMaterializationV1:
    raw_value: object = age if tag == "int" else str(age)
    rows = (
        ()
        if age is None
        else (
            ProviderRelationRowV1(
                age_predicate,
                (
                    GoalValueV1("entity_ref", entity_ref),
                    GoalValueV1(tag, raw_value),  # type: ignore[arg-type]
                ),
                "provider:source:age",
            ),
        )
    )
    return ProviderMaterializationV1(
        request.provider_digest,
        request.request_digest,
        "receipt:lookup:age",
        _token("r"),
        request.supplied_predicate_ids,
        rows,
    )


def test_provider_output_becomes_immutable_schema_typed_relation() -> None:
    schema_ir, alice, age, _skills, _baseline, request = _fixture()
    materialization = _materialization(request, age, alice)

    relation = provider_materialization_to_relation_v1(materialization, schema_ir=schema_ir)
    assert tuple(relation) == (age,)
    assert relation[age][0].fact_tuple == (alice, 30)
    assert relation[age][0].asrt_id.startswith("provider:sha256:")
    with pytest.raises(TypeError):
        relation[age] = ()  # type: ignore[index]


def test_provider_output_rejects_schema_domain_mismatch_before_merge() -> None:
    schema_ir, alice, age, _skills, _baseline, request = _fixture()
    materialization = _materialization(request, age, alice, tag="string")
    with pytest.raises(ProviderRelationMaterializationError) as error:
        provider_materialization_to_relation_v1(materialization, schema_ir=schema_ir)
    assert error.value.code == "PROVIDER_ROW_VALUE_DOMAIN_MISMATCH"


def test_merge_replaces_exact_provider_subset_and_preserves_other_baseline_dependencies() -> None:
    schema_ir, alice, age, skills, baseline, request = _fixture()
    materialization = _materialization(request, age, alice, age=30)

    merged = merge_provider_materialization_v1(
        baseline,
        request=request,
        materialization=materialization,
        schema_ir=schema_ir,
    )
    assert tuple(merged) == request.dependency_predicate_ids
    assert tuple(row.fact_tuple for row in merged[age]) == ((alice, 30),)
    assert tuple(row.fact_tuple for row in merged[skills]) == ((alice, "python"),)
    assert all(row.asrt_id != "baseline-age" for row in merged[age])


def test_merge_preserves_explicit_empty_provider_relation_as_replacement_not_fallback() -> None:
    schema_ir, alice, age, _skills, baseline, request = _fixture()
    materialization = _materialization(request, age, alice, age=None)

    merged = merge_provider_materialization_v1(
        baseline,
        request=request,
        materialization=materialization,
        schema_ir=schema_ir,
    )
    assert merged[age] == ()


def test_merge_rejects_request_mismatch_and_incomplete_baseline_inventory() -> None:
    schema_ir, alice, age, skills, baseline, request = _fixture()
    materialization = _materialization(request, age, alice)
    wrong_request = ProviderRequestV1(
        provider_digest=request.provider_digest,
        query_digest=_token("z"),
        schema_digest=request.schema_digest,
        dependency_predicate_ids=request.dependency_predicate_ids,
        supplied_predicate_ids=request.supplied_predicate_ids,
        bindings=(),
    )
    with pytest.raises(ProviderRelationMaterializationError) as error:
        merge_provider_materialization_v1(
            baseline,
            request=wrong_request,
            materialization=materialization,
            schema_ir=schema_ir,
        )
    assert error.value.code == "PROVIDER_MATERIALIZATION_REQUEST_MISMATCH"

    with pytest.raises(ProviderRelationMaterializationError) as error:
        merge_provider_materialization_v1(
            {age: baseline[age]},
            request=request,
            materialization=materialization,
            schema_ir=schema_ir,
        )
    assert error.value.code == "PROVIDER_BASELINE_RELATION_INVENTORY_MISMATCH"
    assert skills in request.dependency_predicate_ids


def test_merge_rejects_ambiguous_witness_collision_in_effective_relation() -> None:
    schema_ir, alice, age, skills, baseline, request = _fixture()
    materialization = _materialization(request, age, alice)
    # The provider witness is derived from its row digest.  A caller cannot
    # smuggle an unrelated baseline assertion under that same capture-local id.
    provider_witness = provider_materialization_to_relation_v1(
        materialization, schema_ir=schema_ir
    )[age][0].asrt_id
    conflicting_baseline = {
        age: baseline[age],
        skills: (ProjectedFact(provider_witness, (alice, "python")),),
    }
    with pytest.raises(ProviderRelationMaterializationError) as error:
        merge_provider_materialization_v1(
            conflicting_baseline,
            request=request,
            materialization=materialization,
            schema_ir=schema_ir,
        )
    assert error.value.code == "PROVIDER_MERGED_DUPLICATE_WITNESS"
