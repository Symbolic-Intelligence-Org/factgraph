from __future__ import annotations

import unittest

import factgraph.sdk.dsl as dsl
from factgraph.sdk import Entity, Field, Identity, SDKStore


class HardCutPerson(Entity):
    name: str = Identity()
    age: int = Field()


def _store() -> SDKStore:
    return SDKStore([HardCutPerson])


class T5LegacyHardCutTests(unittest.TestCase):
    def test_eval_namespace_exposes_only_t5_evaluate_and_explain(self) -> None:
        graph = _store()

        self.assertTrue(callable(graph.eval.evaluate))
        self.assertTrue(callable(graph.eval.explain))
        for removed in ("run", "accept", "accept_many", "why_not", "why_not_v2"):
            with self.subTest(removed=removed):
                self.assertFalse(hasattr(graph.eval, removed))

    def test_what_if_namespace_is_removed_from_public_sdk(self) -> None:
        graph = _store()

        self.assertFalse(hasattr(graph, "what_if"))

    def test_direct_legacy_shells_are_removed_from_factgraph(self) -> None:
        graph = _store()

        removed = (
            "run",
            "accept",
            "accept_many",
            "check",
            "diagnose",
            "why_not",
            "check_fact_overlay",
            "recheck_proof_frame",
            "check_rule_disable",
            "check_rule_literal_replace",
            "check_rule_add_condition",
        )

        for method_name in removed:
            with self.subTest(method_name=method_name):
                self.assertFalse(hasattr(graph, method_name))

    def test_legacy_dsl_rule_is_internal_only_export(self) -> None:
        self.assertNotIn("Rule", dsl.__all__)
        self.assertTrue(callable(dsl.Rule))


if __name__ == "__main__":
    unittest.main()
