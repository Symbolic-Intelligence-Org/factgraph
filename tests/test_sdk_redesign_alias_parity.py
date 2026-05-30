"""Namespace-contract regression tests after flat SDK aliases were removed."""

from __future__ import annotations

import unittest

from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStore


class Person(Entity):
    pid: str = Identity()
    name: str = Field()
    age: int = Field()


def _new_fg() -> FactGraph:
    return FactGraph.from_schema_classes([Person])


class FactGraphIsSDKStoreAliasTests(unittest.TestCase):
    """`FactGraph` and `SDKStore` remain the same class object."""

    def test_factgraph_is_sdkstore(self) -> None:
        self.assertIs(FactGraph, SDKStore)

    def test_factgraph_constructs_sdkstore_instance(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg, SDKStore)
        self.assertIsInstance(fg, FactGraph)


class CanonicalNamespaceTests(unittest.TestCase):
    def test_flat_and_read_write_shortcuts_are_removed(self) -> None:
        fg = _new_fg()

        for name in ("set", "add", "retract", "edit", "get", "ref", "find", "match", "read", "write"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(fg, name))

    def test_entities_and_fields_reproduce_legacy_read_write_flow(self) -> None:
        fg = _new_fg()
        ref = fg.entities.ref(Person, pid="p-1")
        fg.fields.set(Person.name, ref, "Alice")

        row = fg.entities.get(Person, pid="p-1")
        rows = fg.entities.where(Person)

        self.assertEqual(row.name, "Alice")
        self.assertEqual([item.name for item in rows], ["Alice"])

    def test_field_and_assertion_namespace_work_together(self) -> None:
        fg = _new_fg()
        ref = fg.entities.ref(Person, pid="p-1")
        asrt_id = fg.fields.set(Person.name, ref, "Alice")

        record = fg.assertions.by_id(asrt_id)
        revoker = fg.assertions.retract(asrt_id)

        self.assertEqual(record.value, "Alice")
        self.assertIsInstance(revoker, str)


if __name__ == "__main__":
    unittest.main()
