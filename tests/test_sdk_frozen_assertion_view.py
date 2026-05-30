from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity, SDKStore, SDKStoreError


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag: list[str] = Field()


class _AsrtLike:
    def __init__(self, asrt_id: str) -> None:
        self.asrt_id = asrt_id


def _seed_store() -> tuple[SDKStore, dict[str, str]]:
    sdk = SDKStore([User])
    ref = sdk.ref(User, user_id="u-1")
    ids = {
        "name": sdk.set(User.name, ref, "Alice", meta={"source": "seed"}),
        "tag": sdk.add(User.tag, ref, "vip", meta={"source": "seed"}),
        "old": sdk.add(User.tag, ref, "legacy", meta={"source": "legacy"}),
    }
    sdk.retract(ids["old"])
    return sdk, ids


class FrozenAssertionViewCreationTests(unittest.TestCase):
    def test_create_with_asrt_ids_returns_frozen_assertion_view(self) -> None:
        sdk, ids = _seed_store()
        view = sdk.views.create("review_set", asrt_ids=[ids["tag"], ids["tag"], ids["old"]])

        self.assertEqual(type(view).__name__, "FrozenAssertionView")
        self.assertEqual(view.name, "review_set")
        self.assertIsInstance(view.asrt_ids, frozenset)
        self.assertEqual(view.asrt_ids, frozenset({ids["tag"], ids["old"]}))
        self.assertIs(sdk.views.get("review_set"), view)

    def test_create_with_asrts_uses_duck_typed_asrt_id_only(self) -> None:
        sdk, ids = _seed_store()
        view = sdk.views.create("from_records", asrts=[_AsrtLike(ids["name"]), _AsrtLike(ids["tag"])])

        self.assertEqual(view.asrt_ids, frozenset({ids["name"], ids["tag"]}))

    def test_empty_asrt_ids_is_accepted(self) -> None:
        sdk, _ = _seed_store()
        view = sdk.views.create("empty_review", asrt_ids=[])

        self.assertEqual(view.asrt_ids, frozenset())

    def test_missing_or_future_asrt_ids_do_not_require_ledger_existence(self) -> None:
        sdk, _ = _seed_store()
        view = sdk.views.create("future_import", asrt_ids=["external-asrt-1"])

        self.assertEqual(view.asrt_ids, frozenset({"external-asrt-1"}))

    def test_exactly_one_payload_kind_is_accepted(self) -> None:
        sdk, ids = _seed_store()

        with self.assertRaises(SDKStoreError):
            sdk.views.create("ambiguous", asrt_ids=[ids["name"]], asrts=[_AsrtLike(ids["tag"])])
        with self.assertRaises(SDKStoreError):
            sdk.views.create("missing_payload")

    def test_update_replaces_whole_frozen_membership(self) -> None:
        sdk, ids = _seed_store()
        sdk.views.create("review_set", asrt_ids=[ids["name"], ids["tag"]])

        updated = sdk.views.update("review_set", asrt_ids=[ids["old"]])

        self.assertEqual(updated.asrt_ids, frozenset({ids["old"]}))
        self.assertEqual(sdk.views.get("review_set").asrt_ids, frozenset({ids["old"]}))

    def test_patch_and_diff_are_not_shipped(self) -> None:
        sdk, _ = _seed_store()

        self.assertFalse(hasattr(sdk.views, "patch"))
        self.assertFalse(hasattr(sdk.views, "diff"))


class FrozenAssertionViewSingleMeaningTests(unittest.TestCase):
    def test_views_registry_starts_empty_without_default_entry(self) -> None:
        sdk, _ = _seed_store()

        self.assertEqual(sdk.views.list(), {})

    def test_default_view_name_is_not_builtin_or_reserved(self) -> None:
        sdk, ids = _seed_store()

        with self.assertRaises(SDKStoreError) as get_ctx:
            sdk.views.get("default")
        self.assertIn("default", str(get_ctx.exception))
        self.assertIn("not found", str(get_ctx.exception))

        with self.assertRaises(SDKStoreError) as delete_ctx:
            sdk.views.delete("default")
        self.assertIn("default", str(delete_ctx.exception))
        self.assertIn("not found", str(delete_ctx.exception))

        view = sdk.views.create("default", asrt_ids=[ids["name"]])
        self.assertEqual(type(view).__name__, "FrozenAssertionView")
        self.assertEqual(view.name, "default")
        self.assertEqual(view.asrt_ids, frozenset({ids["name"]}))

        sdk.views.delete("default")
        with self.assertRaises(SDKStoreError):
            sdk.views.get("default")

    def test_views_create_no_longer_accepts_view_spec_payload(self) -> None:
        sdk, _ = _seed_store()

        with self.assertRaises((TypeError, SDKStoreError)) as ctx:
            sdk.views.create("legacy", view_spec=object())
        msg = str(ctx.exception)
        self.assertIn("view_spec", msg)

    def test_views_get_and_list_return_only_frozen_assertion_views(self) -> None:
        sdk, ids = _seed_store()
        first = sdk.views.create("first", asrt_ids=[ids["name"]])
        second = sdk.views.create("second", asrts=[_AsrtLike(ids["tag"])])

        self.assertEqual(type(sdk.views.get("first")).__name__, "FrozenAssertionView")
        self.assertIs(sdk.views.get("first"), first)
        self.assertIs(sdk.views.get("second"), second)
        self.assertEqual(
            {name: type(view).__name__ for name, view in sdk.views.list().items()},
            {"first": "FrozenAssertionView", "second": "FrozenAssertionView"},
        )


if __name__ == "__main__":
    unittest.main()
