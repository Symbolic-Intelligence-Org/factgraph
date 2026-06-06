from __future__ import annotations

import unittest

import factgraph.sdk as sdk_module
from factgraph.application import execute_read_request
from factgraph.application.protocol import EntityReadRequest
from factgraph.sdk import Entity, Field, Identity, SDKSchemaError, SDKStore


class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    name: str = Field()
    tag: list[str] = Field()


def _seed_store() -> SDKStore:
    sdk = SDKStore([User])
    user_en = sdk.entities.ref(User, user_id="u-1", locale="en")
    user_zh = sdk.entities.ref(User, user_id="u-1", locale="zh")
    user_other = sdk.entities.ref(User, user_id="u-2", locale="en")

    sdk.fields.set(User.name, user_en, "Alice")
    sdk.fields.add(User.tag, user_en, "vip")
    sdk.fields.add(User.tag, user_en, "editor")

    sdk.fields.set(User.name, user_zh, "Alice")
    sdk.fields.add(User.tag, user_zh, "viewer")

    sdk.fields.set(User.name, user_other, "Bob")
    sdk.fields.add(User.tag, user_other, "vip")
    return sdk


class SDKFindPartialIdentityTests(unittest.TestCase):
    def test_partial_identity_filter_returns_all_matching_full_coordinates(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1")

        self.assertEqual({row.identity["locale"] for row in rows}, {"en", "zh"})
        self.assertEqual({row.identity["user_id"] for row in rows}, {"u-1"})
        self.assertTrue(all(row.identity_available for row in rows))

    def test_partial_identity_filter_exposes_full_identity_for_each_snapshot(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1")

        self.assertEqual(
            {tuple(sorted(row.identity.items())) for row in rows},
            {
                (("locale", "en"), ("user_id", "u-1")),
                (("locale", "zh"), ("user_id", "u-1")),
            },
        )
        self.assertTrue(all(row.identity_available for row in rows))

    def test_full_identity_filter_keeps_exact_coordinate_behavior(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1", locale="en")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].identity, {"user_id": "u-1", "locale": "en"})
        self.assertEqual(rows[0].name, "Alice")
        self.assertEqual(set(rows[0].tag), {"vip", "editor"})

    def test_combined_identity_and_field_filters_use_and_semantics(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1", tag="vip")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].identity, {"user_id": "u-1", "locale": "en"})
        self.assertEqual(set(rows[0].tag), {"vip", "editor"})

    def test_partial_identity_no_match_returns_empty_list(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="missing")

        self.assertEqual(rows, [])

    def test_limit_applies_after_partial_identity_filters_match(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1", limit=1)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].identity["user_id"], "u-1")
        self.assertIn(rows[0].identity["locale"], {"en", "zh"})

    def test_zero_filter_find_behavior_is_unchanged(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User)

        self.assertEqual(len(rows), 3)

    def test_unknown_filter_names_remain_schema_errors(self) -> None:
        sdk = _seed_store()

        with self.assertRaises(SDKSchemaError) as ctx:
            sdk.entities.where(User, unknown="x")

        self.assertIn("unknown", str(ctx.exception))
        self.assertIn("User", str(ctx.exception))

    def test_get_still_requires_complete_identity_coordinate(self) -> None:
        sdk = _seed_store()

        with self.assertRaises(SDKSchemaError) as ctx:
            sdk.entities.get(User, user_id="u-1")

        self.assertIn("locale", str(ctx.exception))

    def test_application_protocol_still_rejects_identity_field_filters(self) -> None:
        sdk = _seed_store()

        response = execute_read_request(
            EntityReadRequest(
                mode="find",
                entity_type="User",
                field_filters={"user_id": "u-1"},
            ),
            store=sdk.store,
            index=sdk._application_schema_index,
        )

        self.assertEqual(response.items, ())
        self.assertEqual(len(response.errors), 1)
        self.assertEqual(response.errors[0].code, "IDENTITY_FILTER_NOT_SUPPORTED")

    def test_no_new_public_sdk_names_or_read_helpers_are_added(self) -> None:
        sdk = _seed_store()

        self.assertEqual(len(sdk_module.__all__), 63)
        self.assertNotIn("ReadPolicy", sdk_module.__all__)
        self.assertIn("SemanticsProfile", sdk_module.__all__)
        self.assertIn("ProbLogConfig", sdk_module.__all__)
        self.assertIn("PyReasonConfig", sdk_module.__all__)
        self.assertIn("ResultFingerprint", sdk_module.__all__)
        self.assertNotIn("EntityDomainSet", sdk_module.__all__)
        self.assertFalse(hasattr(sdk, "read"))


if __name__ == "__main__":
    unittest.main()
