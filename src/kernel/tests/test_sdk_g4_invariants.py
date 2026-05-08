"""Cross-cutting invariants for G4 Why-not SDK shell.

Mirrors G1's `test_sdk_g1_invariants.py` 6-class structure plus one
G4-specific invariant for the §5.4 Frontier-stays-advanced-importable
lock. Active class:

1. `test_sdk_all_unchanged_and_why_not_result_not_exported` — §5.3
2. `test_sdk_store_why_not_is_instance_method` — §5.4
3. `test_no_frontier_sdk_module_exists` — §5.4 Frontier defer (G4-specific)
4. `test_g4_modules_are_flat_and_no_shells_package_exists` — §5.5
5. `test_g4_modules_do_not_import_internal_or_walker_layers` — §6 layer isolation
6. `test_store_method_remains_thin_delegate_method` — §6 thin-delegate
7. `test_store_method_docstring_records_boundary_contract` — §5.7 + §6 docstring
"""

from __future__ import annotations

import inspect
import pathlib
import unittest
from importlib import import_module

from kernel import sdk as kernel_sdk
from kernel.sdk import SDKStore


G4_MODULES = ("kernel.sdk.why_not",)
FORBIDDEN_PRODUCTION_IMPORT_TEXT = (
    "kernel.application.capability_helpers._binding",
    "_reject_sdk_origin",
    "from kernel.application.walker",
    "import kernel.application.walker",
    "from kernel.application.walker import",
    "kernel.audit",
    "kernel.core.rules.frontier",
)


class SDKG4InvariantTests(unittest.TestCase):
    """G4 invariants — must hold across all G4 phases."""

    def test_sdk_all_unchanged_and_why_not_result_not_exported(self) -> None:
        """§5.3 lock: ``WhyNotUniverseResult`` is not re-exported from SDK."""
        self.assertEqual(len(kernel_sdk.__all__), 34)
        self.assertNotIn("WhyNotUniverseResult", kernel_sdk.__all__)
        self.assertNotIn("why_not", kernel_sdk.__all__)
        self.assertNotIn("sdk_why_not", kernel_sdk.__all__)
        self.assertFalse(hasattr(kernel_sdk, "WhyNotUniverseResult"))

    def test_sdk_store_why_not_is_instance_method(self) -> None:
        """§5.4 lock: ``why_not`` is an SDKStore instance method, not a free function.

        ``kernel.sdk.why_not`` resolves to the submodule (``why_not.py``) once
        any test in the process has imported it; the lock is that the SDK
        package never exposes ``why_not`` as a callable free function.
        """
        import types

        self.assertTrue(hasattr(SDKStore, "why_not"))
        self.assertTrue(callable(SDKStore.why_not))
        if hasattr(kernel_sdk, "why_not"):
            self.assertIsInstance(kernel_sdk.why_not, types.ModuleType)

    def test_no_frontier_sdk_module_or_method_exists(self) -> None:
        """§5.4 lock: G4 ships no Frontier SDK method or module."""
        sdk_dir = pathlib.Path(kernel_sdk.__file__).parent
        self.assertFalse((sdk_dir / "frontier.py").exists())
        self.assertFalse(hasattr(kernel_sdk, "frontier"))
        self.assertFalse(hasattr(SDKStore, "frontier"))
        self.assertFalse(hasattr(SDKStore, "frontier_view_facts"))

    def test_g4_modules_are_flat_and_no_shells_package_exists(self) -> None:
        """§5.5 lock: ``why_not.py`` is flat at ``src/kernel/sdk/``; no ``shells/`` subpackage."""
        sdk_dir = pathlib.Path(kernel_sdk.__file__).parent
        self.assertTrue((sdk_dir / "why_not.py").is_file())
        self.assertFalse((sdk_dir / "shells").exists())

    def test_g4_modules_do_not_import_internal_or_walker_layers(self) -> None:
        """§6 lock: G4 SDK modules must not import application internals, walker, or audit layers."""
        for module_name in G4_MODULES:
            module = import_module(module_name)
            source = pathlib.Path(inspect.getfile(module)).read_text(encoding="utf-8")
            for forbidden in FORBIDDEN_PRODUCTION_IMPORT_TEXT:
                with self.subTest(module=module_name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)

    def test_store_method_remains_thin_delegate_method(self) -> None:
        """§6 thin-delegate lock: ``SDKStore.why_not`` body is just ``from .why_not import ...; return ...``."""
        why_not_source = inspect.getsource(SDKStore.why_not)

        self.assertIn("from .why_not import sdk_why_not", why_not_source)
        self.assertIn("return sdk_why_not(", why_not_source)
        self.assertNotIn("build_why_not_candidate_universe", why_not_source)
        self.assertNotIn("check_why_not_universe", why_not_source)
        self.assertNotIn("WhyNotUniverseRequest", why_not_source)

    def test_store_method_docstring_records_boundary_contract(self) -> None:
        """§5.7 + §6 lock: ``SDKStore.why_not`` docstring records boundary contract."""
        why_not_doc = SDKStore.why_not.__doc__ or ""

        self.assertIn("Derivation", why_not_doc)
        self.assertIn("WhyNotUniverseResult", why_not_doc)
        self.assertIn("SDKStoreError", why_not_doc)
        self.assertIn("candidate", why_not_doc.lower())
        for path in (
            "$.why_not.derivation",
            "$.why_not.dependencies",
            "$.why_not.candidates",
            "$.why_not.request",
            "$.why_not",
        ):
            with self.subTest(path=path):
                self.assertIn(path, why_not_doc)


if __name__ == "__main__":
    unittest.main()
