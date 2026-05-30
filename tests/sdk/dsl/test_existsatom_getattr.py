from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity
from factgraph.sdk.dsl import vars
from factgraph.sdk.dsl.expr import AttrRef, lower_where


class User(Entity):
    user_id: str = Identity()
    status: str = Field()


class ExistsAtomGetattrTests(unittest.TestCase):
    def test_entity_call_field_returns_attr_ref_with_entity_type(self) -> None:
        with vars("u") as (u,):
            attr = User(u).status

        self.assertIsInstance(attr, AttrRef)
        self.assertEqual(attr.record_var, u)
        self.assertEqual(attr.field_name, "status")
        self.assertEqual(attr.entity_type, "User")

    def test_logic_var_getattr_remains_legacy_entity_type_none(self) -> None:
        with vars("u") as (u,):
            attr = u.status

        self.assertIsInstance(attr, AttrRef)
        self.assertEqual(attr.record_var, u)
        self.assertEqual(attr.field_name, "status")
        self.assertIsNone(attr.entity_type)

    def test_lower_compare_uses_entity_type_without_prior_exists_atom(self) -> None:
        with vars("u") as (u,):
            where_ir = lower_where([User(u).status == "active"])

        self.assertEqual(where_ir[0], ("pred", "User:exists", [u.token]))
        self.assertEqual(where_ir[1], ("pred", "user:status", [u.token, "active"]))


if __name__ == "__main__":
    unittest.main()
