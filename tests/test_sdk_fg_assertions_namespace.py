from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity, SDKStore


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag: list[str] = Field()


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

    def test_no_graph_wide_assertion_query_methods_ship(self) -> None:
        sdk, _ = _seed_store()

        for name in ("active", "history", "where", "at", "version"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(sdk.assertions, name))

    def test_record_shape_remains_existing_assertion_record(self) -> None:
        sdk, ids = _seed_store()

        record = sdk.assertions.by_id(ids["name"])
        self.assertIsNotNone(record)
        assert record is not None

        for attr in ("entity_type", "field_name", "pred_id", "ref", "identity"):
            with self.subTest(attr=attr):
                self.assertFalse(hasattr(record, attr))


if __name__ == "__main__":
    unittest.main()
