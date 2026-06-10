from __future__ import annotations

import unittest

from factgraph.application import (
    SchemaResolutionError,
    build_schema_index,
    field_predicate,
    field_value_type,
    materialize_identity,
    render_entity_repr,
    resolve_selector,
)
from factgraph.application.schema_runtime import EntityTypeInfo, IdentityFieldInfo, SchemaIndex
from factgraph.application.protocol import EntitySelector
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Country(Entity):
    code: str = Identity()
    name: str = Field()


class User(Entity):
    name: str = Identity()
    locale: str = Identity()
    lives_in: Country = Field()
    tag: list[str] = Field()


class Session(Entity):
    session_id: str = Identity()
    user: User = Field()


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

    def test_resolve_selector_accepts_complete_identity(self) -> None:
        index = _schema_index()

        ref = resolve_selector(
            EntitySelector(
                entity_type="User",
                identity={"name": "alice", "locale": "en"},
            ),
            index=index,
        )

        self.assertEqual(ref.entity_type, "User")
        self.assertEqual(ref.identity, {"name": "alice", "locale": "en"})
        self.assertIsNotNone(ref.encoded_ref)
        self.assertTrue(str(ref.encoded_ref).startswith("idref_v1:User:"))

    def test_resolve_selector_rejects_incomplete_identity(self) -> None:
        index = _schema_index()

        with self.assertRaises(SchemaResolutionError) as ctx:
            resolve_selector(
                EntitySelector(entity_type="User", identity={"name": "alice"}),
                index=index,
            )

        self.assertEqual(ctx.exception.code, "IDENTITY_INCOMPLETE")
        self.assertEqual(ctx.exception.details["missing_fields"], ["locale"])

    def test_resolve_selector_rejects_unknown_identity_field(self) -> None:
        index = _schema_index()

        with self.assertRaises(SchemaResolutionError) as ctx:
            resolve_selector(
                EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "unknown": "x"},
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
                ),
                index=index,
            )

        self.assertEqual(ctx.exception.code, "IDENTITY_TYPE_MISMATCH")

    def test_resolve_selector_accepts_explicit_session_identity(self) -> None:
        index = _schema_index()

        ref = resolve_selector(
            EntitySelector(
                entity_type="Session",
                identity={"session_id": "session-1"},
            ),
            index=index,
        )

        self.assertEqual(ref.entity_type, "Session")
        self.assertEqual(ref.identity, {"session_id": "session-1"})
        self.assertTrue(str(ref.encoded_ref).startswith("idref_v1:Session:"))

    def test_render_entity_repr_uses_default_first_identity_label(self) -> None:
        index = _schema_index()

        self.assertEqual(
            render_entity_repr(index, "User", {"name": "alice", "locale": "en"}),
            "User alice",
        )

    def test_render_entity_repr_uses_meta_template_and_indexes_predicate_repr(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "%CLS %user_id"

            user_id: str = Identity(repr="%CLS %ENT %FLD")
            display_name: str = Field(repr="%CLS %ENT %FLD")

        index = build_schema_index(compile_schema_from_classes([DisplayUser]))

        self.assertEqual(render_entity_repr(index, "DisplayUser", {"user_id": "u-1"}), "DisplayUser u-1")
        self.assertEqual(index.entities["DisplayUser"].meta_repr, "%CLS %user_id")
        self.assertEqual(index.entities["DisplayUser"].identity_predicates["user_id"].repr, "%CLS %ENT %FLD")
        self.assertEqual(field_predicate(index, "DisplayUser", "display_name").repr, "%CLS %ENT %FLD")

    def test_render_entity_repr_rejects_missing_identity_value(self) -> None:
        index = _schema_index()

        with self.assertRaises(SchemaResolutionError) as ctx:
            render_entity_repr(index, "User", {"locale": "en"})

        self.assertEqual(ctx.exception.code, "MISSING_ENTITY_IDENTITY_VALUE")

    def test_render_entity_repr_uses_single_pass_replacement(self) -> None:
        class OrgUnit(Entity):
            class Meta:
                repr = "%org/%org_unit"

            org: str = Identity()
            org_unit: str = Identity()

        index = build_schema_index(compile_schema_from_classes([OrgUnit]))

        self.assertEqual(
            render_entity_repr(index, "OrgUnit", {"org": "acme", "org_unit": "sales"}),
            "acme/sales",
        )

    def test_render_entity_repr_preserves_unknown_runtime_placeholders(self) -> None:
        index = SchemaIndex(
            schema_ir={},
            schema_digest="test",
            entities={
                "RuntimeOnly": EntityTypeInfo(
                    entity_type="RuntimeOnly",
                    identity_fields=(IdentityFieldInfo(name="known", type_domain="string"),),
                    exists_predicate_id="RuntimeOnly:exists",
                    identity_predicates={},
                    meta_repr="%known/%unknown",
                )
            },
            field_predicates={},
            predicates_by_id={},
            identity_pred_ids=frozenset(),
            exists_pred_ids=frozenset(),
        )

        self.assertEqual(render_entity_repr(index, "RuntimeOnly", {"known": "value"}), "value/%unknown")

    def test_render_entity_repr_does_not_reinterpret_identity_values(self) -> None:
        class OrgUnit(Entity):
            class Meta:
                repr = "%org %org_unit"

            org: str = Identity()
            org_unit: str = Identity()

        index = build_schema_index(compile_schema_from_classes([OrgUnit]))

        self.assertEqual(
            render_entity_repr(index, "OrgUnit", {"org": "%org_unit", "org_unit": "sales"}),
            "%org_unit sales",
        )

    def test_render_entity_repr_decodes_float64_for_display_only(self) -> None:
        class FloatIdentity(Entity):
            class Meta:
                repr = "Float %value"

            value: float = Identity()

        index = build_schema_index(compile_schema_from_classes([FloatIdentity]))
        canonical = "0x3ff8000000000000"

        self.assertEqual(render_entity_repr(index, "FloatIdentity", {"value": canonical}), "Float 1.5")
        self.assertEqual(
            materialize_identity("FloatIdentity", {"value": canonical}, index=index),
            {"value": canonical},
        )


if __name__ == "__main__":
    unittest.main()
