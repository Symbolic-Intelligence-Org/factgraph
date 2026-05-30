from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from factgraph.sdk import (
    Entity,
    FactGraph,
    Field,
    Identity,
    SchemaConflictError,
    SchemaNonAdditiveError,
    SchemaNotFoundError,
    SDKStoreError,
)
from factgraph.application.schema_mutation_runtime import validate_additive_schema_extension
from factgraph.sdk.compile import compile_schema_from_classes


class SchemaUser(Entity):
    user_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


class SchemaAccount(Entity):
    account_id: str = Identity()
    label: str = Field()


class SchemaProject(Entity):
    project_id: str = Identity()
    title: str = Field()


class SchemaTenantUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()


def _entity_class(name: str, annotations: dict[str, Any], members: dict[str, Any]) -> type[Entity]:
    namespace = {"__annotations__": annotations, "__module__": __name__}
    namespace.update(members)
    return type(name, (Entity,), namespace)


def _user_adds_nickname() -> type[Entity]:
    return _entity_class(
        "SchemaUser",
        {
            "user_id": str,
            "name": str,
            "tags": list[str],
            "nickname": str,
        },
        {
            "user_id": Identity(),
            "name": Field(),
            "tags": Field(),
            "nickname": Field(),
        },
    )


def _user_identity_added() -> type[Entity]:
    return _entity_class(
        "SchemaUser",
        {
            "user_id": str,
            "tenant_id": str,
            "name": str,
            "tags": list[str],
        },
        {
            "user_id": Identity(),
            "tenant_id": Identity(),
            "name": Field(),
            "tags": Field(),
        },
    )


def _user_identity_to_field() -> type[Entity]:
    return _tenant_user_identity_to_field()


def _tenant_user_identity_to_field() -> type[Entity]:
    return _entity_class(
        "SchemaTenantUser",
        {
            "user_id": str,
            "tenant_id": str,
            "name": str,
        },
        {
            "user_id": Identity(),
            "tenant_id": Field(),
            "name": Field(),
        },
    )


def _user_field_to_identity() -> type[Entity]:
    return _entity_class(
        "SchemaUser",
        {
            "user_id": str,
            "name": str,
            "tags": list[str],
        },
        {
            "user_id": Identity(),
            "name": Identity(),
            "tags": Field(),
        },
    )


def _user_field_removed() -> type[Entity]:
    return _entity_class(
        "SchemaUser",
        {
            "user_id": str,
            "tags": list[str],
        },
        {
            "user_id": Identity(),
            "tags": Field(),
        },
    )


def _user_cardinality_changed() -> type[Entity]:
    return _entity_class(
        "SchemaUser",
        {
            "user_id": str,
            "name": str,
            "tags": str,
        },
        {
            "user_id": Identity(),
            "name": Field(),
            "tags": Field(),
        },
    )


def _user_type_changed() -> type[Entity]:
    return _entity_class(
        "SchemaUser",
        {
            "user_id": str,
            "name": int,
            "tags": list[str],
        },
        {
            "user_id": Identity(),
            "name": Field(),
            "tags": Field(),
        },
    )


def _new_entity(name: str = "SchemaNote") -> type[Entity]:
    return _entity_class(
        name,
        {
            "note_id": str,
            "body": str,
        },
        {
            "note_id": Identity(),
            "body": Field(),
        },
    )


def _fg() -> FactGraph:
    return FactGraph.create(schema_classes=[SchemaUser])


def _field_pred_ids(fg: FactGraph) -> set[str]:
    return {row["pred_id"] for row in fg._field_pred_by_descriptor.values()}


def _schema_state_snapshot(fg: FactGraph) -> dict[str, Any]:
    return {
        "schema_ir": deepcopy(fg.schema_ir),
        "schema_digest": fg._schema_digest,
        "identity_pred_ids": tuple(sorted(fg._application_schema_index.identity_pred_ids)),
        "exists_pred_ids": tuple(sorted(fg._application_schema_index.exists_pred_ids)),
        "classes": tuple(cls.__name__ for cls in fg._classes),
        "field_pred_ids": tuple(sorted(_field_pred_ids(fg))),
        "field_decl_names": tuple(
            sorted(
                (
                    row.get("owner_type"),
                    row.get("py_name"),
                    row.get("cardinality"),
                    str(row.get("value_type")),
                )
                for row in fg._field_decl_by_descriptor.values()
            )
        ),
        "shadow_store": deepcopy(fg._identity_values_by_e_ref),
    }


