from __future__ import annotations

import unittest

from kernel.core.evidence.write_protocol import WriteProtocolError
from kernel.sdk import Entity, Field, Identity, SDKStore
from kernel.sdk.errors import CardinalityError, SDKStoreError


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="zh")
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")
    home: Country = Field(cardinality="single")


def _build_sdk() -> SDKStore:
    return SDKStore([Country, User])


class SDKSetAddApplicationDelegateTests(unittest.TestCase):
    def test_set_writes_field_and_materializes_identity_and_exists(self) -> None:
        sdk = _build_sdk()
        alice = sdk.ref(User, user_id="u1", locale="zh")
        asrt = sdk.set(User.name, alice, "Alice")

        self.assertIsInstance(asrt, str)
        self.assertTrue(asrt)

        snap = sdk.get(User, user_id="u1", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")

    def test_add_writes_multi_field(self) -> None:
        sdk = _build_sdk()
        alice = sdk.ref(User, user_id="u1", locale="zh")
        sdk.add(User.tag, alice, "admin")
        sdk.add(User.tag, alice, "vip")

        snap = sdk.get(User, user_id="u1", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(set(snap.tag), {"admin", "vip"})

    def test_set_returns_field_mutation_assertion_id_only(self) -> None:
        sdk = _build_sdk()
        alice = sdk.ref(User, user_id="u1", locale="zh")
        asrt_a = sdk.set(User.name, alice, "Alice")
        asrt_b = sdk.set(User.name, alice, "Alicia")
        self.assertNotEqual(asrt_a, asrt_b)

    def test_set_with_entity_ref_value_resolves_dependency(self) -> None:
        sdk = _build_sdk()
        de = sdk.ref(Country, code="DE")
        sdk.set(Country.name, de, "Germany")
        alice = sdk.ref(User, user_id="u1", locale="zh")
        sdk.set(User.home, alice, de)

        snap = sdk.get(User, user_id="u1", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.home, de)

    def test_unmanaged_target_e_ref_raises_actionable_error(self) -> None:
        sdk = _build_sdk()
        with self.assertRaises(SDKStoreError) as ctx:
            sdk.set(User.name, "idref_v1:User:foreign-token", "Alice")
        self.assertEqual(ctx.exception.code, "UNRESOLVABLE_E_REF")
        self.assertIn("not managed", str(ctx.exception))

    def test_unmanaged_value_e_ref_raises_actionable_error(self) -> None:
        sdk = _build_sdk()
        alice = sdk.ref(User, user_id="u1", locale="zh")
        with self.assertRaises(SDKStoreError) as ctx:
            sdk.set(User.home, alice, "idref_v1:Country:foreign-token")
        self.assertEqual(ctx.exception.code, "UNRESOLVABLE_E_REF")

    def test_set_on_multi_field_raises_cardinality_error(self) -> None:
        sdk = _build_sdk()
        alice = sdk.ref(User, user_id="u1", locale="zh")
        with self.assertRaises(CardinalityError) as ctx:
            sdk.set(User.tag, alice, "admin")
        self.assertEqual(ctx.exception.code, "FIELD_CARDINALITY_MISMATCH")
        self.assertEqual(ctx.exception.operation, "set")
        self.assertEqual(ctx.exception.actual_cardinality, "multi")

    def test_add_on_single_field_raises_cardinality_error(self) -> None:
        sdk = _build_sdk()
        de = sdk.ref(Country, code="DE")
        sdk.set(Country.name, de, "Germany")
        alice = sdk.ref(User, user_id="u1", locale="zh")
        with self.assertRaises(CardinalityError) as ctx:
            sdk.add(User.home, alice, de)
        self.assertEqual(ctx.exception.code, "FIELD_CARDINALITY_MISMATCH")
        self.assertEqual(ctx.exception.operation, "add")
        self.assertEqual(ctx.exception.actual_cardinality, "single")

    def test_retract_unknown_assertion_remaps_core_write_error(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.retract("asrt_missing")

        self.assertEqual(ctx.exception.code, "ASSERTION_NOT_FOUND")
        self.assertIn("unknown revoked_asrt_id", str(ctx.exception))
        self.assertIsInstance(ctx.exception.__cause__, WriteProtocolError)

    def test_retract_invalid_assertion_id_remaps_core_write_error(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.retract("")

        self.assertIsNone(ctx.exception.code)
        self.assertIn("revoked_asrt_id must be non-empty string", str(ctx.exception))
        self.assertIsInstance(ctx.exception.__cause__, WriteProtocolError)


if __name__ == "__main__":
    unittest.main()
