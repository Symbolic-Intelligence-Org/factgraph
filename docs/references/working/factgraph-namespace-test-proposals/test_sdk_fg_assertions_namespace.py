from __future__ import annotations

import unittest

from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _seed_store() -> tuple[SDKStore, dict[str, str]]:
    sdk = FactGraph.create(schema_classes=[User])
    ref = sdk.read.ref(User, user_id="u-1")
    ids = {
        "name": sdk.write.set(User.name, ref, "Alice", meta={"source": "seed"}),
        "tag": sdk.write.add(User.tag, ref, "vip", meta={"source": "seed"}),
    }
    return sdk, ids


class FGAssertionsNamespaceTests(unittest.TestCase):
    def test_assertions_namespace_is_read_only_and_idempotent(self) -> None:
        sdk, _ = _seed_store()

        self.assertTrue(hasattr(sdk, "assertions"))
        self.assertIs(sdk.assertions, sdk.assertions)
        with self.assertRaises(Exception) as ctx:
            sdk.assertions.anything = object()  # type: ignore[attr-defined]
        self.assertIn("assertions", str(ctx.exception))

    def test_by_id_returns_record_or_none(self) -> None:
        sdk, ids = _seed_store()

        record = sdk.assertions.by_id(ids["name"])

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.asrt_id, ids["name"])
        self.assertEqual(record.value, "Alice")
        self.assertIsNone(sdk.assertions.by_id("missing-asrt"))

    def test_by_ids_accepts_iterable_and_skips_unknowns(self) -> None:
        sdk, ids = _seed_store()
        view = sdk.views.create("review_set", asrt_ids=[ids["name"], "missing-asrt", ids["tag"]])

        records = sdk.assertions.by_ids(view.asrt_ids)

        self.assertEqual({record.asrt_id for record in records}, {ids["name"], ids["tag"]})
        self.assertTrue(hasattr(records, "where"))
        self.assertEqual(records.where(value="vip").one().asrt_id, ids["tag"])

    def test_by_ids_has_no_strict_parameter_in_first_slice(self) -> None:
        sdk, ids = _seed_store()

        with self.assertRaises(TypeError):
            sdk.assertions.by_ids([ids["name"]], strict=True)

    def test_assertions_all_and_active_are_graph_scoped_record_sets(self) -> None:
        sdk, ids = _seed_store()
        sdk.write.retract(ids["tag"], meta={"source": "review"})

        all_records = sdk.assertions.all()
        active_records = sdk.assertions.active()

        all_ids = {record.asrt_id for record in all_records}
        active_ids = {record.asrt_id for record in active_records}
        self.assertGreaterEqual(len(all_records), 4)
        self.assertIn(ids["name"], all_ids)
        self.assertIn(ids["tag"], all_ids)
        self.assertIn(ids["name"], active_ids)
        self.assertNotIn(ids["tag"], active_ids)

    def test_assertions_namespace_still_has_no_chain_helpers_directly(self) -> None:
        sdk, _ = _seed_store()

        for name in ("history", "where", "at", "version"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(sdk.assertions, name))

    def test_assertions_field_returns_field_scoped_records(self) -> None:
        sdk, ids = _seed_store()

        records = sdk.assertions.field(User.name).all()

        self.assertEqual([record.asrt_id for record in records], [ids["name"]])
        self.assertEqual(records.one().value, "Alice")

    def test_assertions_field_rejects_string_field_names(self) -> None:
        sdk, _ = _seed_store()

        with self.assertRaisesRegex(Exception, "Field descriptor"):
            sdk.assertions.field("user:name")  # type: ignore[arg-type]

    def test_record_shape_remains_existing_assertion_record(self) -> None:
        sdk, ids = _seed_store()

        record = sdk.assertions.by_id(ids["name"])
        self.assertIsNotNone(record)
        assert record is not None

        expected_context = {
            "entity_type": "User",
            "field_name": "name",
            "pred_id": "user:name",
        }
        for attr, value in expected_context.items():
            with self.subTest(attr=attr):
                self.assertEqual(getattr(record, attr), value)
        self.assertFalse(hasattr(record, "identity"))


if __name__ == "__main__":
    unittest.main()
