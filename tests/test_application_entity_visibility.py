from factgraph.application import (
    build_schema_index,
    entity_info,
    is_entity_identity_bundle_active,
    resolve_selector,
)
from factgraph.application.protocol import EntitySelector
from factgraph.core.evidence.write_protocol import retract_by_asrt, set_field
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class VisibilityUser(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()


def _store_index_ref(identity: dict[str, object] | None = None):
    schema_ir = compile_schema_from_classes([VisibilityUser])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    selector = EntitySelector(
        entity_type="VisibilityUser",
        identity=dict(identity or {"user_id": "alice", "tenant_id": "acme"}),
    )
    ref = resolve_selector(selector, index=index)
    assert ref.encoded_ref is not None
    return store, index, ref


def _write_identity_claim(
    store: Store,
    index,
    ref,
    field_name: str,
    value: object | None = None,
) -> str:
    info = entity_info(index, ref.entity_type)
    field = next(row for row in info.identity_fields if row.name == field_name)
    pred = info.identity_predicates[field_name]
    return set_field(
        store.ledger,
        pred.pred_id,
        ref.encoded_ref or "",
        [(field.type_domain, ref.identity[field_name] if value is None else value)],
    )


def test_identity_bundle_active_true_for_complete_active_bundle():
    store, index, ref = _store_index_ref()
    _write_identity_claim(store, index, ref, "user_id")
    _write_identity_claim(store, index, ref, "tenant_id")

    assert is_entity_identity_bundle_active(
        store=store,
        schema_index=index,
        entity_type="VisibilityUser",
        e_ref=ref.encoded_ref or "",
        identity_values=dict(ref.identity),
    ) is True


def test_identity_bundle_active_false_when_no_identity_claims_exist():
    store, index, ref = _store_index_ref()

    assert is_entity_identity_bundle_active(
        store=store,
        schema_index=index,
        entity_type="VisibilityUser",
        e_ref=ref.encoded_ref or "",
        identity_values=dict(ref.identity),
    ) is False


def test_identity_bundle_active_false_for_partial_identity_claim_bundle():
    store, index, ref = _store_index_ref()
    _write_identity_claim(store, index, ref, "user_id")

    assert is_entity_identity_bundle_active(
        store=store,
        schema_index=index,
        entity_type="VisibilityUser",
        e_ref=ref.encoded_ref or "",
        identity_values=dict(ref.identity),
    ) is False


def test_identity_bundle_active_false_for_mismatched_identity_value():
    store, index, ref = _store_index_ref()
    _write_identity_claim(store, index, ref, "user_id")
    _write_identity_claim(store, index, ref, "tenant_id", value="other")

    assert is_entity_identity_bundle_active(
        store=store,
        schema_index=index,
        entity_type="VisibilityUser",
        e_ref=ref.encoded_ref or "",
        identity_values=dict(ref.identity),
    ) is False


def test_identity_bundle_active_false_after_identity_claim_revoke():
    store, index, ref = _store_index_ref()
    _write_identity_claim(store, index, ref, "user_id")
    tenant_asrt_id = _write_identity_claim(store, index, ref, "tenant_id")

    retract_by_asrt(store.ledger, tenant_asrt_id)

    assert is_entity_identity_bundle_active(
        store=store,
        schema_index=index,
        entity_type="VisibilityUser",
        e_ref=ref.encoded_ref or "",
        identity_values=dict(ref.identity),
    ) is False


def test_identity_bundle_active_ignores_exists_claim_without_identity_bundle():
    store, index, ref = _store_index_ref()
    info = entity_info(index, ref.entity_type)
    set_field(store.ledger, info.exists_predicate_id, ref.encoded_ref or "", [])

    assert is_entity_identity_bundle_active(
        store=store,
        schema_index=index,
        entity_type="VisibilityUser",
        e_ref=ref.encoded_ref or "",
        identity_values=dict(ref.identity),
    ) is False
