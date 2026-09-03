from __future__ import annotations

import hashlib

import pytest

from factgraph.application import build_schema_index, entity_info, resolve_selector
from factgraph.application.protocol import EntitySelector
from factgraph.core.evidence.write_protocol import retract_by_asrt, set_field
from factgraph.core.store import Store
from factgraph.core.store.premise_filter import MetaExclusion, premise_scoped_ledger
from factgraph.core.view.projector import (
    project_view_facts,
    project_view_facts_with_witness,
)
from factgraph.sdk import Entity, Identity, compile_schema_from_classes


class DomainUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()


class TripleDomain(Entity):
    first: str = Identity()
    middle: str = Identity()
    last: str = Identity()


@pytest.mark.parametrize("absent", ["first", "middle", "last"])
@pytest.mark.parametrize("mode", ["missing", "revoked", "hidden"])
def test_incomplete_identity_intersection_stays_empty(absent, mode):
    schema = compile_schema_from_classes([TripleDomain])
    store = Store(schema)
    index = build_schema_index(schema)
    info = entity_info(index, "TripleDomain")
    identity = {"first": "a", "middle": "b", "last": "c"}
    ref = resolve_selector(
        EntitySelector(entity_type="TripleDomain", identity=identity), index=index
    )
    for name, value in identity.items():
        if name == absent and mode == "missing":
            continue
        assertion = set_field(
            store.ledger,
            info.identity_predicates[name].pred_id,
            ref.encoded_ref,
            [("string", value)],
            meta={"visibility": "hidden"} if name == absent else None,
        )
        if name == absent and mode == "revoked":
            retract_by_asrt(store.ledger, assertion)
    ledger = store.ledger
    if mode == "hidden":
        ledger = premise_scoped_ledger(
            ledger,
            (MetaExclusion(key="visibility", values=frozenset({"hidden"})),),
        )
    assert project_view_facts(ledger, schema)[info.exists_predicate_id] == []
    assert project_view_facts_with_witness(ledger, schema)[info.exists_predicate_id] == []


def test_disjoint_intermediate_identity_intersection_stays_empty():
    schema = compile_schema_from_classes([TripleDomain])
    store = Store(schema)
    index = build_schema_index(schema)
    info = entity_info(index, "TripleDomain")
    for name, first in [("first", "a"), ("middle", "other"), ("last", "a")]:
        identity = {"first": first, "middle": "b", "last": "c"}
        ref = resolve_selector(
            EntitySelector(entity_type="TripleDomain", identity=identity), index=index
        )
        set_field(
            store.ledger,
            info.identity_predicates[name].pred_id,
            ref.encoded_ref,
            [("string", identity[name])],
        )
    assert project_view_facts(store.ledger, schema)[info.exists_predicate_id] == []
    assert project_view_facts_with_witness(store.ledger, schema)[info.exists_predicate_id] == []


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

    assert project_view_facts(store.ledger, store.schema_ir)[exists_pred] == [(ref.encoded_ref,)]
    (row,) = project_view_facts_with_witness(store.ledger, store.schema_ir)[exists_pred]
    assert row.fact_tuple == (ref.encoded_ref,)
    assert row.asrt_id.startswith("virtual-entity-exists:v1:")
    payload = "\x00".join(
        (
            "factgraph.virtual-entity-exists.v1",
            exists_pred,
            ref.encoded_ref,
            *sorted((first, second)),
        )
    ).encode("utf-8")
    assert row.asrt_id == "virtual-entity-exists:v1:" + hashlib.sha256(payload).hexdigest()
    assert row.witness_kind == "virtual"
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
    assert project_view_facts(store.ledger, store.schema_ir)[exists_pred] == [(ref.encoded_ref,)]
