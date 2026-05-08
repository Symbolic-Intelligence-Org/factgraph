"""Cross-cutting invariants for G3 Rule Overlay SDK shells.

Mirrors G1's `test_sdk_g1_invariants.py`, G4's
`test_sdk_g4_invariants.py`, and G2's `test_sdk_g2_invariants.py`
6-class structure under the active `kernel/sdk/shells/` subpackage
layout (activated at G2 Phase 0; now hosting 8 modules).

Active classes:

1. `test_sdk_all_unchanged_and_g3_result_types_not_exported` — §5.3 / §5.4
2. `test_g3_methods_are_instance_methods_and_no_scenario_method_shipped` — §5.7
3. `test_g3_modules_live_in_shells_subpackage` — §5.5 + §5.6
4. `test_g3_modules_do_not_import_internal_or_walker_layers` — §6 layer isolation
5. `test_store_methods_remain_thin_delegate_methods` — §6 thin-delegate
6. `test_store_method_docstrings_record_boundary_contracts` — §5.7 + §6 docstring
"""

from __future__ import annotations

import inspect
import pathlib
import unittest
from importlib import import_module

from kernel import sdk as kernel_sdk
from kernel.sdk import SDKStore


G3_MODULES = (
    "kernel.sdk.shells.rule_disable",
    "kernel.sdk.shells.rule_literal_replace",
    "kernel.sdk.shells.rule_add_condition",
)
FORBIDDEN_PRODUCTION_IMPORT_TEXT = (
    "kernel.application.capability_helpers._binding",
    "_reject_sdk_origin",
    "from kernel.application.walker",
    "import kernel.application.walker",
    "from kernel.application.walker import",
    "kernel.audit",
    "kernel.core.rules.frontier",
)


