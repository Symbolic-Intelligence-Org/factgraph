from __future__ import annotations

from collections import Counter
import unittest
from uuid import UUID, uuid4

from factgraph.sdk import Entity, Field, Identity, SDKStore, SDKStoreError


class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    name: str = Field()


class AccountUser(Entity):
    tenant_id: str = Identity()
    user_id: str = Identity()
    locale: str = Identity()
    name: str = Field()


class Session(Entity):
    sid: str = Identity()
    locale: str = Identity()
    status: str = Field()


PRED_USER_ID = "user:user_id"
PRED_USER_LOCALE = "user:locale"
PRED_USER_NAME = "user:name"
PRED_USER_EXISTS = "User:exists"
PRED_ACCOUNT_TENANT = "account_user:tenant_id"
PRED_ACCOUNT_USER = "account_user:user_id"
PRED_ACCOUNT_LOCALE = "account_user:locale"
PRED_ACCOUNT_NAME = "account_user:name"
PRED_ACCOUNT_EXISTS = "AccountUser:exists"
PRED_SESSION_ID = "session:sid"
PRED_SESSION_LOCALE = "session:locale"
PRED_SESSION_STATUS = "session:status"
PRED_SESSION_EXISTS = "Session:exists"


def _claim_counts(sdk: SDKStore, e_ref: str) -> Counter:
    return Counter(c.pred_id for c in sdk.ledger.find_claims(e_ref=e_ref))


class SDKBatchPrimaryIdentityTests(unittest.TestCase):
    def test_complete_identity_bundle_commits_without_exists_claim(self) -> None:
        sdk = SDKStore([User])

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1", locale="en")
            user.name.set("Alice")
            tx.commit(objects=[user])

        snap = sdk.entities.get(User, user_id="u-1", locale="en")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")
        self.assertEqual(
            _claim_counts(sdk, user.e_ref),
            Counter({PRED_USER_ID: 1, PRED_USER_LOCALE: 1, PRED_USER_NAME: 1}),
        )
        self.assertEqual(len(sdk.ledger.find_claims(pred_id=PRED_USER_EXISTS, e_ref=user.e_ref)), 0)

    def test_entity_creation_rejects_incomplete_identity_bundle(self) -> None:
        sdk = SDKStore([User])

        with sdk.batch() as tx:
            with self.assertRaises(SDKStoreError) as ctx:
                tx.entity(User, user_id="u-1")

        msg = str(ctx.exception)
        self.assertIn("identity is incomplete", msg)
        self.assertIn("locale", msg)

    def test_multi_identity_requires_complete_bundle_upfront(self) -> None:
        sdk = SDKStore([AccountUser])

        with sdk.batch() as tx:
            with self.assertRaises(SDKStoreError) as ctx:
                tx.entity(AccountUser, tenant_id="t-1", user_id="u-1")

        msg = str(ctx.exception)
        self.assertIn("identity is incomplete", msg)
        self.assertIn("locale", msg)

    def test_multi_identity_complete_bundle_commit(self) -> None:
        sdk = SDKStore([AccountUser])

        with sdk.batch() as tx:
            user = tx.entity(AccountUser, tenant_id="t-1", user_id="u-1", locale="en")
            user.name.set("Alice")
            tx.commit(objects=[user])

        snap = sdk.entities.get(AccountUser, tenant_id="t-1", user_id="u-1", locale="en")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")
        self.assertEqual(
            _claim_counts(sdk, user.e_ref),
            Counter(
                {
                    PRED_ACCOUNT_TENANT: 1,
                    PRED_ACCOUNT_USER: 1,
                    PRED_ACCOUNT_LOCALE: 1,
                    PRED_ACCOUNT_NAME: 1,
                }
            ),
        )
        self.assertEqual(len(sdk.ledger.find_claims(pred_id=PRED_ACCOUNT_EXISTS, e_ref=user.e_ref)), 0)

    def test_uuid_identity_value_must_be_supplied_explicitly(self) -> None:
        sdk = SDKStore([Session])

        with sdk.batch() as tx:
            with self.assertRaises(SDKStoreError) as ctx:
                tx.entity(Session, locale="en")

        self.assertIn("sid", str(ctx.exception))

    def test_uuid_identity_value_commits_when_supplied(self) -> None:
        sdk = SDKStore([Session])
        sid = str(uuid4())
        UUID(sid)

        with sdk.batch() as tx:
            session = tx.entity(Session, sid=sid, locale="en")
            session.status.set("open")
            tx.commit(objects=[session])

        snap = sdk.entities.get(Session, sid=sid, locale="en")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.status, "open")
        self.assertEqual(
            _claim_counts(sdk, session.e_ref),
            Counter({PRED_SESSION_ID: 1, PRED_SESSION_LOCALE: 1, PRED_SESSION_STATUS: 1}),
        )
        self.assertEqual(len(sdk.ledger.find_claims(pred_id=PRED_SESSION_EXISTS, e_ref=session.e_ref)), 0)

    def test_bind_rejects_conflicting_identity_after_resolution(self) -> None:
        sdk = SDKStore([User])

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1", locale="en")
            with self.assertRaises(SDKStoreError) as ctx:
                user.bind(locale="zh")

        msg = str(ctx.exception)
        self.assertIn("identity field 'locale' is immutable once bound", msg)

    def test_write_side_rejects_incomplete_identity_bundle_at_entity_creation(self) -> None:
        sdk = SDKStore([User])

        with sdk.batch() as tx:
            with self.assertRaises(SDKStoreError) as ctx:
                tx.entity(User, user_id="u-1")

        msg = str(ctx.exception)
        self.assertIn("identity is incomplete", msg)
        self.assertIn("locale", msg)

    def test_flat_assertion_id_retract_is_unaffected(self) -> None:
        sdk = SDKStore([User])
        e_ref = sdk.entities.ref(User, user_id="u-1", locale="en")
        asrt_id = sdk.fields.set(User.name, e_ref, "Alice")

        revoked = sdk.assertions.retract(asrt_id)

        self.assertIsInstance(revoked, str)
        snap = sdk.entities.get(User, user_id="u-1", locale="en")
        self.assertIsNone(snap.name if snap is not None else None)


if __name__ == "__main__":
    unittest.main()
