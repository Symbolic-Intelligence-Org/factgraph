from __future__ import annotations

import unittest

from kernel.core.store.types import ViewSpec
from kernel.sdk import Entity, Field, Identity, SDKStore, SDKStoreError


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


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


class LegacyViewSpecCompatibilityTests(unittest.TestCase):
    def test_legacy_views_manager_behavior_is_preserved(self) -> None:
        sdk, _ = _seed_store()
        spec = ViewSpec(confidence_strategy="max")

        created = sdk.views.create("preferred", spec)
        self.assertIs(created, spec)
        self.assertIs(sdk.views.get("preferred"), spec)
        self.assertIs(sdk.views.list()["preferred"], spec)

        replacement = ViewSpec(confidence_strategy="median")
        updated = sdk.views.update("preferred", replacement)
        self.assertIs(updated, replacement)
        self.assertIs(sdk.views.get("preferred"), replacement)

        sdk.views.delete("preferred")
        with self.assertRaises(SDKStoreError):
            sdk.views.get("preferred")

    def test_default_view_protection_is_preserved(self) -> None:
        sdk, _ = _seed_store()

        with self.assertRaises(SDKStoreError):
            sdk.views.delete("default")


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
            sdk.views.create("ambiguous", ViewSpec(), asrt_ids=[ids["name"]])
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


if __name__ == "__main__":
    unittest.main()
