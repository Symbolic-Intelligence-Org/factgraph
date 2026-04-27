from __future__ import annotations

import unittest

from kernel.application import (
    SchemaResolutionError,
    build_schema_index,
    field_predicate,
    field_value_type,
    resolve_selector,
)
from kernel.application.protocol import EntitySelector
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    name: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    lives_in: Country = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


class Session(Entity):
    session_id: str = Identity(default_factory="uuid4")
    user: User = Field(cardinality="single")


def _schema_index():
    schema_ir = compile_schema_from_classes([Country, User, Session])
    return build_schema_index(schema_ir)


class ApplicationSchemaRuntimeTests(unittest.TestCase):
    def test_build_schema_index_indexes_field_predicates(self) -> None:
        index = _schema_index()

        self.assertIn("User", index.entities)
        self.assertEqual(index.entities["User"].exists_predicate_id, "User:exists")
        self.assertEqual(field_predicate(index, "User", "lives_in").cardinality, "single")
        self.assertEqual(field_predicate(index, "User", "tag").cardinality, "multi")

    def test_field_value_type_reports_scalar_multi(self) -> None:
        index = _schema_index()

        field_type = field_value_type(index, "User", "tag")

        self.assertEqual(field_type.value_kind, "scalar")
        self.assertEqual(field_type.cardinality, "multi")
        self.assertEqual(field_type.scalar_domain, "string")
        self.assertIsNone(field_type.ref_target_type)

    def test_field_value_type_reports_entity_ref_single(self) -> None:
        index = _schema_index()

        field_type = field_value_type(index, "User", "lives_in")

        self.assertEqual(field_type.value_kind, "entity_ref")
        self.assertEqual(field_type.cardinality, "single")
        self.assertIsNone(field_type.scalar_domain)
        self.assertIsNone(field_type.ref_target_type)

    def test_resolve_selector_materializes_default_when_allowed(self) -> None:
        index = _schema_index()

        ref = resolve_selector(
            EntitySelector(
                entity_type="User",
                identity={"name": "alice"},
                allow_identity_defaults=True,
            ),
            index=index,
        )

        self.assertEqual(ref.entity_type, "User")
        self.assertEqual(ref.identity, {"name": "alice", "locale": "en"})
        self.assertIsNotNone(ref.encoded_ref)
        self.assertTrue(str(ref.encoded_ref).startswith("idref_v1:User:"))

    def test_resolve_selector_rejects_defaults_when_not_allowed(self) -> None:
        index = _schema_index()

        with self.assertRaises(SchemaResolutionError) as ctx:
            resolve_selector(
                EntitySelector(entity_type="User", identity={"name": "alice"}),
                index=index,
            )

        self.assertEqual(ctx.exception.code, "IDENTITY_DEFAULTS_NOT_ALLOWED")

    def test_resolve_selector_rejects_unknown_identity_field(self) -> None:
        index = _schema_index()

        with self.assertRaises(SchemaResolutionError) as ctx:
            resolve_selector(
                EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "unknown": "x"},
                    allow_identity_defaults=True,
                ),
                index=index,
            )

        self.assertEqual(ctx.exception.code, "UNKNOWN_IDENTITY_FIELD")

    def test_resolve_selector_rejects_unknown_entity_type(self) -> None:
        index = _schema_index()

        with self.assertRaises(SchemaResolutionError) as ctx:
            resolve_selector(
                EntitySelector(entity_type="Unknown", identity={"name": "alice"}),
                index=index,
            )

        self.assertEqual(ctx.exception.code, "ENTITY_TYPE_NOT_FOUND")

    def test_resolve_selector_rejects_identity_type_mismatch(self) -> None:
        index = _schema_index()

        with self.assertRaises(SchemaResolutionError) as ctx:
            resolve_selector(
                EntitySelector(
                    entity_type="User",
                    identity={"name": 123, "locale": "en"},
                    allow_identity_defaults=True,
                ),
                index=index,
            )

        self.assertEqual(ctx.exception.code, "IDENTITY_TYPE_MISMATCH")

    def test_resolve_selector_materializes_uuid4_default_factory(self) -> None:
        index = _schema_index()

        ref = resolve_selector(
            EntitySelector(
                entity_type="Session",
                identity={},
                allow_identity_defaults=True,
            ),
            index=index,
        )

        self.assertEqual(ref.entity_type, "Session")
        self.assertIn("session_id", ref.identity)
        self.assertIsInstance(ref.identity["session_id"], str)
        self.assertTrue(ref.identity["session_id"])


if __name__ == "__main__":
    unittest.main()
