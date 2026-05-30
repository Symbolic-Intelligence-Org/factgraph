from __future__ import annotations

import unittest

import factgraph.sdk.dsl as dsl
from factgraph.sdk import Entity, Field, Identity, SDKStore
from factgraph.sdk.errors import SDKStoreError


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

    def test_direct_legacy_shells_reject_with_t5_guidance(self) -> None:
        graph = _store()
        cases = (
            ("fg.run", lambda: graph.run(object())),
            ("fg.accept", lambda: graph.accept(object())),
            ("fg.accept_many", lambda: graph.accept_many([])),
            ("fg.check", lambda: graph.check(object(), {})),
            ("fg.diagnose", lambda: graph.diagnose(object(), {})),
            ("fg.why_not", lambda: graph.why_not(object(), [])),
            ("fg.check_fact_overlay", lambda: graph.check_fact_overlay(object(), {}, object())),
            ("fg.recheck_proof_frame", lambda: graph.recheck_proof_frame(object(), object())),
            ("fg.check_rule_disable", lambda: graph.check_rule_disable(object(), object(), branch_index=0, atom_index=0)),
            (
                "fg.check_rule_literal_replace",
                lambda: graph.check_rule_literal_replace(
                    object(),
                    object(),
                    branch_index=0,
                    atom_index=0,
                    literal_path=object(),
                    old_literal=object(),
                    new_literal=object(),
                ),
            ),
            (
                "fg.check_rule_add_condition",
                lambda: graph.check_rule_add_condition(
                    object(),
                    object(),
                    branch_index=0,
                    added_atom=object(),
                ),
            ),
        )

        for method_name, call in cases:
            with self.subTest(method_name=method_name):
                with self.assertRaises(SDKStoreError) as ctx:
                    call()
                message = str(ctx.exception)
                self.assertIn(method_name, message)
                self.assertIn("fg.eval.evaluate", message)
                self.assertIn("row.explain", message)

    def test_legacy_dsl_rule_is_internal_only_export(self) -> None:
        self.assertNotIn("Rule", dsl.__all__)
        self.assertTrue(callable(dsl.Rule))


if __name__ == "__main__":
    unittest.main()
