from __future__ import annotations

import unittest

import factgraph.sdk as sdk
import factgraph.sdk.dsl as dsl
from factgraph.application.protocol import Rule as ApplicationRule
from factgraph.sdk import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    status: str = Field(cardinality="single")


class SDKRuleNamingTests(unittest.TestCase):
    def test_top_level_rule_remains_legacy_rule(self) -> None:
        self.assertIs(sdk.Rule, dsl.Rule)
        self.assertIs(sdk.LegacyRule, dsl.Rule)
        self.assertIs(sdk.Rule, sdk.LegacyRule)

    def test_top_level_application_rule_alias(self) -> None:
        self.assertIs(sdk.ApplicationRule, ApplicationRule)

    def test_top_level_application_rule_bridge_aliases(self) -> None:
        self.assertIs(sdk.build_application_rule, dsl.build_application_rule)
        self.assertIs(sdk.DSLToApplicationRuleError, dsl.DSLToApplicationRuleError)

    def test_legacy_top_level_rule_construction_still_works(self) -> None:
        with sdk.vars("u") as (u,):
            rule = sdk.Rule(
                id="legacy_rule",
                version="v1",
                select=[u],
                where=[sdk.Pred("User:exists", u)],
            )

        self.assertIsInstance(rule, sdk.LegacyRule)
        self.assertEqual(rule.id, "legacy_rule")
        self.assertEqual(rule.version, "v1")

    def test_top_level_build_application_rule_returns_application_rule(self) -> None:
        with sdk.vars("u") as (u,):
            rule = sdk.build_application_rule(
                id="active_user",
                where=[User(u).status == "active"],
                ports={"user": u},
            )

        self.assertIsInstance(rule, sdk.ApplicationRule)
        self.assertIsInstance(rule, ApplicationRule)

    def test_transitional_aliases_are_exported(self) -> None:
        for name in (
            "Rule",
            "LegacyRule",
            "ApplicationRule",
            "build_application_rule",
            "DSLToApplicationRuleError",
        ):
            with self.subTest(name=name):
                self.assertIn(name, sdk.__all__)


if __name__ == "__main__":
    unittest.main()
