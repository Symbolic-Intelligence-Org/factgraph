from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity, SDKStore


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="zh")
    lives_in: Country = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


class SDKFacadeApplicationDelegateTests(unittest.TestCase):
    def test_sdk_get_preserves_sdk_snapshot_shape(self) -> None:
        sdk = SDKStore([Country, User])
        country_ref = sdk.ref(Country, code="DE")
        user_ref = sdk.ref(User, user_id="u1", locale="zh")

        sdk.set(Country.name, country_ref, "Germany")
        sdk.set(User.lives_in, user_ref, country_ref)
        tag_asrt = sdk.add(User.tag, user_ref, "admin")

        snap = sdk.get(User, user_id="u1", locale="zh")

        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.ref, user_ref)
        self.assertEqual(snap.lives_in, country_ref)
        self.assertEqual(snap.tag, ("admin",))
        self.assertTrue(snap.identity_available)
        self.assertEqual(snap.identity, {"user_id": "u1", "locale": "zh"})
        self.assertEqual([row.asrt_id for row in snap.assertions.tag.active], [tag_asrt])

    def test_sdk_find_preserves_filtering_and_identity_visibility(self) -> None:
        sdk = SDKStore([Country, User])
        user_a = sdk.ref(User, user_id="u-a", locale="zh")
        user_b = sdk.ref(User, user_id="u-b", locale="zh")

        sdk.add(User.tag, user_a, "vip")
        sdk.add(User.tag, user_b, "viewer")

        rows = sdk.find(User, tag="vip")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ref, user_a)
        self.assertEqual(rows[0].tag, ("vip",))
        self.assertFalse(rows[0].identity_available)
        self.assertEqual(rows[0].identity, {})

    def test_sdk_find_identity_filters_return_identity_enabled_snapshot(self) -> None:
        sdk = SDKStore([Country, User])
        user_ref = sdk.ref(User, user_id="u-c", locale="zh")
        sdk.add(User.tag, user_ref, "vip")

        rows = sdk.find(User, user_id="u-c", locale="zh")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ref, user_ref)
        self.assertTrue(rows[0].identity_available)
        self.assertEqual(rows[0].identity, {"user_id": "u-c", "locale": "zh"})


if __name__ == "__main__":
    unittest.main()
