from __future__ import annotations

import unittest

from kernel.sdk import Entity, Field, Identity, SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _seed_store() -> tuple[SDKStore, dict[str, str]]:
    sdk = SDKStore([User])
    ref = sdk.ref(User, user_id="u-1")
    ids = {
        "name": sdk.set(User.name, ref, "Alice", meta={"source": "seed"}),
        "tag": sdk.add(User.tag, ref, "vip", meta={"source": "seed"}),
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

    def test_graph_wide_assertion_collection_methods_ship(self) -> None:
        sdk, ids = _seed_store()

        active = sdk.assertions.active()
        all_records = sdk.assertions.all()
        field_records = sdk.assertions.field(User.tag).active()

        self.assertEqual(active.where(value="Alice").one().asrt_id, ids["name"])
        self.assertEqual(all_records.where(value="vip").one().asrt_id, ids["tag"])
        self.assertEqual(field_records.one().asrt_id, ids["tag"])
        for name in ("where", "at", "version", "history"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(sdk.assertions, name))

    def test_record_shape_includes_assertion_context(self) -> None:
        sdk, ids = _seed_store()

        record = sdk.assertions.by_id(ids["name"])
        self.assertIsNotNone(record)
        assert record is not None

        self.assertEqual(record.entity_type, "User")
        self.assertEqual(record.field_name, "name")
        self.assertEqual(record.pred_id, "user:name")
        self.assertTrue(record.e_ref.startswith("idref_v1:User:"))
        for attr in ("ref", "identity", "is_revoked"):
            with self.subTest(attr=attr):
                self.assertFalse(hasattr(record, attr))


if __name__ == "__main__":
    unittest.main()
