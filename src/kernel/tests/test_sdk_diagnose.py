"""Phase 0 skeleton test for SDKStore.diagnose.

Validates the Phase 0 stub raises ``NotImplementedError`` when invoked
through the ``SDKStore.diagnose`` instance method delegation. Full
contract tests (passed / failed.no_candidate / failed.atom_localized /
unsupported / invalid_request paths, error remap, type-check,
single-head, Q1 Sibling assertion, engine + registry coverage) land in
Phase 2 per blueprint
``docs/blueprints/active/2026-05-08_l-direction-g1-check-diagnose.md`` §8.
"""

from __future__ import annotations

import unittest

from kernel.sdk import Entity, Identity, SDKStore


class _DummyEntity(Entity):
    name: str = Identity(primary_key=True)


class TestSDKDiagnosePhase0(unittest.TestCase):
    """Phase 0 — verifies stub delegation; no real Diagnose behavior tested."""

    def test_sdk_diagnose_phase0_stub_raises_not_implemented(self) -> None:
        sdk = SDKStore.from_schema_classes(classes=[_DummyEntity])
        with self.assertRaises(NotImplementedError):
            sdk.diagnose(None, {})


if __name__ == "__main__":
    unittest.main()
