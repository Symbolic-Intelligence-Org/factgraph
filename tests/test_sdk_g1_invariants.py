"""Cross-cutting invariants for G1 Check/Diagnose SDK shells."""

from __future__ import annotations

import inspect
import unittest
from importlib import import_module
from pathlib import Path

import factgraph.sdk as sdk_pkg
from factgraph.sdk import SDKStore
from factgraph.sdk.shells.check import sdk_check
from factgraph.sdk.shells.diagnose import sdk_diagnose


EXPECTED_SDK_ALL: tuple[str, ...] = (
    "Case",
    "CardinalityError",
    "Inference",
    "EditorClosedError",
    "Entity",
    "EntityNotFoundError",
    "FactGraph",
    "Field",
    "FrozenSnapshotError",
    "INVALID_ROW_FORMAT",
    "Identity",
    "IngestResult",
    "Not",
    "Pred",
    "QUERY_ALIAS_CONFLICT",
    "QUERY_INVALID_ROW_FORMAT",
    "QUERY_MISSING_REF",
    "QUERY_NOT_IMPLEMENTED",
    "QUERY_TYPE_MISMATCH",
    "QUERY_UNBOUND_VAR",
    "Query",
    "ReadPolicy",
    "Relationship",
    "Rule",
    "RuleRef",
    "SchemaAddResult",
    "SDKDSLError",
    "SDKSchemaError",
    "SDKStore",
    "SDKStoreError",
    "SemanticsProfile",
    "ProbLogSemantics",
    "PyReasonSemantics",
    "ValidationReport",
    "build_authoring_schema_from_classes",
    "compile_schema_from_classes",
    "schema_preflight_from_classes",
    "vars",
)

G1_MODULES = ("factgraph.sdk.shells.check", "factgraph.sdk.shells.diagnose")
FORBIDDEN_PRODUCTION_IMPORT_TEXT = (
    "factgraph.application.capability_helpers._binding",
    "_reject_sdk_origin",
    "from factgraph.application.walker",
    "import factgraph.application.walker",
    "from factgraph.application.walker import",
    "factgraph.audit",
)


class SDKG1InvariantTests(unittest.TestCase):
    def test_sdk_all_is_unchanged_and_result_types_are_not_exported(self) -> None:
        self.assertIn("FactGraph", sdk_pkg.__all__)
        self.assertIn("SemanticsProfile", sdk_pkg.__all__)
        self.assertIn("ProbLogSemantics", sdk_pkg.__all__)
        self.assertIn("PyReasonSemantics", sdk_pkg.__all__)
        for name in ("CheckResult", "DiagnoseResult"):
            with self.subTest(name=name):
                self.assertNotIn(name, sdk_pkg.__all__)
                self.assertFalse(hasattr(sdk_pkg, name))

    def test_g1_flat_methods_are_removed_and_no_scenario_method_shipped(self) -> None:
        self.assertFalse(hasattr(SDKStore, "check"))
        self.assertFalse(hasattr(SDKStore, "diagnose"))
        self.assertFalse(hasattr(SDKStore, "explain"))

    def test_g1_modules_live_in_shells_subpackage(self) -> None:
        """Retrofit per G2 §5.5 #P1 carve-out: G1 shells migrated into factgraph/sdk/shells/."""
        sdk_dir = Path(inspect.getfile(SDKStore)).parent
        self.assertTrue((sdk_dir / "shells").is_dir())
        self.assertTrue((sdk_dir / "shells" / "__init__.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "check.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "diagnose.py").is_file())
        self.assertFalse((sdk_dir / "check.py").exists())
        self.assertFalse((sdk_dir / "diagnose.py").exists())

    def test_g1_modules_do_not_import_internal_or_walker_layers(self) -> None:
        for module_name in G1_MODULES:
            module = import_module(module_name)
            source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
            for forbidden in FORBIDDEN_PRODUCTION_IMPORT_TEXT:
                with self.subTest(module=module_name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)

    def test_private_helpers_hold_capability_logic(self) -> None:
        check_source = inspect.getsource(sdk_check)
        diagnose_source = inspect.getsource(sdk_diagnose)

        self.assertIn("build_check_request", check_source)
        self.assertIn("check_derivation_binding", check_source)

        self.assertIn("build_diagnose_request", diagnose_source)
        self.assertIn("diagnose_derivation_binding", diagnose_source)

    def test_store_method_docstrings_record_boundary_contracts(self) -> None:
        check_doc = sdk_check.__doc__ or ""
        diagnose_doc = sdk_diagnose.__doc__ or ""

        self.assertIn("Inference", check_doc)
        self.assertIn("CheckResult", check_doc)
        self.assertIn("walker", check_doc)

        self.assertIn("Inference", diagnose_doc)
        self.assertIn("DiagnoseResult", diagnose_doc)
        self.assertIn("not import walker helpers", diagnose_doc)


if __name__ == "__main__":
    unittest.main()
