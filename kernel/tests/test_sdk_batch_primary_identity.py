from __future__ import annotations

import unittest
from uuid import UUID

from kernel.sdk import Entity, Field, Identity, SDKSchemaError, SDKStore, SDKStoreError


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")


class AccountUser(Entity):
    tenant_id: str = Identity(primary_key=True)
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")


class DefaultTenantUser(Entity):
    tenant_id: str = Identity(primary_key=True, default="default-tenant")
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")


class Session(Entity):
    sid: UUID = Identity(primary_key=True, default_factory="uuid4")
    locale: str = Identity()
    status: str = Field(cardinality="single")


class SDKBatchPrimaryIdentityTests(unittest.TestCase):
    def test_single_primary_allows_primary_first_then_non_primary_bind(self) -> None:
        sdk = SDKStore([User])

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1")
            returned = user.bind(locale="en")
            user.name.set("Alice")
            tx.commit(objects=[user])

        self.assertIs(returned, user)
        snap = sdk.get(User, user_id="u-1", locale="en")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")

    def test_single_primary_rejects_non_primary_only_handle_creation(self) -> None:
        sdk = SDKStore([User])

        with sdk.batch() as tx:
            with self.assertRaises(SDKStoreError) as ctx:
                tx.entity(User, locale="en")

        msg = str(ctx.exception)
        self.assertIn("tx.entity(...)", msg)
        self.assertIn("primary", msg)
        self.assertIn("user_id", msg)

    def test_multi_primary_requires_all_primary_fields_upfront(self) -> None:
        sdk = SDKStore([AccountUser])

        with sdk.batch() as tx:
            with self.assertRaises(SDKStoreError) as ctx:
                tx.entity(AccountUser, tenant_id="t-1")

        msg = str(ctx.exception)
        self.assertIn("tx.entity(...)", msg)
        self.assertIn("primary", msg)
        self.assertIn("user_id", msg)

    def test_multi_primary_allows_all_primary_then_non_primary_bind(self) -> None:
        sdk = SDKStore([AccountUser])

        with sdk.batch() as tx:
            user = tx.entity(AccountUser, tenant_id="t-1", user_id="u-1")
            user.bind(locale="en")
            user.name.set("Alice")
            tx.commit(objects=[user])

        snap = sdk.get(AccountUser, tenant_id="t-1", user_id="u-1", locale="en")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")

    def test_literal_primary_default_counts_as_present_at_entity_creation(self) -> None:
        sdk = SDKStore([DefaultTenantUser])

        with sdk.batch() as tx:
            user = tx.entity(DefaultTenantUser, user_id="u-1")
            self.assertEqual(user.identity_values["tenant_id"], "default-tenant")
            user.bind(locale="en")
            user.name.set("Alice")
            tx.commit(objects=[user])

        snap = sdk.get(DefaultTenantUser, tenant_id="default-tenant", user_id="u-1", locale="en")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")

    def test_uuid4_primary_default_factory_counts_as_present_at_entity_creation(self) -> None:
        sdk = SDKStore([Session])

        with sdk.batch() as tx:
            session = tx.entity(Session, locale="en")
            sid = session.identity_values.get("sid")
            self.assertIsInstance(sid, str)
            UUID(str(sid))
            session.status.set("open")
            tx.commit(objects=[session])

        snap = sdk.get(Session, sid=sid, locale="en")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.status, "open")

    def test_read_still_rejects_omitted_uuid4_primary_identity(self) -> None:
        sdk = SDKStore([Session])

        with self.assertRaises(SDKSchemaError) as ctx:
            sdk.get(Session, locale="en")

        self.assertIn("uuid4", str(ctx.exception))
        self.assertIn("sid", str(ctx.exception))

    def test_bind_rejects_primary_identity_even_when_value_matches(self) -> None:
        sdk = SDKStore([User])

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1")
            with self.assertRaises(SDKStoreError) as ctx:
                user.bind(user_id="u-1")

        msg = str(ctx.exception)
        self.assertIn("bind", msg)
        self.assertIn("primary", msg)
        self.assertIn("user_id", msg)

    def test_write_side_rejects_incomplete_non_primary_coordinate(self) -> None:
        sdk = SDKStore([User])

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1")
            with self.assertRaises(SDKStoreError) as ctx:
                user.name.set("Alice")

        msg = str(ctx.exception)
        self.assertIn("identity is incomplete", msg)
        self.assertIn("locale", msg)
        self.assertIn("handle.bind", msg)

    def test_flat_assertion_id_retract_is_unaffected(self) -> None:
        sdk = SDKStore([User])
        e_ref = sdk.ref(User, user_id="u-1", locale="en")
        asrt_id = sdk.set(User.name, e_ref, "Alice")

        revoked = sdk.retract(asrt_id)

        self.assertIsInstance(revoked, str)
        snap = sdk.get(User, user_id="u-1", locale="en")
        self.assertIsNone(snap.name if snap is not None else None)


if __name__ == "__main__":
    unittest.main()