def _active_claim_fingerprint(fg: FactGraph, e_ref: str) -> tuple[tuple[Any, ...], ...]:
    rows = []
    for claim in fg._store.ledger.find_claims(e_ref=e_ref):
        rows.append(
            (
                claim.asrt_id,
                claim.pred_id,
                claim.e_ref,
                tuple(claim.rest_terms),
                fg._store.ledger.has_active_revocation(claim.asrt_id),
            )
        )
    return tuple(sorted(rows))


def _candidate_schema_with_exists_mutation(kind: str) -> dict[str, Any]:
    candidate = compile_schema_from_classes([SchemaUser])
    out = deepcopy(candidate)
    exists_pred = next(pred for pred in out["predicates"] if pred.get("is_entity_exists") is True)
    if kind == "removed":
        out["predicates"] = [
            pred for pred in out["predicates"] if pred.get("is_entity_exists") is not True
        ]
    elif kind == "owner_changed":
        exists_pred["owner_type"] = "OtherEntity"
    elif kind == "arity_changed":
        exists_pred["arity"] = 2
        exists_pred["arg_specs"] = list(exists_pred.get("arg_specs", [])) + [
            {"name": "exists", "type_domain": "bool"}
        ]
    else:
        raise AssertionError(kind)
    return out


def test_schema_add_manager_method_is_removed() -> None:
    fg = _fg()

    assert not hasattr(fg.schema, "add")
    with pytest.raises(AttributeError):
        getattr(fg.schema, "add")


def test_schema_register_adds_new_entity_and_rebuilds_schema_index_atomically() -> None:
    fg = _fg()
    before = fg._schema_digest

    result = fg.schema.register(SchemaAccount)

    assert result.old_digest == before
    assert result.new_digest == fg._schema_digest
    assert result.added_entities == ["SchemaAccount"]
    assert result.added_fields == []
    assert any(entity["entity_type"] == "SchemaAccount" for entity in fg.schema_ir["entities"])
    assert "schema_account:account_id" in fg._application_schema_index.identity_pred_ids
    assert "SchemaAccount:exists" in fg._application_schema_index.exists_pred_ids
    assert "schema_account:label" in _field_pred_ids(fg)


def test_schema_extend_adds_non_identity_field() -> None:
    fg = _fg()

    result = fg.schema.extend(_user_adds_nickname())

    assert result.added_entities == []
    assert result.added_fields == ["SchemaUser.nickname"]
    assert "schema_user:nickname" in _field_pred_ids(fg)


def test_schema_apply_routes_register_and_extend() -> None:
    fg = _fg()

    register_result = fg.schema.apply(SchemaProject)
    extend_result = fg.schema.apply(_user_adds_nickname())

    assert register_result.added_entities == ["SchemaProject"]
    assert register_result.added_fields == []
    assert extend_result.added_entities == []
    assert extend_result.added_fields == ["SchemaUser.nickname"]


def test_schema_register_rejects_existing_entity_type() -> None:
    fg = _fg()

    with pytest.raises(SchemaConflictError) as exc_info:
        fg.schema.register(SchemaUser)

    assert exc_info.value.code == "SCHEMA_CONFLICT"
    assert "already registered" in str(exc_info.value)


def test_schema_extend_rejects_unregistered_entity_type() -> None:
    fg = _fg()

    with pytest.raises(SchemaNotFoundError) as exc_info:
        fg.schema.extend(_new_entity())

    assert exc_info.value.code == "SCHEMA_NOT_FOUND"
    assert "not registered" in str(exc_info.value)


