"""Cross-cutting invariants for G4 Why-not SDK shell.

Mirrors G1's `test_sdk_g1_invariants.py` 6-class structure plus one
G4-specific invariant for the §5.4 Frontier-stays-advanced-importable
lock. Active class:

1. `test_sdk_all_unchanged_and_why_not_result_not_exported` — §5.3
2. `test_sdk_store_why_not_flat_method_removed` — Q-NAMING-C
3. `test_no_frontier_sdk_module_or_method_exists` — §5.4 Frontier defer (G4-specific)
4. `test_g4_modules_live_in_shells_subpackage` — §5.5 (retrofit per G2 §5.5 #P1 carve-out)
5. `test_g4_modules_do_not_import_internal_or_walker_layers` — §6 layer isolation
6. `test_private_helper_holds_capability_logic` — Q-NAMING-C private helper retention
7. `test_store_method_docstring_records_boundary_contract` — §5.7 + §6 docstring
"""

from __future__ import annotations

import inspect
import pathlib
import unittest
from importlib import import_module

from factgraph import sdk as factgraph_sdk
from factgraph.sdk import SDKStore
from factgraph.sdk.shells.why_not import sdk_why_not


G4_MODULES = ("factgraph.sdk.shells.why_not",)
FORBIDDEN_PRODUCTION_IMPORT_TEXT = (
    "factgraph.application.capability_helpers._binding",
    "_reject_sdk_origin",
    "from factgraph.application.walker",
    "import factgraph.application.walker",
    "from factgraph.application.walker import",
    "factgraph.audit",
    "factgraph.core.rules.frontier",
)


class SDKG4InvariantTests(unittest.TestCase):
    """G4 invariants — must hold across all G4 phases."""

    def test_sdk_all_unchanged_and_why_not_result_not_exported(self) -> None:
        """§5.3 lock: ``WhyNotUniverseResult`` is not re-exported from SDK."""
        self.assertIn("SchemaAddResult", factgraph_sdk.__all__)
        self.assertIn("FactGraph", factgraph_sdk.__all__)
        self.assertIn("SemanticsProfile", factgraph_sdk.__all__)
        self.assertIn("ProbLogSemantics", factgraph_sdk.__all__)
        self.assertIn("PyReasonSemantics", factgraph_sdk.__all__)
        self.assertNotIn("WhyNotUniverseResult", factgraph_sdk.__all__)
        self.assertNotIn("why_not", factgraph_sdk.__all__)
        self.assertNotIn("sdk_why_not", factgraph_sdk.__all__)
        self.assertFalse(hasattr(factgraph_sdk, "WhyNotUniverseResult"))

    def test_sdk_store_why_not_flat_method_removed(self) -> None:
        """Q-NAMING-C lock: ``why_not`` is no longer an SDKStore method.

        Post-G2 Phase 0 hygiene: the shell module lives at
        ``factgraph.sdk.shells.why_not``, not at ``factgraph.sdk.why_not``.
        ``factgraph.sdk.why_not`` therefore should not exist either as a
        callable free function or as a submodule attribute.
        """
        self.assertFalse(hasattr(SDKStore, "why_not"))
        self.assertTrue(callable(sdk_why_not))
        self.assertFalse(hasattr(factgraph_sdk, "why_not"))

    def test_no_frontier_sdk_module_or_method_exists(self) -> None:
        """§5.4 lock: G4 ships no Frontier SDK method or module (flat or under shells/)."""
        sdk_dir = pathlib.Path(factgraph_sdk.__file__).parent
        self.assertFalse((sdk_dir / "frontier.py").exists())
        self.assertFalse((sdk_dir / "shells" / "frontier.py").exists())
        self.assertFalse(hasattr(factgraph_sdk, "frontier"))
        self.assertFalse(hasattr(SDKStore, "frontier"))
        self.assertFalse(hasattr(SDKStore, "frontier_view_facts"))

    def test_g4_modules_live_in_shells_subpackage(self) -> None:
        """Retrofit per G2 §5.5 #P1 carve-out: ``why_not.py`` migrated into ``factgraph/sdk/shells/``."""
        sdk_dir = pathlib.Path(factgraph_sdk.__file__).parent
        self.assertTrue((sdk_dir / "shells").is_dir())
        self.assertTrue((sdk_dir / "shells" / "__init__.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "why_not.py").is_file())
        self.assertFalse((sdk_dir / "why_not.py").exists())

    def test_g4_modules_do_not_import_internal_or_walker_layers(self) -> None:
        """§6 lock: G4 SDK modules must not import application internals, walker, or audit layers."""
        for module_name in G4_MODULES:
            module = import_module(module_name)
            source = pathlib.Path(inspect.getfile(module)).read_text(encoding="utf-8")
            for forbidden in FORBIDDEN_PRODUCTION_IMPORT_TEXT:
                with self.subTest(module=module_name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)

    def test_private_helper_holds_capability_logic(self) -> None:
        """Q-NAMING-C keeps the why-not shell module as a private helper."""
        why_not_source = inspect.getsource(sdk_why_not)

        self.assertIn("build_why_not_candidate_universe", why_not_source)
        self.assertIn("check_why_not_universe", why_not_source)
        self.assertIn("WhyNotUniverseRequest", why_not_source)

    def test_store_method_docstring_records_boundary_contract(self) -> None:
        """§5.7 + §6 lock: ``sdk_why_not`` docstring records boundary contract."""
        why_not_doc = sdk_why_not.__doc__ or ""

        self.assertIn("Inference", why_not_doc)
        self.assertIn("WhyNotUniverseResult", why_not_doc)
        self.assertIn("candidate", why_not_doc.lower())


if __name__ == "__main__":
    unittest.main()
