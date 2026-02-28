from __future__ import annotations

import unittest

from factpy_kernel.service.rules_v1 import compile_rule_preview


class FacadeRulesV1CompilePreviewTests(unittest.TestCase):
    def test_compile_preview_validation_failure_returns_no_preview(self) -> None:
        resp = compile_rule_preview(_dto(strict=True, rule=_rule_ruleref_json()))
        self.assertFalse(resp["ok"])
        self.assertNotIn("preview", resp)
        self.assertEqual(resp["meta"]["profile_effective"], "souffle_strict")
        self.assertEqual(resp["errors"][0]["kind"], "rule_ast_validate")

    def test_compile_preview_success_returns_compiled_payload_and_profile_effective(self) -> None:
        resp = compile_rule_preview(_dto(rule=_rule_pred_only_json()))
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["meta"]["profile_effective"], "default")
        self.assertIn("preview", resp)
        self.assertIn("compiled_payload", resp["preview"])
        compiled = resp["preview"]["compiled_payload"]
        self.assertEqual(compiled["rule_id"], "rules.country_rows")
        self.assertEqual(compiled["select_vars"], ["$E", "$C"])
        self.assertEqual(compiled["where"], [["pred", "person:country", ["$E", "$C"]]])


def _dto(
    *,
    rule: dict[str, object],
    strict: bool | None = None,
    profile: dict[str, object] | None = None,
) -> dict[str, object]:
    dto: dict[str, object] = {
        "api_version": "v1",
        "mode": "souffle",
        "rule": rule,
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
