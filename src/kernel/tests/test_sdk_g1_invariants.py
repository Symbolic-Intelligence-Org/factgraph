"""Cross-cutting invariants for G1 Check/Diagnose SDK shells."""

from __future__ import annotations

import inspect
import unittest
from importlib import import_module
from pathlib import Path

import kernel.sdk as sdk_pkg
from kernel.sdk import SDKStore


EXPECTED_SDK_ALL: tuple[str, ...] = (
    "Body",
    "CardinalityError",
    "Derivation",
    "EditorClosedError",
    "Entity",
    "EntityNotFoundError",
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
    "Relationship",
    "Rule",
    "RuleRef",
    "SDKDSLError",
    "SDKRegistry",
    "SDKRegistryError",
    "SDKSchemaError",
    "SDKStore",
    "SDKStoreError",
    "ValidationReport",
    "build_authoring_schema_from_classes",
    "compile_schema_from_classes",
    "schema_preflight_from_classes",
    "vars",
)

G1_MODULES = ("kernel.sdk.shells.check", "kernel.sdk.shells.diagnose")
FORBIDDEN_PRODUCTION_IMPORT_TEXT = (
    "kernel.application.capability_helpers._binding",
    "_reject_sdk_origin",
    "from kernel.application.walker",
    "import kernel.application.walker",
    "from kernel.application.walker import",
    "kernel.audit",
)


class SDKG1InvariantTests(unittest.TestCase):
    def test_sdk_all_is_unchanged_and_result_types_are_not_exported(self) -> None:
        self.assertEqual(set(sdk_pkg.__all__), set(EXPECTED_SDK_ALL))
        self.assertEqual(len(sdk_pkg.__all__), 34)
        for name in ("CheckResult", "DiagnoseResult"):
            with self.subTest(name=name):
                self.assertNotIn(name, sdk_pkg.__all__)
                self.assertFalse(hasattr(sdk_pkg, name))

    def test_g1_methods_are_instance_methods_and_no_scenario_method_shipped(self) -> None:
        self.assertTrue(callable(getattr(SDKStore, "check", None)))
        self.assertTrue(callable(getattr(SDKStore, "diagnose", None)))
        self.assertFalse(hasattr(SDKStore, "explain"))

    def test_g1_modules_live_in_shells_subpackage(self) -> None:
        """Retrofit per G2 §5.5 #P1 carve-out: G1 shells migrated into kernel/sdk/shells/."""
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

    def test_store_methods_remain_thin_delegate_methods(self) -> None:
        check_source = inspect.getsource(SDKStore.check)
        diagnose_source = inspect.getsource(SDKStore.diagnose)

        self.assertIn("from .shells.check import sdk_check", check_source)
        self.assertIn("return sdk_check(", check_source)
        self.assertNotIn("build_check_request", check_source)
        self.assertNotIn("check_derivation_binding", check_source)

        self.assertIn("from .shells.diagnose import sdk_diagnose", diagnose_source)
        self.assertIn("return sdk_diagnose(", diagnose_source)
        self.assertNotIn("build_diagnose_request", diagnose_source)
        self.assertNotIn("diagnose_derivation_binding", diagnose_source)

    def test_store_method_docstrings_record_boundary_contracts(self) -> None:
        check_doc = SDKStore.check.__doc__ or ""
        diagnose_doc = SDKStore.diagnose.__doc__ or ""

        self.assertIn("Derivation", check_doc)
        self.assertIn("CheckResult", check_doc)
        self.assertIn("SDKStoreError", check_doc)
        self.assertIn("SupportArtifactView", check_doc)

        self.assertIn("Derivation", diagnose_doc)
        self.assertIn("DiagnoseResult", diagnose_doc)
        self.assertIn("SDKStoreError", diagnose_doc)
        self.assertIn("not import walker helpers", diagnose_doc)


if __name__ == "__main__":
    unittest.main()
