from __future__ import annotations

import unittest

from kernel.sdk import Entity, Field, Identity, SDKStore, SDKStoreError


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _seed_store() -> tuple[SDKStore, dict[str, str]]:
    sdk = SDKStore([User])
    ref = sdk.ref(User, user_id="u-1")
    ids = {
        "name_old": sdk.set(
            User.name,
            ref,
            "Alice",
            meta={
                "source": "seed",
                "version": "name-v1",
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2026-02-01T00:00:00Z",
            },
        ),
        "name_new": sdk.set(
            User.name,
            ref,
            "Alicia",
            meta={
                "source": "correction",
                "version": "name-v2",
                "valid_from": "2026-02-01T00:00:00Z",
            },
        ),
        "tag_vip": sdk.add(
            User.tag,
            ref,
            "vip",
            meta={
                "source": "seed",
                "version": "tag-v1",
                "valid_from": "2026-01-10T00:00:00Z",
                "valid_to": "2026-03-01T00:00:00Z",
            },
        ),
        "tag_missing_valid_from": sdk.add(
            User.tag,
            ref,
            "unscoped",
            meta={
                "source": "legacy",
                "version": "tag-v0",
            },
        ),
    }
    return sdk, ids


class AssertionRecordSetTemporalFilterTests(unittest.TestCase):
    def test_at_filters_current_set_by_business_validity_interval(self) -> None:
        sdk, ids = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        january = snap.field("tag").history.at("2026-01-15T00:00:00Z")
        march_boundary = snap.field("tag").history.at("2026-03-01T00:00:00Z")
        missing_valid_from = snap.field("tag").history.by_id(ids["tag_missing_valid_from"])

        self.assertEqual(january.by_id(ids["tag_vip"]).one().value, "vip")
        self.assertEqual(march_boundary.by_id(ids["tag_vip"]).all(), ())
        self.assertEqual(missing_valid_from.at("2026-01-15T00:00:00Z").all(), ())

    def test_at_rejects_non_iso8601_timestamp(self) -> None:
        sdk, _ = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        with self.assertRaises(SDKStoreError):
            snap.field("tag").history.at("not-a-time")

    def test_version_and_by_id_filter_current_set(self) -> None:
        sdk, ids = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        versioned = snap.field("name").history.version("name-v1")
        by_id = snap.field("name").history.by_id(ids["name_old"])

        self.assertEqual(versioned.one().asrt_id, ids["name_old"])
        self.assertEqual(by_id.one().value, "Alice")
        self.assertEqual(snap.field("name").history.by_id("missing").all(), ())

    def test_non_terminal_filters_preserve_type_and_chainability(self) -> None:
        sdk, ids = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        records = snap.field("tag").history
        chained = (
            records.where(source="seed")
            .at("2026-01-15T00:00:00Z")
            .version("tag-v1")
            .by_id(ids["tag_vip"])
        )

        self.assertIs(type(chained), type(records))
        self.assertEqual(chained.one().asrt_id, ids["tag_vip"])

    def test_field_assertions_at_and_version_are_active_shortcuts(self) -> None:
        sdk, ids = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        field = snap.field("name")

        self.assertEqual(
            [record.asrt_id for record in field.at("2026-02-15T00:00:00Z")],
            [record.asrt_id for record in field.active.at("2026-02-15T00:00:00Z")],
        )
        self.assertEqual(
            [record.asrt_id for record in field.version("name-v2")],
            [record.asrt_id for record in field.active.version("name-v2")],
        )
        self.assertEqual(field.active.by_id(ids["name_new"]).one().value, "Alicia")


if __name__ == "__main__":
    unittest.main()
