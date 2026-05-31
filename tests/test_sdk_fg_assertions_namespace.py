from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity, SDKStore


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag: list[str] = Field()


def _seed_store() -> tuple[SDKStore, dict[str, str]]:
    sdk = SDKStore([User])
    ref = sdk.entities.ref(User, user_id="u-1")
    ids = {
        "name": sdk.fields.set(User.name, ref, "Alice", meta={"source": "seed"}),
        "tag": sdk.fields.add(User.tag, ref, "vip", meta={"source": "seed"}),
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
        view = sdk.assertion_views.create("review_set", asrt_ids=[ids["name"], "missing-asrt", ids["tag"]])

        records = sdk.assertions.by_ids(view.asrt_ids)

        self.assertEqual({record.asrt_id for record in records}, {ids["name"], ids["tag"]})
        self.assertTrue(hasattr(records, "where"))
        self.assertEqual(records.where(value="vip").one().asrt_id, ids["tag"])

    def test_by_ids_strict_rejects_missing_ids(self) -> None:
        sdk, ids = _seed_store()

        with self.assertRaises(Exception) as ctx:
            sdk.assertions.by_ids([ids["name"], "missing-asrt"], strict=True)
        self.assertIn("missing-asrt", str(ctx.exception))

    def test_by_ids_strict_rejects_duplicate_input_before_deduplication(self) -> None:
        sdk, ids = _seed_store()

        with self.assertRaises(Exception) as ctx:
            sdk.assertions.by_ids([ids["name"], ids["name"]], strict=True)
        self.assertIn("duplicate assertion id", str(ctx.exception))

    def test_field_assertion_view_by_ids_strict_matches_top_level_behavior(self) -> None:
        sdk, ids = _seed_store()
        view = sdk.assertions.field(User.name)

        self.assertEqual(view.by_ids([ids["name"]], strict=True).one().asrt_id, ids["name"])
        with self.assertRaises(Exception) as missing_ctx:
            view.by_ids([ids["name"], "missing-asrt"], strict=True)
        self.assertIn("missing-asrt", str(missing_ctx.exception))
        with self.assertRaises(Exception) as duplicate_ctx:
            view.by_ids([ids["name"], ids["name"]], strict=True)
        self.assertIn("duplicate assertion id", str(duplicate_ctx.exception))

    def test_audit_explain_and_conflicts_accept_assertion_record(self) -> None:
        sdk, ids = _seed_store()
        record = sdk.assertions.by_id(ids["name"])
        self.assertIsNotNone(record)
        assert record is not None

        explanation = sdk.audit.explain(record)
        self.assertEqual(explanation["asrt_id"], ids["name"])
        self.assertEqual(explanation["pred_id"], record.pred_id)
        self.assertEqual(explanation["e_ref"], record.e_ref)
        self.assertTrue(explanation["chosen"])

        conflicts = sdk.audit.conflicts(record)
        self.assertEqual(conflicts["pred_id"], record.pred_id)
        self.assertEqual(conflicts["e_ref"], record.e_ref)
        self.assertIn(ids["name"], conflicts["active_asrt_ids"])

    def test_audit_conflicts_accepts_entity_ref_and_field_name(self) -> None:
        sdk, ids = _seed_store()
        ref = sdk.entities.ref(User, user_id="u-1")

        conflicts = sdk.audit.conflicts((ref, "name"))

        self.assertEqual(conflicts["e_ref"], ref)
        self.assertIn(ids["name"], conflicts["active_asrt_ids"])

    def test_expected_graph_wide_assertion_query_methods_ship(self) -> None:
        sdk, _ = _seed_store()

        for name in ("active", "all", "where", "field", "by_id", "by_ids", "retract"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(sdk.assertions, name))
        for name in ("history", "at", "version"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(sdk.assertions, name))

    def test_record_shape_remains_existing_assertion_record(self) -> None:
        sdk, ids = _seed_store()

        record = sdk.assertions.by_id(ids["name"])
        self.assertIsNotNone(record)
        assert record is not None

        for attr in ("entity_type", "field_name", "pred_id"):
            with self.subTest(attr=attr):
                self.assertTrue(hasattr(record, attr))
        for attr in ("ref", "identity"):
            with self.subTest(attr=attr):
                self.assertFalse(hasattr(record, attr))


if __name__ == "__main__":
    unittest.main()
