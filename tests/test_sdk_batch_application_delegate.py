from __future__ import annotations

from collections import Counter
import unittest
from uuid import UUID

from factgraph.sdk import (
    Database,
    Entity,
    FactGraph,
    Field,
    Identity,
    SDKStore,
    SDKStoreError,
    compile_schema_from_classes,
)
from factgraph.sdk.batch import BatchPlan, WireBatchPlan


class Country(Entity):
    code: str = Identity()
    name: str = Field()


class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    name: str = Field()
    tag: list[str] = Field()
    lives_in: Country = Field()


class BinaryDoc(Entity):
    doc_id: str = Identity()
    payload: bytes = Field()


class UUIDDoc(Entity):
    doc_id: str = Identity()
    external_id: UUID = Field()


PRED_USER_ID = "user:user_id"
PRED_LOCALE = "user:locale"
PRED_USER_NAME = "user:name"
PRED_USER_TAG = "user:tag"
PRED_USER_EXISTS = "User:exists"


def _claim_counts(sdk: SDKStore, e_ref: str) -> Counter:
    return Counter(c.pred_id for c in sdk.ledger.find_claims(e_ref=e_ref))


class SDKBatchApplicationDelegateTests(unittest.TestCase):
    def test_attached_batch_fails_closed_when_value_is_not_application_representable(self) -> None:
        db = Database.create(schema_ir=compile_schema_from_classes([BinaryDoc]))
        sdk = FactGraph.attach(db, schema_classes=[BinaryDoc])
        before = db.head()

        with sdk.batch() as tx:
            doc = tx.entity(BinaryDoc, doc_id="doc-1")
            doc.payload.set(b"payload")
            plan = tx.preview(objects=[doc])
            self.assertFalse(plan._application_handle_order)
            with self.assertRaises(SDKStoreError) as caught:
                plan.apply(sdk)
            self.assertIn("BinaryDoc#1.payload", str(caught.exception))
            self.assertIn("cannot be represented", str(caught.exception))
            self.assertIn("bytes", str(caught.exception))

        self.assertEqual(db.head(), before)
        self.assertEqual(sdk.ledger.claims, [])

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

    def test_batch_preview_delegates_managed_raw_entity_ref_values(self) -> None:
        delegated_sdk = SDKStore([Country, User])
        legacy_sdk = SDKStore([Country, User])
        country_ref = delegated_sdk.entities.ref(Country, code="DE")
        self.assertEqual(country_ref, legacy_sdk.entities.ref(Country, code="DE"))
        delegated_sdk.fields.set(Country.name, country_ref, "Germany")
        legacy_sdk.fields.set(Country.name, country_ref, "Germany")

        with delegated_sdk.batch() as tx:
            user = tx.entity(User, user_id="u-3", locale="zh")
            user.lives_in.set(country_ref)

            plan = tx.preview(objects=[user])
            self.assertTrue(plan._application_handle_order)
            delegated_result = plan.apply(delegated_sdk)

        legacy_plan = BatchPlan(ops=plan.ops, warnings=plan.warnings)
        legacy_result = legacy_plan.apply(legacy_sdk)

        self.assertEqual(delegated_result.refs_by_handle_id, legacy_result.refs_by_handle_id)
        delegated_rows = sorted(
            (claim.pred_id, claim.e_ref, tuple(claim.rest_terms))
            for claim in delegated_sdk.ledger.claims
        )
        legacy_rows = sorted(
            (claim.pred_id, claim.e_ref, tuple(claim.rest_terms))
            for claim in legacy_sdk.ledger.claims
        )
        self.assertEqual(delegated_rows, legacy_rows)
        snap = delegated_sdk.entities.get(User, user_id="u-3", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.lives_in, country_ref)

    def test_empty_attached_batch_forms_are_noops(self) -> None:
        db = Database.create(schema_ir=compile_schema_from_classes([User]))
        sdk = FactGraph.attach(db, schema_classes=[User])
        before = db.head()

        direct = BatchPlan(ops=[]).apply(sdk)
        wire = BatchPlan(ops=[]).export(sdk).apply(sdk)
        with sdk.batch() as tx:
            committed = tx.commit()

        self.assertEqual(direct.refs_by_handle_id, {})
        self.assertEqual(direct.assertion_ids, [])
        self.assertEqual(wire, direct)
        self.assertEqual(committed.apply_result, direct)
        self.assertEqual(db.head(), before)

    def test_wire_uuid_normalization_is_portable_across_runtimes(self) -> None:
        uppercase = "550E8400-E29B-41D4-A716-446655440000"
        lowercase = uppercase.lower()
        planner = SDKStore([UUIDDoc])
        with planner.batch() as tx:
            doc = tx.entity(UUIDDoc, doc_id="uuid-1")
            doc.external_id.set(uppercase)
            payload = tx.preview(objects=[doc]).export(planner).to_dict()

        workspace = SDKStore([UUIDDoc])
        database = Database.create(schema_ir=compile_schema_from_classes([UUIDDoc]))
        attached = FactGraph.attach(database, schema_classes=[UUIDDoc])
        wire = WireBatchPlan.from_dict(payload)
        workspace_result = wire.apply(workspace)
        attached_result = wire.apply(attached)

        workspace_ref = workspace_result.refs_by_handle_id[doc.handle_id]
        attached_ref = attached_result.refs_by_handle_id[doc.handle_id]
        self.assertEqual(workspace_ref, attached_ref)
        for runtime, e_ref in ((workspace, workspace_ref), (attached, attached_ref)):
            claims = [
                claim
                for claim in runtime.ledger.find_claims(e_ref=e_ref)
                if claim.pred_id == "uuid_doc:external_id"
            ]
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0].rest_terms, [("uuid", lowercase)])

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