def test_schema_extend_rejects_identity_to_field_demotion() -> None:
    fg = FactGraph.create(schema_classes=[SchemaTenantUser])
    before = _schema_state_snapshot(fg)

    with pytest.raises(SchemaNonAdditiveError) as exc_info:
        fg.schema.extend(_tenant_user_identity_to_field())

    assert exc_info.value.code == "SCHEMA_NON_ADDITIVE"
    assert "Identity bundle redesign" in str(exc_info.value)
    assert "ADR-IC §4.3.6" in str(exc_info.value)
    assert _schema_state_snapshot(fg) == before


@pytest.mark.parametrize(
    ("candidate_factory", "message_part"),
    [
        (_user_identity_added, "Identity bundle redesign"),
        (_user_field_to_identity, "Identity bundle redesign"),
        (_user_field_removed, "schema mutation is non-additive"),
        (_user_cardinality_changed, "schema mutation is non-additive"),
        (_user_type_changed, "schema mutation is non-additive"),
    ],
)
def test_schema_extend_rejects_non_additive_entity_shape(
    candidate_factory: Any,
    message_part: str,
) -> None:
    fg = _fg()

    with pytest.raises(SchemaNonAdditiveError) as exc_info:
        fg.schema.extend(candidate_factory())

    assert exc_info.value.code == "SCHEMA_NON_ADDITIVE"
    assert message_part in str(exc_info.value)
    assert "ADR-IC §4.3.6" in str(exc_info.value)


@pytest.mark.parametrize(
    "candidate_factory",
    [
        _user_identity_added,
        _user_field_to_identity,
        _user_field_removed,
        _user_cardinality_changed,
        _user_type_changed,
    ],
)
def test_schema_extend_rejects_before_any_schema_state_changes(candidate_factory: Any) -> None:
    fg = _fg()
    before = _schema_state_snapshot(fg)

    with pytest.raises(SchemaNonAdditiveError):
        fg.schema.extend(candidate_factory())

    assert _schema_state_snapshot(fg) == before


def test_schema_register_conflict_rejects_before_any_schema_state_changes() -> None:
    fg = _fg()
    before = _schema_state_snapshot(fg)

    with pytest.raises(SchemaConflictError):
        fg.schema.register(SchemaUser)

    assert _schema_state_snapshot(fg) == before


def test_schema_extend_missing_entity_rejects_before_any_schema_state_changes() -> None:
    fg = _fg()
    before = _schema_state_snapshot(fg)

    with pytest.raises(SchemaNotFoundError):
        fg.schema.extend(_new_entity())

    assert _schema_state_snapshot(fg) == before


@pytest.mark.parametrize(
    ("mutation_kind", "message_part"),
    [
        ("removed", "existing predicate id removed or changed"),
        ("owner_changed", "existing field changed for predicate"),
        ("arity_changed", "existing field changed for predicate"),
    ],
)
def test_schema_runtime_validator_protects_entity_exists_predicate(
    mutation_kind: str,
    message_part: str,
) -> None:
    current = compile_schema_from_classes([SchemaUser])
    candidate = _candidate_schema_with_exists_mutation(mutation_kind)

    with pytest.raises(SDKStoreError) as exc_info:
        validate_additive_schema_extension(
            current_schema_ir=current,
            candidate_schema_ir=candidate,
        )

    assert message_part in str(exc_info.value)


def test_schema_extend_preserves_existing_active_claims_byte_for_byte() -> None:
    fg = _fg()
    e_ref = fg.entities.create(SchemaUser, user_id="alice")
    fg.fields.set(SchemaUser.name, e_ref, "Alice")
    fg.fields.add(SchemaUser.tags, e_ref, "blue")
    before = _active_claim_fingerprint(fg, e_ref)

    result = fg.schema.extend(_user_adds_nickname())

    assert result.added_fields == ["SchemaUser.nickname"]
    assert _active_claim_fingerprint(fg, e_ref) == before


def test_schema_errors_exported_from_sdk_top_level() -> None:
    import factgraph.sdk as sdk

    assert sdk.SchemaConflictError is SchemaConflictError
    assert sdk.SchemaNotFoundError is SchemaNotFoundError
    assert sdk.SchemaNonAdditiveError is SchemaNonAdditiveError
    assert "SchemaConflictError" in sdk.__all__
    assert "SchemaNotFoundError" in sdk.__all__
    assert "SchemaNonAdditiveError" in sdk.__all__
