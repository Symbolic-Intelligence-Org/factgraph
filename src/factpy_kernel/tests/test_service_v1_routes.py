from __future__ import annotations

import unittest

from factpy_kernel.facade.rules_v1 import compile_rule_preview, list_profiles, validate_rule

try:
    from fastapi.testclient import TestClient

    from factpy_kernel.service.app_v1 import app

    _FASTAPI_AVAILABLE = True
except Exception:  # pragma: no cover - service extra not installed in core-only environments
    TestClient = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "service extra dependencies are not installed")
class ServiceV1RoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)  # type: ignore[arg-type]

    def test_validate_route_ok_matches_facade(self) -> None:
        dto = _dto(rule=_rule_pred_only_json())
        resp = self.client.post("/v1/rules/validate", json=dto)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), validate_rule(dto))

    def test_validate_route_error_matches_facade(self) -> None:
        dto = _dto(strict=True, rule=_rule_ruleref_json())
        resp = self.client.post("/v1/rules/validate", json=dto)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body, validate_rule(dto))
        self.assertFalse(body["ok"])
        self.assertEqual(body["errors"][0]["kind"], "rule_ast_validate")

    def test_compile_preview_route_matches_facade(self) -> None:
        dto = _dto(rule=_rule_pred_only_json())
        resp = self.client.post("/v1/rules/compile-preview", json=dto)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), compile_rule_preview(dto))

    def test_profiles_route_matches_facade_and_contains_strict(self) -> None:
        resp = self.client.get("/v1/profiles")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body, list_profiles())
        names = {item["name"] for item in body["profiles"]}
        self.assertIn("souffle_strict", names)


def _dto(*, rule: dict[str, object], strict: bool | None = None) -> dict[str, object]:
    dto: dict[str, object] = {
        "api_version": "v1",
        "mode": "souffle",
        "rule": rule,
    }
    if strict is not None:
        dto["strict"] = strict
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
