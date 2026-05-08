"""Unit tests for the shared SDK shell input validators.

Exercises ``kernel.sdk.shells._validation.validate_derivation`` and
``validate_binding`` directly: behavior parity vs the inlined G1 validators
they replaced (Q1 follow-up to Round 4 audit), the path-parameter contract
that lets multiple SDK shell methods (Check, Diagnose, Why-not, future G2
shells, etc.) share validators without duplicating logic, and the post-G2
Phase 0 hygiene location under ``kernel/sdk/shells/``.
"""

from __future__ import annotations

import unittest

from kernel.sdk import Derivation, Entity, Field, Identity, SDKStoreError, vars
from kernel.sdk.shells._validation import validate_binding, validate_derivation


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")


def _age_derivation() -> Derivation:
    with vars("p", "age") as (p, age):
        return Derivation(
            id="sdk.validation.age",
            version="v1",
            where=[Person(p), p.age == age],
            head=Person.age(value=age),
        )


class ValidateDerivationTests(unittest.TestCase):
    def test_accepts_sdk_derivation(self) -> None:
        validate_derivation(_age_derivation(), path="$.check.derivation")

    def test_rejects_non_derivation_with_provided_path(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_derivation({"not": "derivation"}, path="$.diagnose.derivation")
        self.assertEqual(ctx.exception.path, "$.diagnose.derivation")
        self.assertIn("derivation must be SDK Derivation", str(ctx.exception))

    def test_rejects_none(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_derivation(None, path="$.check.derivation")
        self.assertEqual(ctx.exception.path, "$.check.derivation")

    def test_path_is_forwarded_verbatim(self) -> None:
        custom_path = "$.future_g4.why_not.derivation"
        with self.assertRaises(SDKStoreError) as ctx:
            validate_derivation("not-a-derivation", path=custom_path)
        self.assertEqual(ctx.exception.path, custom_path)


class ValidateBindingTests(unittest.TestCase):
    def test_accepts_dollar_prefixed_string_keys_and_returns_dict_copy(self) -> None:
        binding = {"$p": "alice", "$age": 30}
        out = validate_binding(binding, path="$.check.binding")
        self.assertEqual(out, {"$p": "alice", "$age": 30})
        self.assertIsInstance(out, dict)
        self.assertIsNot(out, binding)

    def test_rejects_non_mapping(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding([("$p", "alice")], path="$.check.binding")
        self.assertEqual(ctx.exception.path, "$.check.binding")
        self.assertIn("Mapping", str(ctx.exception))

    def test_rejects_non_string_key(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding({1: "x"}, path="$.diagnose.binding")
        self.assertEqual(ctx.exception.path, "$.diagnose.binding")

    def test_rejects_unprefixed_key(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding({"p": "alice"}, path="$.check.binding")
        self.assertEqual(ctx.exception.path, "$.check.binding")

    def test_rejects_lone_dollar_key(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding({"$": "alice"}, path="$.check.binding")
        self.assertIn("$-prefixed", str(ctx.exception))

    def test_accepts_empty_mapping(self) -> None:
        out = validate_binding({}, path="$.check.binding")
        self.assertEqual(out, {})

    def test_path_is_forwarded_verbatim(self) -> None:
        custom_path = "$.future_g4.why_not.binding"
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding("not-a-mapping", path=custom_path)
        self.assertEqual(ctx.exception.path, custom_path)


if __name__ == "__main__":
    unittest.main()
