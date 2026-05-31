"""Cross-cutting invariants for G3 Rule Overlay SDK shells.

Mirrors G1's `test_sdk_g1_invariants.py`, G4's
`test_sdk_g4_invariants.py`, and G2's `test_sdk_g2_invariants.py`
6-class structure under the active `factgraph/sdk/shells/` subpackage
layout (activated at G2 Phase 0; now hosting 8 modules).

Active classes:

1. `test_sdk_all_unchanged_and_g3_result_types_not_exported` — §5.3 / §5.4
2. `test_g3_flat_methods_are_removed_and_no_scenario_method_shipped` — Q-NAMING-C
3. `test_g3_modules_live_in_shells_subpackage` — §5.5 + §5.6
4. `test_g3_modules_do_not_import_internal_or_walker_layers` — §6 layer isolation
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
from factgraph.sdk.shells.rule_disable import sdk_rule_disable
from factgraph.sdk.shells.rule_literal_replace import sdk_rule_literal_replace
from factgraph.sdk.shells.rule_add_condition import sdk_rule_add_condition


G3_MODULES = (
    "factgraph.sdk.shells.rule_disable",
    "factgraph.sdk.shells.rule_literal_replace",
    "factgraph.sdk.shells.rule_add_condition",
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


class SDKG3InvariantTests(unittest.TestCase):
    """G3 invariants — must hold across all G3 phases."""

    def test_sdk_all_unchanged_and_g3_result_types_not_exported(self) -> None:
        """§5.3 + §5.4 lock: G3 result DTOs are not re-exported from SDK."""
        self.assertIn("SchemaAddResult", factgraph_sdk.__all__)
        self.assertIn("FactGraph", factgraph_sdk.__all__)
        self.assertIn("SemanticsProfile", factgraph_sdk.__all__)
        self.assertIn("ProbLogConfig", factgraph_sdk.__all__)
        self.assertIn("PyReasonConfig", factgraph_sdk.__all__)
        for name in (
            "RuleDisableResult",
            "RuleDisableAction",
            "RuleDisableRequest",
            "RuleLiteralReplaceResult",
            "RuleLiteralReplaceAction",
            "RuleLiteralReplaceRequest",
            "ConditionPath",
            "RuleAddConditionResult",
            "RuleAddConditionAction",
            "RuleAddConditionRequest",
            "AddedCondition",
            "check_rule_disable",
            "check_rule_literal_replace",
            "check_rule_add_condition",
            "sdk_rule_disable",
            "sdk_rule_literal_replace",
            "sdk_rule_add_condition",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, factgraph_sdk.__all__)
                self.assertFalse(hasattr(factgraph_sdk, name))

    def test_g3_flat_methods_are_removed_and_no_scenario_method_shipped(
        self,
    ) -> None:
        """Q-NAMING-C lock: G3 flat SDKStore methods are removed."""
        self.assertFalse(hasattr(SDKStore, "check_rule_disable"))
        self.assertFalse(hasattr(SDKStore, "check_rule_literal_replace"))
        self.assertFalse(hasattr(SDKStore, "check_rule_add_condition"))
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
        ``factgraph/sdk/shells/{rule_disable,rule_literal_replace,rule_add_condition}.py``.

        Also enforces that the flat ``factgraph/sdk/<x>.py`` location must
        not exist.
        """
        sdk_dir = pathlib.Path(factgraph_sdk.__file__).parent
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

    def test_private_helpers_hold_capability_logic(self) -> None:
        """Q-NAMING-C keeps G3 shell modules as private helpers."""
        rule_disable_source = inspect.getsource(sdk_rule_disable)
        rule_literal_replace_source = inspect.getsource(
            sdk_rule_literal_replace
        )
        rule_add_condition_source = inspect.getsource(
            sdk_rule_add_condition
        )

        self.assertIn("build_rule_disable_request(", rule_disable_source)
        self.assertIn("check_rule_disable_action(", rule_disable_source)
        self.assertIn("validate_rule(", rule_disable_source)
        self.assertIn("validate_support_artifact(", rule_disable_source)

        self.assertIn("build_rule_literal_replace_request(", rule_literal_replace_source)
        self.assertIn("check_rule_literal_replace_action(", rule_literal_replace_source)
        self.assertIn("validate_rule(", rule_literal_replace_source)

        self.assertIn("build_rule_add_condition_request(", rule_add_condition_source)
        self.assertIn("check_rule_add_condition_action(", rule_add_condition_source)
        self.assertIn("validate_rule(", rule_add_condition_source)

    def test_store_method_docstrings_record_boundary_contracts(self) -> None:
        """§5.7 + §6 lock: G3 SDKStore method docstrings record boundary
        contracts + paths."""
        rule_disable_doc = sdk_rule_disable.__doc__ or ""
        rule_literal_replace_doc = sdk_rule_literal_replace.__doc__ or ""
        rule_add_condition_doc = sdk_rule_add_condition.__doc__ or ""

        for required in (
            "Rule",
            "support",
            "RuleDisableResult",
        ):
            with self.subTest(doc="check_rule_disable", required=required):
                self.assertIn(required, rule_disable_doc)

        for required in (
            "Rule",
            "literal-path",
            "RuleLiteralReplaceResult",
        ):
            with self.subTest(doc="check_rule_literal_replace", required=required):
                self.assertIn(required, rule_literal_replace_doc)

        for required in (
            "Rule",
            "new atom",
            "RuleAddConditionResult",
        ):
            with self.subTest(doc="check_rule_add_condition", required=required):
                self.assertIn(required, rule_add_condition_doc)


if __name__ == "__main__":
    unittest.main()
