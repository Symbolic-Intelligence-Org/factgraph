from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity, SDKStore


class Country(Entity):
    code: str = Identity()
    name: str = Field()


class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    lives_in: Country = Field()
    tag: list[str] = Field()


class SDKFacadeApplicationDelegateTests(unittest.TestCase):
    def test_sdk_get_preserves_sdk_snapshot_shape(self) -> None:
        sdk = SDKStore([Country, User])
        country_ref = sdk.entities.ref(Country, code="DE")
        user_ref = sdk.entities.ref(User, user_id="u1", locale="zh")

        sdk.fields.set(Country.name, country_ref, "Germany")
        sdk.fields.set(User.lives_in, user_ref, country_ref)
        tag_asrt = sdk.fields.add(User.tag, user_ref, "admin")

        snap = sdk.entities.get(User, user_id="u1", locale="zh")

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
        user_a = sdk.entities.ref(User, user_id="u-a", locale="zh")
        user_b = sdk.entities.ref(User, user_id="u-b", locale="zh")

        sdk.fields.add(User.tag, user_a, "vip")
        sdk.fields.add(User.tag, user_b, "viewer")

        rows = sdk.entities.where(User, tag="vip")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ref, user_a)
        self.assertEqual(rows[0].tag, ("vip",))
        self.assertFalse(rows[0].identity_available)
        self.assertEqual(rows[0].identity, {})

    def test_sdk_find_identity_filters_return_identity_enabled_snapshot(self) -> None:
        sdk = SDKStore([Country, User])
        user_ref = sdk.entities.ref(User, user_id="u-c", locale="zh")
        sdk.fields.add(User.tag, user_ref, "vip")

        rows = sdk.entities.where(User, user_id="u-c", locale="zh")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ref, user_ref)
        self.assertTrue(rows[0].identity_available)
        self.assertEqual(rows[0].identity, {"user_id": "u-c", "locale": "zh"})


if __name__ == "__main__":
    unittest.main()
