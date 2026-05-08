"""G4 cross-cutting invariants.

Phase 0 of G4 (per blueprint
``docs/blueprints/active/2026-05-08_l-direction-g4-why-not-frontier.md`` §8)
seeds the invariant test class. Phase 0 covers only the invariants that
can be verified before the real implementation ships:

- ``kernel.sdk.__all__`` length unchanged at 34 and ``WhyNotUniverseResult``
  not exported (§5.3 lock).
- ``SDKStore.why_not`` exists as instance method, not as a free function
  in ``kernel.sdk.__all__`` (§5.4 instance-method-placement lock).
- No ``kernel/sdk/frontier.py`` module shipped (§5.4 Frontier-stays-
  advanced-importable lock).
- No ``kernel/sdk/shells/`` subpackage exists (§5.5 flat-layout lock).

Phase 2 adds the remaining four invariants per §5.7 (no-internal-walker-
audit-imports / thin-delegate / docstring-boundary-contract / Q1 Sibling
static scan).
"""

from __future__ import annotations

import pathlib
import unittest

from kernel import sdk as kernel_sdk
from kernel.sdk import SDKStore


class SDKG4InvariantPhase0Tests(unittest.TestCase):
    """Phase 0 G4 invariants — must hold before Phase 1 real implementation."""

    def test_sdk_all_unchanged_and_why_not_result_not_exported(self) -> None:
        """§5.3 lock: ``WhyNotUniverseResult`` is not re-exported from SDK."""
        self.assertEqual(len(kernel_sdk.__all__), 34)
        self.assertNotIn("WhyNotUniverseResult", kernel_sdk.__all__)
        self.assertNotIn("why_not", kernel_sdk.__all__)
        self.assertNotIn("sdk_why_not", kernel_sdk.__all__)
        self.assertFalse(hasattr(kernel_sdk, "WhyNotUniverseResult"))

    def test_sdk_store_why_not_is_instance_method(self) -> None:
        """§5.4 lock: ``why_not`` is an SDKStore instance method, not a free function."""
        self.assertTrue(hasattr(SDKStore, "why_not"))
        self.assertTrue(callable(SDKStore.why_not))

    def test_no_frontier_sdk_module_exists(self) -> None:
        """§5.4 lock: G4 ships no Frontier SDK method or module."""
        sdk_dir = pathlib.Path(kernel_sdk.__file__).parent
        self.assertFalse((sdk_dir / "frontier.py").exists())
        self.assertFalse(hasattr(kernel_sdk, "frontier"))

    def test_g4_modules_are_flat_and_no_shells_package_exists(self) -> None:
        """§5.5 lock: ``why_not.py`` is flat at ``src/kernel/sdk/``; no ``shells/`` subpackage."""
        sdk_dir = pathlib.Path(kernel_sdk.__file__).parent
        self.assertTrue((sdk_dir / "why_not.py").is_file())
        self.assertFalse((sdk_dir / "shells").exists())


if __name__ == "__main__":
    unittest.main()
