from __future__ import annotations

import unittest

from factpy_kernel.facade.rules_v1 import list_profiles


class FacadeRulesV1ProfilesTests(unittest.TestCase):
    def test_list_profiles_contains_default_and_souffle_strict(self) -> None:
        resp = list_profiles()
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["errors"], [])
        names = {item["name"] for item in resp["profiles"]}
        self.assertIn("default", names)
        self.assertIn("souffle_strict", names)

        strict = next(item for item in resp["profiles"] if item["name"] == "souffle_strict")
        self.assertEqual(strict["capabilities"]["ruleref_policy"], "require_resolved")
        self.assertEqual(strict["capabilities"]["not_body_policy"], "forbid_or")


if __name__ == "__main__":
    unittest.main()
