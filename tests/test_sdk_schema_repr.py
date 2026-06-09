from __future__ import annotations

import json
import unittest

from factgraph.core.schema.schema_ir import schema_digest
from factgraph.sdk import Entity, Field, Identity, Relationship
from factgraph.sdk.compile import build_authoring_schema_from_classes, compile_schema_from_classes
from factgraph.sdk.schema import SDKSchemaError


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


class SDKSchemaReprTests(unittest.TestCase):
    def test_field_identity_and_meta_repr_are_accepted_but_not_authored(self) -> None:
        class ReprUser(Entity):
            class Meta:
                repr = "%CLS %user_id"

            user_id: str = Identity(repr="%CLS %ENT %FLD")
            display_name: str = Field(repr="%CLS %ENT %FLD")

        self.assertEqual(ReprUser.user_id.repr, "%CLS %ENT %FLD")
        self.assertEqual(ReprUser.display_name.repr, "%CLS %ENT %FLD")

        authoring = build_authoring_schema_from_classes([ReprUser])
        self.assertFalse(_contains_key(authoring, "repr"))

    def test_schema_repr_does_not_change_schema_digest_or_compiled_ir(self) -> None:
        DigestUser = type(
            "DigestUser",
            (Entity,),
            {
                "__annotations__": {"user_id": str, "display_name": str},
                "user_id": Identity(),
                "display_name": Field(),
            },
        )
        DigestUserWithRepr = type(
            "DigestUser",
            (Entity,),
            {
                "__annotations__": {"user_id": str, "display_name": str},
                "user_id": Identity(repr="%CLS %ENT %FLD"),
                "display_name": Field(repr="%CLS %ENT %FLD"),
            },
        )

        without_repr = compile_schema_from_classes([DigestUser], generated_at="2026-06-09T00:00:00Z")
        with_repr = compile_schema_from_classes([DigestUserWithRepr], generated_at="2026-06-09T00:00:00Z")

        self.assertEqual(schema_digest(without_repr), schema_digest(with_repr))
        self.assertNotIn('"repr"', json.dumps(with_repr, sort_keys=True))

    def test_member_repr_rejects_sibling_and_unknown_placeholders(self) -> None:
        for template in ("%display_name", "%UNKNOWN"):
            with self.subTest(template=template):
                with self.assertRaises(SDKSchemaError):

                    class _BadMember(Entity):
                        user_id: str = Identity(repr=template)
                        display_name: str = Field()

    def test_meta_repr_rejects_ent_fld_and_non_identity_placeholders(self) -> None:
        for template in ("%ENT", "%FLD", "%display_name", "%UNKNOWN"):
            with self.subTest(template=template):
                with self.assertRaises(SDKSchemaError):

                    class _BadMeta(Entity):
                        class Meta:
                            repr = template

                        user_id: str = Identity()
                        display_name: str = Field()

    def test_repr_extends_form_i_allow_list_without_opening_unknown_kwargs(self) -> None:
        Identity(repr="%FLD")
        Field(repr="%FLD")

        with self.assertRaises(SDKSchemaError):
            Identity(label="%FLD")
        with self.assertRaises(SDKSchemaError):
            Field(label="%FLD")

    def test_reserved_identity_name_collisions_are_rejected_when_meta_repr_is_used(self) -> None:
        with self.assertRaises(SDKSchemaError):

            class _BadReservedIdentity(Entity):
                class Meta:
                    repr = "%CLS"

                CLS: str = Identity()

    def test_relationship_field_repr_uses_same_member_validation(self) -> None:
        class _User(Entity):
            user_id: str = Identity()

        with self.assertRaises(SDKSchemaError):

            class _BadRelationship(Relationship):
                from_entity = _User
                to_entity = _User
                label: str = Field(repr="%other")


if __name__ == "__main__":
    unittest.main()
