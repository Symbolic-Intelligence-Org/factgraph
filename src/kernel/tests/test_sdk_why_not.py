"""SDKStore.why_not contract tests.

Phase 0 of G4 (per blueprint
``docs/blueprints/active/2026-05-08_l-direction-g4-why-not-frontier.md`` §8)
ships skeleton tests verifying the delegate hook is in place. Phase 1
fills the full §5.1-§5.6 contract coverage, and the Q1 Sibling
discipline tests (runtime + static) are added alongside the real
``sdk_why_not(...)`` body.
"""

from __future__ import annotations

import unittest

from kernel.sdk import Entity, Field, Identity, SDKStore
from kernel.sdk.why_not import sdk_why_not


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")


class SDKWhyNotPhase0SkeletonTests(unittest.TestCase):
    """Phase 0 placeholder tests — Phase 1 expands to full §5.1-§5.6 coverage."""

    def test_sdk_store_exposes_why_not_method(self) -> None:
        sdk = SDKStore([Person])
        self.assertTrue(callable(getattr(sdk, "why_not", None)))

    def test_sdk_store_why_not_delegates_to_sdk_why_not_module(self) -> None:
        sdk = SDKStore([Person])
        with self.assertRaises(NotImplementedError):
            sdk.why_not(None, [])

    def test_sdk_why_not_module_function_is_phase0_placeholder(self) -> None:
        with self.assertRaises(NotImplementedError) as ctx:
            sdk_why_not(None, None, [])
        self.assertIn("Phase 0 skeleton", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
