from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from factpy_kernel.facade.rules_v1 import validate_rule


class FacadeRulesV1ValidateTests(unittest.TestCase):
    def test_validate_rule_default_profile_success_with_json_where(self) -> None:
        resp = validate_rule(_dto(rule=_rule_pred_only_json()))
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["errors"], [])
        self.assertEqual(resp["meta"]["profile_effective"], "default")
        self.assertEqual(resp["meta"]["mode"], "souffle")

    def test_validate_rule_strict_rejects_ruleref_even_when_env_gates_off(self) -> None:
        with patch.dict(
            os.environ,
            {"FACTPY_RULE_AST_VALIDATE": "0", "FACTPY_WHERE_AST_VALIDATE": "0"},
            clear=False,
        ):
            resp = validate_rule(_dto(strict=True, rule=_rule_ruleref_json()))
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["meta"]["profile_effective"], "souffle_strict")
        self.assertEqual(len(resp["errors"]), 1)
        err = resp["errors"][0]
        self.assertEqual(err["kind"], "rule_ast_validate")
        self.assertEqual(err["path"], "$.query_rule.where[0]")
        self.assertIn("message", err["details"])

    def test_profile_default_overrides_strict_true(self) -> None:
        resp = validate_rule(_dto(strict=True, profile={"name": "default"}, rule=_rule_ruleref_json()))
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["meta"]["profile_effective"], "default")

    def test_unknown_profile_name_returns_structured_error(self) -> None:
        resp = validate_rule(_dto(profile={"name": "unknown_profile"}))
        self.assertFalse(resp["ok"])
        err = resp["errors"][0]
        self.assertEqual(err["kind"], "profile_unknown")
        self.assertEqual(err["path"], "$.profile.name")
        self.assertIn("message", err["details"])


def _dto(
    *,
    rule: dict[str, object] | None = None,
    strict: bool | None = None,
    profile: dict[str, object] | None = None,
    mode: str = "souffle",
) -> dict[str, object]:
    dto: dict[str, object] = {
        "api_version": "v1",
        "mode": mode,
        "rule": rule or _rule_pred_only_json(),
    }
    if strict is not None:
        dto["strict"] = strict
    if profile is not None:
        dto["profile"] = profile
    return dto


def _rule_pred_only_json() -> dict[str, object]:
    return {
        "rule_id": "rules.country_rows",
        "version": "v1",
        "select_vars": ["$E", "$C"],
        "where": [["pred", "person:country", ["$E", "$C"]]],
        "expose": True,
    }


def _rule_ruleref_json() -> dict[str, object]:
    return {
        "rule_id": "rules.rank_rows",
        "version": "v1",
        "select_vars": ["$E", "$R"],
        "where": [["ruleref", "q_rank", "1.0.0", ["$E", "$R"]]],
    }


if __name__ == "__main__":
    unittest.main()
