"""Cross-cutting invariants for G2 Fact Overlay + ProofFrame Recheck SDK shells.

Mirrors G1's `test_sdk_g1_invariants.py` and G4's
`test_sdk_g4_invariants.py` 6-class structure under the post-G2-Phase-0
`factgraph/sdk/shells/` subpackage layout. Active classes:

1. `test_sdk_all_unchanged_and_g2_result_types_not_exported` — §5.3 / §5.4
2. `test_g2_flat_methods_are_removed_and_no_scenario_method_shipped` — Q-NAMING-C
3. `test_g2_modules_live_in_shells_subpackage` — §5.5 + §5.6
4. `test_g2_modules_do_not_import_internal_or_walker_layers` — §6 layer isolation
5. `test_private_helpers_hold_capability_logic` — Q-NAMING-C private helper retention
6. `test_store_method_docstrings_record_boundary_contracts` — §5.7 + §6 docstring
"""

from __future__ import annotations

import inspect
import pathlib
import unittest
from importlib import import_module

from factgraph import sdk as factgraph_sdk
from factgraph.sdk import SDKStore
from factgraph.sdk.shells.fact_overlay import sdk_fact_overlay_check
from factgraph.sdk.shells.proof_frame import sdk_proof_frame_recheck


G2_MODULES = (
    "factgraph.sdk.shells.fact_overlay",
    "factgraph.sdk.shells.proof_frame",
)
FORBIDDEN_PRODUCTION_IMPORT_TEXT = (
    "factgraph.application.capability_helpers._binding",
    "_reject_sdk_origin",
    "from factgraph.application.walker",
    "import factgraph.application.walker",
    "from factgraph.application.walker import",
    "factgraph.audit",
    "factgraph.core.rules.frontier",
)


class SDKG2InvariantTests(unittest.TestCase):
    """G2 invariants — must hold across all G2 phases."""

    def test_sdk_all_unchanged_and_g2_result_types_not_exported(self) -> None:
        """§5.3 + §5.4 lock: G2 result DTOs are not re-exported from SDK."""
        self.assertIn("SchemaAddResult", factgraph_sdk.__all__)
        self.assertIn("FactGraph", factgraph_sdk.__all__)
        self.assertIn("SemanticsProfile", factgraph_sdk.__all__)
        self.assertIn("ProbLogConfig", factgraph_sdk.__all__)
        self.assertIn("PyReasonConfig", factgraph_sdk.__all__)
        for name in (
            "FactOverlayCheckResult",
            "ProofFrameRecheckResult",
            "FactOverlay",
            "ReplaceFact",
            "RemoveFact",
            "ProofFrameConditionVerdict",
            "check_fact_overlay",
            "recheck_proof_frame",
            "sdk_fact_overlay_check",
            "sdk_proof_frame_recheck",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, factgraph_sdk.__all__)
                self.assertFalse(hasattr(factgraph_sdk, name))

    def test_g2_flat_methods_are_removed_and_no_scenario_method_shipped(self) -> None:
        """Q-NAMING-C lock: G2 flat SDKStore methods are removed."""
        self.assertFalse(hasattr(SDKStore, "check_fact_overlay"))
        self.assertFalse(hasattr(SDKStore, "recheck_proof_frame"))
        for scenario_name in (
            "explain",
            "fact_overlay",
            "overlay_check",
            "proof_frame",
            "recheck",
        ):
            with self.subTest(name=scenario_name):
                self.assertFalse(hasattr(SDKStore, scenario_name))

    def test_g2_modules_live_in_shells_subpackage(self) -> None:
        """§5.5 + §5.6 lock: G2 shells live at ``factgraph/sdk/shells/{fact_overlay,proof_frame}.py``.

        Also enforces that the shared SDK shell validators
        (``_validation.py``) sit under ``factgraph/sdk/shells/`` post-G2
        Phase 0 hygiene migration; the flat ``factgraph/sdk/_validation.py``
        location must not exist.
        """
        sdk_dir = pathlib.Path(factgraph_sdk.__file__).parent
        self.assertTrue((sdk_dir / "shells").is_dir())
        self.assertTrue((sdk_dir / "shells" / "__init__.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "fact_overlay.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "proof_frame.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "_validation.py").is_file())
        self.assertFalse((sdk_dir / "fact_overlay.py").exists())
        self.assertFalse((sdk_dir / "proof_frame.py").exists())
        self.assertFalse((sdk_dir / "_validation.py").exists())

    def test_g2_modules_do_not_import_internal_or_walker_layers(self) -> None:
        """§6 lock: G2 SDK shells must not import application internals, walker, audit, or frontier."""
        for module_name in G2_MODULES:
            module = import_module(module_name)
            source = pathlib.Path(inspect.getfile(module)).read_text(encoding="utf-8")
            for forbidden in FORBIDDEN_PRODUCTION_IMPORT_TEXT:
                with self.subTest(module=module_name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)

    def test_private_helpers_hold_capability_logic(self) -> None:
        """Q-NAMING-C keeps G2 shell modules as private helpers."""
        fact_overlay_source = inspect.getsource(sdk_fact_overlay_check)
        proof_frame_source = inspect.getsource(sdk_proof_frame_recheck)

        self.assertIn("FactOverlayCheckRequest(", fact_overlay_source)
        self.assertIn("check_fact_overlay_binding(", fact_overlay_source)
        self.assertIn("resolve_derivation_plan(", fact_overlay_source)
        self.assertIn("validate_binding(", fact_overlay_source)

        self.assertIn("ProofFrameRecheckRequest(", proof_frame_source)
        self.assertIn("recheck_proof_frame(request", proof_frame_source)
        self.assertIn("validate_support_artifact(", proof_frame_source)
        self.assertIn("validate_evaluation_overlay(", proof_frame_source)

    def test_store_method_docstrings_record_boundary_contracts(self) -> None:
        """§5.7 + §6 lock: G2 SDKStore method docstrings record boundary contracts + paths."""
        fact_overlay_doc = sdk_fact_overlay_check.__doc__ or ""
        proof_frame_doc = sdk_proof_frame_recheck.__doc__ or ""

        for required in (
            "Inference",
            "FactOverlayCheckResult",
            "check_fact_overlay_binding",
        ):
            with self.subTest(doc="check_fact_overlay", required=required):
                self.assertIn(required, fact_overlay_doc)

        for required in (
            "support frame",
            "overlay",
            "ProofFrameRecheckResult",
        ):
            with self.subTest(doc="recheck_proof_frame", required=required):
                self.assertIn(required, proof_frame_doc)


if __name__ == "__main__":
    unittest.main()
