from __future__ import annotations

import unittest

import factgraph.sdk as sdk
import factgraph.sdk.dsl as dsl
from factgraph.application.protocol import Rule
from factgraph.application.protocol import RuleValidationError
from factgraph.sdk import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity()
    status: str = Field()


class SDKRuleNamingTests(unittest.TestCase):
    def test_top_level_rule_is_application_protocol_rule(self) -> None:
        self.assertIs(sdk.Rule, Rule)
        self.assertIs(sdk.ApplicationRule, sdk.Rule)
        self.assertIsNot(sdk.Rule, dsl.Rule)

    def test_top_level_application_rule_alias(self) -> None:
        self.assertIs(sdk.ApplicationRule, Rule)

    def test_top_level_application_rule_bridge_aliases(self) -> None:
        self.assertIs(sdk.build_application_rule, dsl.build_application_rule)
        self.assertIs(sdk.DSLToApplicationRuleError, dsl.DSLToApplicationRuleError)

    def test_legacy_rule_construction_is_explicit_dsl_path(self) -> None:
        self.assertNotIn("Rule", dsl.__all__)

        with sdk.vars("u") as (u,):
            rule = dsl.Rule(
                id="legacy_rule",
                version="v1",
                select=[u],
                where=[sdk.Pred("User:exists", u)],
            )

        self.assertIsInstance(rule, dsl.Rule)
        self.assertEqual(rule.id, "legacy_rule")
        self.assertEqual(rule.version, "v1")

    def test_top_level_rule_no_longer_accepts_legacy_dsl_shape(self) -> None:
        with sdk.vars("u") as (u,):
            with self.assertRaises((RuleValidationError, TypeError)):
                sdk.Rule(
                    id="legacy_rule",
                    version="v1",
                    select=[u],
                    where=[sdk.Pred("User:exists", u)],
                )

    def test_top_level_build_application_rule_returns_application_rule(self) -> None:
        with sdk.vars("u") as (u,):
            rule = sdk.build_application_rule(
                id="active_user",
                where=[User(u).status == "active"],
                ports={"user": u},
            )

        self.assertIsInstance(rule, sdk.ApplicationRule)
        self.assertIsInstance(rule, Rule)

    def test_transitional_aliases_are_exported(self) -> None:
        for name in (
            "Rule",
            "ApplicationRule",
            "build_application_rule",
            "DSLToApplicationRuleError",
        ):
            with self.subTest(name=name):
                self.assertIn(name, sdk.__all__)

        self.assertNotIn("LegacyRule", sdk.__all__)
        self.assertFalse(hasattr(sdk, "LegacyRule"))
        self.assertIs(sdk.Inference, dsl.Inference)


if __name__ == "__main__":
    unittest.main()
