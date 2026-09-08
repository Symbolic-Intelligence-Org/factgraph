"""Current advanced Query DTO behavior, independent of the removed run shell."""

from typing import Literal

import pytest

from factgraph.application import (
    build_schema_index,
    entity_info,
    execute_query,
    field_predicate,
    resolve_selector,
)
from factgraph.application.protocol import (
    EntitySelector,
    EntitySnapshotDTO,
    FieldPath,
    QueryReturnContract,
    QueryReturnSlot,
    QueryRuntimeRequest,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()
    nickname: str = Field()


def _fixture():
    schema = compile_schema_from_classes([Person])
    store = Store(schema)
    index = build_schema_index(schema)
    info = entity_info(index, "Person")
    predicate = field_predicate(index, "Person", "nickname").pred_id
    for name, nickname in (("alice", "ally"), ("bob", "bobby")):
        selected = resolve_selector(
            EntitySelector(entity_type="Person", identity={"name": name}), index=index
        )
        ref = selected.encoded_ref
        assert ref is not None
        set_field(store.ledger, info.exists_predicate_id, ref, [])
        set_field(store.ledger, info.identity_predicates["name"].pred_id, ref, [("string", name)])
        set_field(store.ledger, predicate, ref, [("string", nickname)])
    return store, index, [("pred", predicate, ["$person", "$nickname"])]


def _scalar(alias="nickname", var="$nickname"):
    return QueryReturnSlot(
        alias=alias,
        kind="scalar",
        var=var,
        field_path=FieldPath(entity_type="Person", field_name="nickname"),
    )


@pytest.mark.parametrize("kind", ["entity", "scalar"])
@pytest.mark.parametrize("policy", ["error", "skip", "null"])
def test_current_missing_slot_policy_executes_without_legacy_sdk_mapping(
    kind: Literal["entity", "scalar"],
    policy: Literal["error", "skip", "null"],
):
    store, index, where = _fixture()
    missing = (
        QueryReturnSlot(alias="missing", kind="entity", var="$unbound")
        if kind == "entity"
        else _scalar("missing", "$unbound")
    )
    request = QueryRuntimeRequest(
        entity_type="Person",
        where_ir=where,
        return_contract=QueryReturnContract(slots=(missing, _scalar())),
        on_missing=policy,
    )
    response = execute_query(request, store=store, index=index)
    assert response.warnings == ()
    if policy == "error":
        assert response.rows == ()
        assert len(response.errors) == 1
        error = response.errors[0]
        assert error.code == "QUERY_MISSING_BINDING"
        assert error.path == ("return_contract", "slots", "missing")
        assert error.details == {"var": "$unbound"}
    elif policy == "skip":
        assert response.errors == ()
        assert response.rows == ()
    else:
        assert response.errors == ()
        assert len(response.rows) == 2
        assert {row["nickname"] for row in response.rows} == {"ally", "bobby"}
        assert all(row["missing"] is None for row in response.rows)


def test_current_scalar_projection_returns_values_in_the_declared_alias():
    store, index, where = _fixture()
    request = QueryRuntimeRequest(
        entity_type="Person",
        where_ir=where,
        return_contract=QueryReturnContract(slots=(_scalar(),)),
    )
    response = execute_query(request, store=store, index=index)
    assert response.errors == response.warnings == ()
    assert len(response.rows) == 2
    assert all(set(row) == {"nickname"} for row in response.rows)
    assert {row["nickname"] for row in response.rows} == {"ally", "bobby"}


def test_current_entity_and_scalar_projection_keep_distinct_typed_values():
    store, index, where = _fixture()
    request = QueryRuntimeRequest(
        entity_type="Person",
        where_ir=where,
        return_contract=QueryReturnContract(
            slots=(
                QueryReturnSlot(alias="person", kind="entity", var="$person", entity_type="Person"),
                _scalar(),
            )
        ),
        on_missing="error",
    )
    response = execute_query(request, store=store, index=index)
    assert response.errors == response.warnings == ()
    assert len(response.rows) == 2
    observed = set()
    for row in response.rows:
        person = row["person"]
        assert type(person) is EntitySnapshotDTO
        observed.add((person.ref.identity["name"], row["nickname"]))
    assert observed == {("alice", "ally"), ("bob", "bobby")}
