from __future__ import annotations

import unittest

from factpy.application import (
    build_schema_index,
    entity_info,
    execute_read_request,
    field_predicate,
    hydrate_entity,
    resolve_selector,
)
from factpy.application.protocol import EntityReadRequest, EntityRef, EntitySelector
from factpy.core.evidence.write_protocol import set_field
from factpy.core.store import Store
from factpy.sdk import Entity, Field, Identity, compile_schema_from_classes


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    name: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    lives_in: Country = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _build_store() -> tuple[Store, object]:
    schema_ir = compile_schema_from_classes([Country, User])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _write_entity_exists(store: Store, index, ref: EntityRef) -> None:
    info = entity_info(index, ref.entity_type)
    set_field(store.ledger, info.exists_predicate_id, ref.encoded_ref or "", [])
    for field in info.identity_fields:
        pred = info.identity_predicates[field.name]
        set_field(
            store.ledger,
            pred.pred_id,
            ref.encoded_ref or "",
            [(field.type_domain, ref.identity[field.name])],
        )


def _seed_user_graph() -> tuple[Store, object, EntityRef, EntityRef]:
    store, index = _build_store()

    country_ref = resolve_selector(
        EntitySelector(entity_type="Country", identity={"code": "DE"}),
        index=index,
    )
    user_ref = resolve_selector(
        EntitySelector(
            entity_type="User",
            identity={"name": "alice"},
            allow_identity_defaults=True,
        ),
        index=index,
    )

    _write_entity_exists(store, index, country_ref)
    _write_entity_exists(store, index, user_ref)

    set_field(
        store.ledger,
        field_predicate(index, "Country", "name").pred_id,
        country_ref.encoded_ref or "",
        [("string", "Germany")],
    )
    set_field(
        store.ledger,
        field_predicate(index, "User", "lives_in").pred_id,
        user_ref.encoded_ref or "",
        [("entity_ref", country_ref.encoded_ref or "")],
    )
    set_field(
        store.ledger,
        field_predicate(index, "User", "tag").pred_id,
        user_ref.encoded_ref or "",
        [("string", "admin")],
    )
    set_field(
        store.ledger,
        field_predicate(index, "User", "tag").pred_id,
        user_ref.encoded_ref or "",
        [("string", "beta")],
    )
    return store, index, user_ref, country_ref


class ApplicationEntityViewTests(unittest.TestCase):
    def test_hydrate_entity_restores_identity_and_entity_refs(self) -> None:
        store, index, user_ref, country_ref = _seed_user_graph()

        snapshot = hydrate_entity(user_ref.encoded_ref or "", store=store, index=index)

        self.assertEqual(snapshot.ref, user_ref)
        self.assertEqual(snapshot.fields["tag"].value, ("admin", "beta"))
        self.assertEqual(snapshot.fields["lives_in"].value, country_ref)

    def test_hydrate_entity_includes_assertions(self) -> None:
        store, index, user_ref, _ = _seed_user_graph()

        snapshot = hydrate_entity(
            user_ref.encoded_ref or "",
            store=store,
            index=index,
            include_assertions=True,
            include_history=True,
        )

        self.assertIn("tag", snapshot.assertions)
        self.assertEqual(len(snapshot.assertions["tag"].active), 2)
        self.assertEqual(len(snapshot.assertions["tag"].history), 2)

    def test_execute_read_request_get_returns_snapshot(self) -> None:
        store, index, user_ref, _ = _seed_user_graph()

        response = execute_read_request(
            EntityReadRequest(
                mode="get",
                entity_type="User",
                selector=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice"},
                    allow_identity_defaults=True,
                ),
            ),
            store=store,
            index=index,
        )

        self.assertEqual(response.errors, ())
        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].ref, user_ref)

    def test_execute_read_request_get_returns_not_found_for_missing_entity(self) -> None:
        store, index = _build_store()

        response = execute_read_request(
            EntityReadRequest(
                mode="get",
                entity_type="User",
                selector=EntitySelector(
                    entity_type="User",
                    identity={"name": "missing"},
                    allow_identity_defaults=True,
                ),
            ),
            store=store,
            index=index,
        )

        self.assertEqual(response.items, ())
        self.assertEqual(len(response.errors), 1)
        self.assertEqual(response.errors[0].code, "ENTITY_NOT_FOUND")

    def test_execute_read_request_find_applies_multi_value_filters(self) -> None:
        store, index, user_ref, _ = _seed_user_graph()

        other_ref = resolve_selector(
            EntitySelector(
                entity_type="User",
                identity={"name": "bob"},
                allow_identity_defaults=True,
            ),
            index=index,
        )
        _write_entity_exists(store, index, other_ref)
        set_field(
            store.ledger,
            field_predicate(index, "User", "tag").pred_id,
            other_ref.encoded_ref or "",
            [("string", "viewer")],
        )

        response = execute_read_request(
            EntityReadRequest(
                mode="find",
                entity_type="User",
                field_filters={"tag": "admin"},
            ),
            store=store,
            index=index,
        )

        self.assertEqual(response.errors, ())
        self.assertEqual([item.ref for item in response.items], [user_ref])


if __name__ == "__main__":
    unittest.main()