class SDKG3InvariantTests(unittest.TestCase):
    """G3 invariants — must hold across all G3 phases."""

    def test_sdk_all_unchanged_and_g3_result_types_not_exported(self) -> None:
        """§5.3 + §5.4 lock: G3 result DTOs are not re-exported from SDK."""
        self.assertEqual(len(kernel_sdk.__all__), 34)
        for name in (
            "RuleDisableResult",
            "RuleDisableAction",
            "RuleDisableRequest",
            "RuleLiteralReplaceResult",
            "RuleLiteralReplaceAction",
            "RuleLiteralReplaceRequest",
            "RuleLiteralPath",
            "RuleAddConditionResult",
            "RuleAddConditionAction",
            "RuleAddConditionRequest",
            "RuleAddedAtom",
            "check_rule_disable",
            "check_rule_literal_replace",
            "check_rule_add_condition",
            "sdk_rule_disable",
            "sdk_rule_literal_replace",
            "sdk_rule_add_condition",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, kernel_sdk.__all__)
                self.assertFalse(hasattr(kernel_sdk, name))

    def test_g3_methods_are_instance_methods_and_no_scenario_method_shipped(
        self,
    ) -> None:
        """§5.7 lock: G3 methods are SDKStore instance methods, not free functions."""
        self.assertTrue(callable(getattr(SDKStore, "check_rule_disable", None)))
        self.assertTrue(
            callable(getattr(SDKStore, "check_rule_literal_replace", None))
        )
        self.assertTrue(
            callable(getattr(SDKStore, "check_rule_add_condition", None))
        )
        for scenario_name in (
            "disable_rule",
            "replace_rule_literal",
            "add_rule_condition",
            "rule_disable",
            "rule_literal_replace",
            "rule_add_condition",
            "mutate_rule",
        ):
            with self.subTest(name=scenario_name):
                self.assertFalse(hasattr(SDKStore, scenario_name))

    def test_g3_modules_live_in_shells_subpackage(self) -> None:
        """§5.5 + §5.6 lock: G3 shells live at
        ``kernel/sdk/shells/{rule_disable,rule_literal_replace,rule_add_condition}.py``.

        Also enforces that the flat ``kernel/sdk/<x>.py`` location must
        not exist.
        """
        sdk_dir = pathlib.Path(kernel_sdk.__file__).parent
        self.assertTrue((sdk_dir / "shells").is_dir())
        self.assertTrue((sdk_dir / "shells" / "__init__.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "rule_disable.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "rule_literal_replace.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "rule_add_condition.py").is_file())
        self.assertFalse((sdk_dir / "rule_disable.py").exists())
        self.assertFalse((sdk_dir / "rule_literal_replace.py").exists())
        self.assertFalse((sdk_dir / "rule_add_condition.py").exists())

    def test_g3_modules_do_not_import_internal_or_walker_layers(self) -> None:
        """§6 lock: G3 SDK shells must not import application internals,
        walker, audit, or frontier."""
        for module_name in G3_MODULES:
            module = import_module(module_name)
            source = pathlib.Path(inspect.getfile(module)).read_text(encoding="utf-8")
            for forbidden in FORBIDDEN_PRODUCTION_IMPORT_TEXT:
                with self.subTest(module=module_name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)

    def test_store_methods_remain_thin_delegate_methods(self) -> None:
        """§6 thin-delegate lock: G3 SDKStore methods are pure delegates.

        Asserts on call/instantiation patterns rather than bare class
        names so that legitimate docstring references to types (e.g.,
        "forwarded to the ``RuleDisableAction``") are not flagged.
        """
        rule_disable_source = inspect.getsource(SDKStore.check_rule_disable)
        rule_literal_replace_source = inspect.getsource(
            SDKStore.check_rule_literal_replace
        )
        rule_add_condition_source = inspect.getsource(
            SDKStore.check_rule_add_condition
        )

        # rule_disable
        self.assertIn(
            "from .shells.rule_disable import sdk_rule_disable", rule_disable_source
        )
        self.assertIn("return sdk_rule_disable(", rule_disable_source)
        self.assertNotIn("RuleDisableRequest(", rule_disable_source)
        self.assertNotIn("check_rule_disable_action(", rule_disable_source)
        self.assertNotIn("validate_rule(", rule_disable_source)
        self.assertNotIn("validate_support_artifact(", rule_disable_source)

        # rule_literal_replace
        self.assertIn(
            "from .shells.rule_literal_replace import sdk_rule_literal_replace",
            rule_literal_replace_source,
        )
        self.assertIn(
            "return sdk_rule_literal_replace(", rule_literal_replace_source
        )
        self.assertNotIn(
            "RuleLiteralReplaceRequest(", rule_literal_replace_source
        )
        self.assertNotIn(
            "check_rule_literal_replace_action(", rule_literal_replace_source
        )
        self.assertNotIn("validate_rule(", rule_literal_replace_source)

        # rule_add_condition
        self.assertIn(
            "from .shells.rule_add_condition import sdk_rule_add_condition",
            rule_add_condition_source,
        )
        self.assertIn(
            "return sdk_rule_add_condition(", rule_add_condition_source
        )
        self.assertNotIn(
            "RuleAddConditionRequest(", rule_add_condition_source
        )
        self.assertNotIn(
            "check_rule_add_condition_action(", rule_add_condition_source
        )
        self.assertNotIn("validate_rule(", rule_add_condition_source)

    def test_store_method_docstrings_record_boundary_contracts(self) -> None:
        """§5.7 + §6 lock: G3 SDKStore method docstrings record boundary
        contracts + paths."""
        rule_disable_doc = SDKStore.check_rule_disable.__doc__ or ""
        rule_literal_replace_doc = SDKStore.check_rule_literal_replace.__doc__ or ""
        rule_add_condition_doc = SDKStore.check_rule_add_condition.__doc__ or ""

        for required in (
            "Rule",
            "SupportArtifact",
            "EvaluationOverlay",
            "RuleDisableResult",
            "SDKStoreError",
            "$.check_rule_disable.rule",
            "$.check_rule_disable.support",
            "$.check_rule_disable.overlay",
            "$.check_rule_disable.dependencies",
            "$.check_rule_disable.request",
            "$.check_rule_disable",
        ):
            with self.subTest(doc="check_rule_disable", required=required):
                self.assertIn(required, rule_disable_doc)

        for required in (
            "Rule",
            "SupportArtifact",
            "EvaluationOverlay",
            "RuleLiteralPath",
            "RuleLiteralReplaceResult",
            "SDKStoreError",
            "$.check_rule_literal_replace.rule",
            "$.check_rule_literal_replace.support",
            "$.check_rule_literal_replace.overlay",
            "$.check_rule_literal_replace.dependencies",
            "$.check_rule_literal_replace.request",
            "$.check_rule_literal_replace",
        ):
            with self.subTest(doc="check_rule_literal_replace", required=required):
                self.assertIn(required, rule_literal_replace_doc)

        for required in (
            "Rule",
            "SupportArtifact",
            "EvaluationOverlay",
            "RuleAddedAtom",
            "RuleAddConditionResult",
            "SDKStoreError",
            "$.check_rule_add_condition.rule",
            "$.check_rule_add_condition.support",
            "$.check_rule_add_condition.overlay",
            "$.check_rule_add_condition.dependencies",
            "$.check_rule_add_condition.request",
            "$.check_rule_add_condition",
        ):
            with self.subTest(doc="check_rule_add_condition", required=required):
                self.assertIn(required, rule_add_condition_doc)


if __name__ == "__main__":
    unittest.main()
