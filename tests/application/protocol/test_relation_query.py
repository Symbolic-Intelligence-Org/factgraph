from __future__ import annotations

from dataclasses import replace

import pytest

from factgraph.application import (
    RelationQueryError,
    build_schema_index,
    compile_published_relation_query,
    execute_published_relation_query,
    field_predicate,
    resolve_selector,
)
from factgraph.application.protocol import (
    EntityRef,
    EntitySelector,
    PublishedEntityFieldV1,
    PublishedRelationGraphV1,
    PublishedRelationPathV1,
    PublishedRelationQueryV1,
    PublishedStoredRelationV1,
    RelationPathStepV1,
    RelationQueryBindingV1,
    RelationQuerySelectionV1,
    RelationQuerySourceV1,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, Relationship, compile_schema_from_classes


class User(Entity):
    user_id: str = Identity()
    region: str = Field()


class Team(Entity):
    team_id: str = Identity()


class Org(Entity):
    org_id: str = Identity()
    label: str = Field()


class MemberOf(Relationship):
    from_entity = User
    to_entity = Team
    role: str = Field()


class OwnedBy(Relationship):
    from_entity = Team
    to_entity = Org
    stake: int = Field()


def _schema_fixture():
    schema = compile_schema_from_classes([User, Team, Org, MemberOf, OwnedBy])
    return schema, build_schema_index(schema)


def _relation_predicate(schema: dict, relationship_type: str) -> dict:
    return next(
        item
        for item in schema["predicates"]
        if item.get("relationship_type") == relationship_type
    )


def _graph(schema: dict, *, relation_kind: str = "stored_relation"):
    member = _relation_predicate(schema, "MemberOf")
    owner = _relation_predicate(schema, "OwnedBy")
    return PublishedRelationGraphV1(
        publication_id="package-v1/operation-query",
        fields=(
            PublishedEntityFieldV1(
                key="org_label",
                predicate_id="org:label",
                entity_type="Org",
                value_type="string",
                cardinality="single",
            ),
        ),
        relations=(
            PublishedStoredRelationV1(
                key="membership",
                predicate_id=member["pred_id"],
                from_entity_type="User",
                to_entity_type="Team",
                value_type="string",
                cardinality="single",
                node_kind=relation_kind,
            ),
            PublishedStoredRelationV1(
                key="ownership",
                predicate_id=owner["pred_id"],
                from_entity_type="Team",
                to_entity_type="Org",
                value_type="int",
                cardinality="single",
            ),
        ),
        paths=(
            PublishedRelationPathV1(
                key="user_to_org",
                root_entity_type="User",
                steps=(
                    RelationPathStepV1("membership"),
                    RelationPathStepV1("ownership"),
                ),
            ),
            PublishedRelationPathV1(
                key="org_to_user",
                root_entity_type="Org",
                steps=(
                    RelationPathStepV1("ownership", "reverse"),
                    RelationPathStepV1("membership", "reverse"),
                ),
            ),
        ),
    )


def _ref(index, entity_type: str, identity: dict) -> EntityRef:
    resolved = resolve_selector(
        EntitySelector(entity_type=entity_type, identity=identity),
        index=index,
    )
    assert resolved.encoded_ref is not None
    return resolved


def _seed_entity(store: Store, index, ref: EntityRef) -> None:
    for field_name, value in ref.identity.items():
        predicate = field_predicate(index, ref.entity_type, field_name)
        type_domain = index.entities[ref.entity_type].identity_fields[0].type_domain
        set_field(
            store.ledger,
            predicate.pred_id,
            ref.encoded_ref or "",
            [(type_domain, value)],
        )


def _runtime_fixture():
    schema, index = _schema_fixture()
    store = Store(schema)
    user = _ref(index, "User", {"user_id": "alice"})
    team = _ref(index, "Team", {"team_id": "core"})
    org = _ref(index, "Org", {"org_id": "acme"})
    for ref in (user, team, org):
        _seed_entity(store, index, ref)
    member = _relation_predicate(schema, "MemberOf")
    owner = _relation_predicate(schema, "OwnedBy")
    set_field(
        store.ledger,
        member["pred_id"],
        user.encoded_ref or "",
        [("entity_ref", team.encoded_ref), ("string", "admin")],
    )
    set_field(
        store.ledger,
        owner["pred_id"],
        team.encoded_ref or "",
        [("entity_ref", org.encoded_ref), ("int", 100)],
    )
    set_field(store.ledger, "org:label", org.encoded_ref or "", [("string", "ACME")])
    return schema, index, store, user, team, org


def _query(graph, user: EntityRef, *, row_limit: int = 10):
    return PublishedRelationQueryV1(
        graph=graph,
        bindings=(
            RelationQueryBindingV1(
                RelationQuerySourceV1("entity", "user_to_org", 0),
                user,
            ),
            RelationQueryBindingV1(
                RelationQuerySourceV1(
                    "relation_value",
                    "user_to_org",
                    0,
                    "membership",
                ),
                "admin",
            ),
        ),
        selections=(
            RelationQuerySelectionV1(
                "team",
                RelationQuerySourceV1("entity", "user_to_org", 1),
            ),
            RelationQuerySelectionV1(
                "org",
                RelationQuerySourceV1("entity", "user_to_org", 2),
            ),
            RelationQuerySelectionV1(
                "stake",
                RelationQuerySourceV1(
                    "relation_value",
                    "user_to_org",
                    1,
                    "ownership",
                ),
            ),
            RelationQuerySelectionV1(
                "org_label",
                RelationQuerySourceV1("field", "user_to_org", 2, "org_label"),
            ),
        ),
        row_limit=row_limit,
    )


def test_multihop_query_is_sealed_with_domain_guards_and_executes():
    schema, index, store, user, team, org = _runtime_fixture()
    invocation = compile_published_relation_query(
        _query(_graph(schema), user),
        schema_index=index,
    )

    assert invocation.domain_guard_predicate_ids == (
        "Org:exists",
        "Team:exists",
        "User:exists",
    )
    assert not hasattr(invocation, "where_ir")
    assert invocation.query_digest == compile_published_relation_query(
        _query(_graph(schema), user),
        schema_index=index,
    ).query_digest

    result = execute_published_relation_query(
        invocation,
        store=store,
        schema_index=index,
    )
    assert result.rows == (
        {
            "team": team.encoded_ref,
            "org": org.encoded_ref,
            "stake": 100,
            "org_label": "ACME",
        },
    )


def test_reverse_path_preserves_endpoint_direction():
    schema, index, store, user, _team, org = _runtime_fixture()
    query = PublishedRelationQueryV1(
        graph=_graph(schema),
        bindings=(
            RelationQueryBindingV1(
                RelationQuerySourceV1("entity", "org_to_user", 0),
                org,
            ),
        ),
        selections=(
            RelationQuerySelectionV1(
                "user",
                RelationQuerySourceV1("entity", "org_to_user", 2),
            ),
        ),
        row_limit=10,
    )
    result = execute_published_relation_query(
        compile_published_relation_query(query, schema_index=index),
        store=store,
        schema_index=index,
    )
    assert result.rows == ({"user": user.encoded_ref},)


def test_typed_comparison_constraint_is_compiled_without_raw_ast_input():
    schema, index, store, user, _team, _org = _runtime_fixture()
    query = _query(_graph(schema), user)
    constrained = replace(
        query,
        bindings=(
            *query.bindings,
            RelationQueryBindingV1(
                RelationQuerySourceV1(
                    "relation_value",
                    "user_to_org",
                    1,
                    "ownership",
                ),
                50,
                "ge",
            ),
        ),
    )
    result = execute_published_relation_query(
        compile_published_relation_query(constrained, schema_index=index),
        store=store,
        schema_index=index,
    )
    assert result.rows[0]["stake"] == 100


def test_phantom_intermediate_entity_is_removed_by_virtual_domain_guard():
    schema, index, store, user, _team, org = _runtime_fixture()
    phantom = _ref(index, "Team", {"team_id": "phantom"})
    member = _relation_predicate(schema, "MemberOf")
    owner = _relation_predicate(schema, "OwnedBy")
    set_field(
        store.ledger,
        member["pred_id"],
        user.encoded_ref or "",
        [("entity_ref", phantom.encoded_ref), ("string", "admin")],
    )
    set_field(
        store.ledger,
        owner["pred_id"],
        phantom.encoded_ref or "",
        [("entity_ref", org.encoded_ref), ("int", 10)],
    )

    result = execute_published_relation_query(
        compile_published_relation_query(
            _query(_graph(schema), user),
            schema_index=index,
        ),
        store=store,
        schema_index=index,
    )
    assert len(result.rows) == 1
    assert result.rows[0]["stake"] == 100


@pytest.mark.parametrize("kind", ["rule", "provider", "scenario"])
def test_query_rejects_non_stored_relation_node_kinds(kind: str):
    schema, index = _schema_fixture()
    user = _ref(index, "User", {"user_id": "alice"})
    with pytest.raises(RelationQueryError) as exc_info:
        compile_published_relation_query(
            _query(_graph(schema, relation_kind=kind), user),
            schema_index=index,
        )
    assert exc_info.value.code == "QUERY_NODE_KIND_FORBIDDEN"


def test_path_endpoint_discontinuity_fails_closed():
    schema, index = _schema_fixture()
    user = _ref(index, "User", {"user_id": "alice"})
    graph = _graph(schema)
    broken = replace(
        graph,
        paths=(
            PublishedRelationPathV1(
                "user_to_org",
                "User",
                (
                    RelationPathStepV1("ownership"),
                    RelationPathStepV1("membership"),
                ),
            ),
        ),
    )
    with pytest.raises(RelationQueryError) as exc_info:
        compile_published_relation_query(_query(broken, user), schema_index=index)
    assert exc_info.value.code == "RELATION_PATH_DISCONTINUITY"


def test_schema_cardinality_mismatch_fails_graph_admission():
    schema, index = _schema_fixture()
    user = _ref(index, "User", {"user_id": "alice"})
    graph = _graph(schema)
    bad_relation = replace(graph.relations[0], cardinality="multi")
    with pytest.raises(RelationQueryError) as exc_info:
        compile_published_relation_query(
            _query(replace(graph, relations=(bad_relation, graph.relations[1])), user),
            schema_index=index,
        )
    assert exc_info.value.code == "PUBLISHED_RELATION_GRAPH_MISMATCH"


def test_published_row_limit_fails_closed_instead_of_truncating():
    schema, index, store, user, _team, _org = _runtime_fixture()
    team2 = _ref(index, "Team", {"team_id": "second"})
    org2 = _ref(index, "Org", {"org_id": "second"})
    _seed_entity(store, index, team2)
    _seed_entity(store, index, org2)
    member = _relation_predicate(schema, "MemberOf")
    owner = _relation_predicate(schema, "OwnedBy")
    set_field(
        store.ledger,
        member["pred_id"],
        user.encoded_ref or "",
        [("entity_ref", team2.encoded_ref), ("string", "admin")],
    )
    set_field(
        store.ledger,
        owner["pred_id"],
        team2.encoded_ref or "",
        [("entity_ref", org2.encoded_ref), ("int", 50)],
    )
    set_field(store.ledger, "org:label", org2.encoded_ref or "", [("string", "Second")])
    invocation = compile_published_relation_query(
        _query(_graph(schema), user, row_limit=1),
        schema_index=index,
    )
    with pytest.raises(RelationQueryError) as exc_info:
        execute_published_relation_query(invocation, store=store, schema_index=index)
    assert exc_info.value.code == "RELATION_QUERY_ROW_LIMIT_EXCEEDED"


def test_tampered_compiler_product_is_rejected_before_execution():
    schema, index, _store, user, _team, _org = _runtime_fixture()
    invocation = compile_published_relation_query(
        _query(_graph(schema), user),
        schema_index=index,
    )
    with pytest.raises(ValueError, match="digest"):
        replace(invocation, _where_ir=())
