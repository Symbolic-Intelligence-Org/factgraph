from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity
from factgraph.sdk.dsl.expr import ExistsAtom
from factgraph.sdk.schema import _is_sdk_dsl_value, _looks_like_sdk_dsl_entity_call


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class SchemaEllipsisTests(unittest.TestCase):
    def test_entity_positional_ellipsis_returns_exists_atom_with_anonymous_var(self) -> None:
        atom = User(...)

        self.assertIsInstance(atom, ExistsAtom)
        self.assertEqual(atom.entity_type, "User")
        self.assertIsNone(atom.var.label)
        self.assertIsInstance(atom.var.token, str)
        self.assertTrue(atom.var.token.startswith("$"))

    def test_two_independent_ellipsis_calls_get_distinct_tokens(self) -> None:
        first = User(...)
        second = User(...)

        self.assertNotEqual(first.var.token, second.var.token)

    def test_ellipsis_is_not_global_sdk_dsl_value(self) -> None:
        self.assertFalse(_is_sdk_dsl_value(Ellipsis))

    def test_only_positional_single_ellipsis_looks_like_dsl_entity_call(self) -> None:
        self.assertTrue(_looks_like_sdk_dsl_entity_call((Ellipsis,), {}))
        self.assertFalse(_looks_like_sdk_dsl_entity_call((), {"name": Ellipsis}))


if __name__ == "__main__":
    unittest.main()
