from __future__ import annotations

from collections import Counter
import unittest

from factgraph.sdk import Entity, Field, Identity, SDKStore
from factgraph.sdk.batch import WireBatchPlan


class Country(Entity):
    code: str = Identity()
    name: str = Field()


class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    name: str = Field()
    tag: list[str] = Field()
    lives_in: Country = Field()


PRED_USER_ID = "user:user_id"
PRED_LOCALE = "user:locale"
PRED_USER_NAME = "user:name"
PRED_USER_TAG = "user:tag"
PRED_USER_EXISTS = "User:exists"


def _claim_counts(sdk: SDKStore, e_ref: str) -> Counter:
    return Counter(c.pred_id for c in sdk.ledger.find_claims(e_ref=e_ref))


class SDKBatchApplicationDelegateTests(unittest.TestCase):
    def test_batch_preview_and_apply_delegate_simple_writes(self) -> None:
        sdk = SDKStore([Country, User])

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1", locale="zh")
            user.name.set("Alice")
            user.tag.add("vip")

            plan = tx.preview(objects=[user])
            wire = plan.export(sdk)
            self.assertEqual(wire.wire_version, "sdk_batch_plan_v1")
            self.assertNotIn("record_exists", [op.kind for op in wire.ops])

            result = plan.apply(sdk)

        self.assertEqual(result.refs_by_handle_id[user.handle_id], user.e_ref)
        self.assertEqual(
            _claim_counts(sdk, user.e_ref),
            Counter({PRED_USER_ID: 1, PRED_LOCALE: 1, PRED_USER_NAME: 1, PRED_USER_TAG: 1}),
        )
        self.assertEqual(len(sdk.ledger.find_claims(pred_id=PRED_USER_EXISTS, e_ref=user.e_ref)), 0)
        snap = sdk.entities.get(User, user_id="u-1", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")
        self.assertEqual(snap.tag, ("vip",))

    def test_batch_commit_delegates_dependency_handle_reference(self) -> None:
        sdk = SDKStore([Country, User])

        with sdk.batch() as tx:
            country = tx.entity(Country, code="DE")
            country.name.set("Germany")

            user = tx.entity(User, user_id="u-2", locale="zh")
            user.lives_in.set(country)

            tx.commit(objects=[user])

        user_snap = sdk.entities.get(User, user_id="u-2", locale="zh")
        country_snap = sdk.entities.get(Country, code="DE")
        self.assertIsNotNone(user_snap)
        self.assertIsNotNone(country_snap)
        assert user_snap is not None
        assert country_snap is not None
        self.assertEqual(user_snap.lives_in, country.e_ref)
        self.assertEqual(country_snap.name, "Germany")

    def test_batch_preview_falls_back_for_raw_entity_ref_values(self) -> None:
        sdk = SDKStore([Country, User])
        country_ref = sdk.entities.ref(Country, code="DE")
        sdk.fields.set(Country.name, country_ref, "Germany")

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-3", locale="zh")
            user.lives_in.set(country_ref)

            plan = tx.preview(objects=[user])
            result = plan.apply(sdk)

        self.assertEqual(result.refs_by_handle_id[user.handle_id], user.e_ref)
        snap = sdk.entities.get(User, user_id="u-3", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.lives_in, country_ref)

    def test_wire_record_exists_remains_legacy_compatibility_surface(self) -> None:
        sdk = SDKStore([Country, User])
        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-wire", locale="zh")
            user.name.set("Wire")
            wire_payload = tx.preview(objects=[user]).export(sdk).to_dict()

        wire_payload["ops"].append(
            {
                "kind": "record_exists",
                "handle_id": user.handle_id,
                "entity_type": "User",
                "pred_id": PRED_USER_EXISTS,
                "meta": {"source": "legacy-wire"},
                "path": "$.ops[legacy_record_exists]",
            }
        )
        result = WireBatchPlan.from_dict(wire_payload).apply(sdk)

        self.assertEqual(result.refs_by_handle_id[user.handle_id], user.e_ref)
        self.assertEqual(len(sdk.ledger.find_claims(pred_id=PRED_USER_EXISTS, e_ref=user.e_ref)), 1)
        self.assertTrue(sdk.entities.exists(User, user_id="u-wire", locale="zh"))


if __name__ == "__main__":
    unittest.main()
