from __future__ import annotations

import unittest

from kernel.sdk import Entity, Field, Identity, SDKStore


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="zh")
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")
    lives_in: Country = Field(cardinality="single")


class SDKBatchApplicationDelegateTests(unittest.TestCase):
    def test_batch_preview_and_apply_delegate_simple_writes(self) -> None:
        sdk = SDKStore([Country, User])

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1")
            user.name.set("Alice")
            user.tag.add("vip")

            plan = tx.preview(objects=[user])
            self.assertEqual(plan._application_handle_order, (user.handle_id,))
            self.assertIn(user.handle_id, plan._application_plans_by_handle_id)

            wire = plan.export(sdk)
            self.assertEqual(wire.wire_version, "sdk_batch_plan_v1")

            result = plan.apply(sdk)

        self.assertEqual(result.refs_by_handle_id[user.handle_id], user.e_ref)
        snap = sdk.get(User, user_id="u-1", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")
        self.assertEqual(snap.tag, ("vip",))

    def test_batch_commit_delegates_dependency_handle_reference(self) -> None:
        sdk = SDKStore([Country, User])

        with sdk.batch() as tx:
            country = tx.entity(Country, code="DE")
            country.name.set("Germany")

            user = tx.entity(User, user_id="u-2")
            user.lives_in.set(country)

            commit = tx.commit(objects=[user])

        self.assertEqual(commit.plan._application_handle_order, (country.handle_id, user.handle_id))
        user_plan = commit.plan._application_plans_by_handle_id[user.handle_id]
        self.assertTrue(all(op.target.entity_type == "User" for op in user_plan.planned_ops))

        user_snap = sdk.get(User, user_id="u-2", locale="zh")
        country_snap = sdk.get(Country, code="DE")
        self.assertIsNotNone(user_snap)
        self.assertIsNotNone(country_snap)
        assert user_snap is not None
        assert country_snap is not None
        self.assertEqual(user_snap.lives_in, country.e_ref)
        self.assertEqual(country_snap.name, "Germany")

    def test_batch_preview_falls_back_for_raw_entity_ref_values(self) -> None:
        sdk = SDKStore([Country, User])
        country_ref = sdk.ref(Country, code="DE")
        sdk.set(Country.name, country_ref, "Germany")

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-3")
            user.lives_in.set(country_ref)

            plan = tx.preview(objects=[user])
            self.assertEqual(plan._application_handle_order, ())

            result = plan.apply(sdk)

        self.assertEqual(result.refs_by_handle_id[user.handle_id], user.e_ref)
        snap = sdk.get(User, user_id="u-3", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.lives_in, country_ref)


if __name__ == "__main__":
    unittest.main()
