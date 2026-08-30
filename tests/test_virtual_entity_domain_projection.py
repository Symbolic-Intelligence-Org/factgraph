from __future__ import annotations

from factgraph.application import build_schema_index, entity_info, resolve_selector
from factgraph.application.protocol import EntitySelector
from factgraph.core.evidence.write_protocol import retract_by_asrt, set_field
from factgraph.core.store import Store
from factgraph.core.view.projector import (
    project_view_facts,
    project_view_facts_with_witness,
)
from factgraph.sdk import Entity, Identity, compile_schema_from_classes


class DomainUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()


def _fixture():
    schema = compile_schema_from_classes([DomainUser])
    store = Store(schema)
    index = build_schema_index(schema)
    ref = resolve_selector(
        EntitySelector(
            entity_type="DomainUser",
            identity={"user_id": "alice", "tenant_id": "acme"},
        ),
        index=index,
    )
    assert ref.encoded_ref is not None
    return store, index, ref


def _identity(store, index, ref, field_name: str) -> str:
    info = entity_info(index, "DomainUser")
    field = next(item for item in info.identity_fields if item.name == field_name)
    predicate = info.identity_predicates[field_name]
    return set_field(
        store.ledger,
        predicate.pred_id,
        ref.encoded_ref,
        [(field.type_domain, ref.identity[field_name])],
    )


def test_complete_identity_bundle_projects_one_virtual_domain_row():
    store, index, ref = _fixture()
    first = _identity(store, index, ref, "user_id")
    second = _identity(store, index, ref, "tenant_id")
    exists_pred = entity_info(index, "DomainUser").exists_predicate_id

    assert project_view_facts(store.ledger, store.schema_ir)[exists_pred] == [
        (ref.encoded_ref,)
    ]
    (row,) = project_view_facts_with_witness(store.ledger, store.schema_ir)[
        exists_pred
    ]
    assert row.fact_tuple == (ref.encoded_ref,)
    assert row.asrt_id.startswith("virtual-entity-exists:v1:")
    assert first != second


def test_partial_or_revoked_identity_bundle_projects_no_domain_row():
    store, index, ref = _fixture()
    _identity(store, index, ref, "user_id")
    tenant = _identity(store, index, ref, "tenant_id")
    exists_pred = entity_info(index, "DomainUser").exists_predicate_id
    retract_by_asrt(store.ledger, tenant)

    assert project_view_facts(store.ledger, store.schema_ir)[exists_pred] == []


def test_legacy_marker_alone_is_not_domain_authority_and_does_not_duplicate():
    store, index, ref = _fixture()
    exists_pred = entity_info(index, "DomainUser").exists_predicate_id
    set_field(store.ledger, exists_pred, ref.encoded_ref, [])
    assert project_view_facts(store.ledger, store.schema_ir)[exists_pred] == []

    _identity(store, index, ref, "user_id")
    _identity(store, index, ref, "tenant_id")
    assert project_view_facts(store.ledger, store.schema_ir)[exists_pred] == [
        (ref.encoded_ref,)
    ]
