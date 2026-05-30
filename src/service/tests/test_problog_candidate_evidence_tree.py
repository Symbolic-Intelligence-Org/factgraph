from __future__ import annotations

import unittest
from unittest.mock import patch

import factgraph.adapters.problog  # noqa: F401
from factgraph.adapters.problog.provenance import (
    parse_problog_trace,
    problog_trace_to_candidate_evidence_tree,
)
from service.static_ui import render_candidate_evidence_html
from factgraph.core.store._candidate_evidence_tree_narrative import (
    render_candidate_evidence_tree_narrative,
)
from factgraph.core.store._candidate_evidence_tree_nl import (
    render_candidate_evidence_tree_nl_explain,
)
from factgraph.core.store._candidate_evidence_tree_summary import (
    summarize_candidate_evidence_tree_dict,
)
from factgraph.core.store._support import PROBLOG_PROVENANCE_KIND
from factgraph.sdk.compile import compile_schema_from_classes
from factgraph.sdk.schema import Entity, Field, Identity
from factgraph.sdk.store import SDKStore
from service.runtime_v1 import (
    accept_runtime_derivation,
    close_runtime_session,
    evaluate_runtime_derivation,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)


_SUCCESS_TRACE = """
 call query(X1) {0.00000} []
  result query(X1) (c(alice),) {{}} {0.00012} []
 complete query(X1) {0.00013} {0.00013} []
 call c(alice) {0.00019} [at 4:7]
  call a(alice) {0.00026} [at 3:9]
   result a(alice) (alice,) {{}} {0.00038} [at 3:9]
  complete a(alice) {0.00039} {0.00013} []
  call b(alice) {0.00041} [at 3:15]
   result b(alice) (alice,) {{}} {0.00053} [at 3:15]
  complete b(alice) {0.00055} {0.00014} []
  result c(alice) (alice,) {{}} {0.00060} []
 complete c(alice) {0.00061} {0.00042} []

c(alice):\t0.35
""".strip()

_FAIL_TRACE = """
 call query(X1) {0.00000} []
  result query(X1) (c(alice),) {{}} {0.00012} []
 complete query(X1) {0.00013} {0.00013} []
 call c(alice) {0.00019} [at 4:7]
  call missing(alice) {0.00026} [at 3:9]
  fail missing(alice) {0.00039} {0.00013} [at 3:9]
 complete c(alice) {0.00061} {0.00042} []

c(alice):\t0.12
""".strip()


class User(Entity):
    user_id: str = Identity()
    tag_seed: str = Field()
    tag: str = Field()


class ProbLogCandidateEvidenceTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def _open_session(self) -> tuple[str, SDKStore]:
        schema_ir = compile_schema_from_classes([User])
        sdk = SDKStore([User], schema_ir=schema_ir)
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        return open_resp["session"]["session_id"], sdk

    def test_builder_summary_narrative_nl_and_html_for_problog_tree(self) -> None:
        tree = problog_trace_to_candidate_evidence_tree(
            parse_problog_trace(_SUCCESS_TRACE),
            candidate_id="cand_v2:problog",
            candidate_payload={
                "pred_id": "c",
                "terms": [{"kind": "entity_ref", "value": "alice"}],
            },
            support_digest="sha256:problog",
        )

        self.assertEqual(tree["kind"], "candidate_evidence_tree")
        self.assertEqual(tree["support_kind"], PROBLOG_PROVENANCE_KIND)
        self.assertEqual(tree["root"]["engine_meta"]["probability"], 0.35)
        support_section = tree["root"]["children"][0]
        self.assertEqual(support_section["node_kind"], "support_section")
        proof_goal = support_section["children"][0]
        self.assertEqual(proof_goal["node_kind"], "proof_goal")
        self.assertEqual(proof_goal["pred_id"], "c")
        self.assertEqual(proof_goal["goal_args"], ["alice"])
        proof_leaves = proof_goal["children"]
        self.assertEqual([node["node_kind"] for node in proof_leaves], ["proof_leaf", "proof_leaf"])
        self.assertTrue(all("asrt_id" not in node for node in proof_leaves))

        summary = summarize_candidate_evidence_tree_dict(tree)
        self.assertEqual(summary["node_count_by_role"]["proof"], 3)
        self.assertEqual(summary["proof_goal_count"], 1)
        self.assertEqual(summary["proof_leaf_count"], 2)
        self.assertEqual(summary["recursive_depth"], 1)
        self.assertEqual(summary["problog_probability"], 0.35)

        narrative = render_candidate_evidence_tree_narrative(summary, locale="en")
        self.assertEqual(
            narrative["evidence_lines"],
            ["ProbLog proof tree: 1 intermediate goals, 2 leaf facts."],
        )
        self.assertEqual(narrative["rule_chain_lines"], ["Proof depth: 1."])
        self.assertEqual(narrative["probability_lines"], ["ProbLog probability: 0.35."])

        explain_nl = render_candidate_evidence_tree_nl_explain(summary, narrative, locale="en")
        self.assertEqual(explain_nl["paragraphs"][4], "Probability assessment: ProbLog probability: 0.35.")

        html = render_candidate_evidence_html(tree, narrative=narrative)
        self.assertIn("Proof Goal", html)
        self.assertIn("Proof Leaf", html)
        self.assertIn("ProbLog probability: 0.35.", html)
        self.assertNotIn("View assertion", html)

    def test_builder_maps_failed_leaf_to_non_fact_check(self) -> None:
        tree = problog_trace_to_candidate_evidence_tree(
            parse_problog_trace(_FAIL_TRACE),
            candidate_id="cand_v2:fail",
            candidate_payload={
                "pred_id": "c",
                "terms": [{"kind": "entity_ref", "value": "alice"}],
            },
            support_digest="sha256:fail",
        )

        proof_goal = tree["root"]["children"][0]["children"][0]
        self.assertEqual(proof_goal["node_kind"], "proof_goal")
        failed_child = proof_goal["children"][0]
        self.assertEqual(failed_child["node_kind"], "non_fact_check")
        self.assertEqual(failed_child["status"], "fail")
        self.assertEqual(failed_child["check_kind"], "missing")

    @patch("factgraph.adapters.problog.engine_eval.run_problog")
    def test_runtime_evaluate_returns_result_envelope_and_accept_is_removed(self, mock_run) -> None:
        session_id, sdk = self._open_session()
        alice_ref = sdk.entities.ref(User, user_id="Alice")
        mock_run.return_value = "\n".join(
            [
                " call query(X1,X2) {0.00000} []",
                f'  result query(X1,X2) ("vip","{alice_ref}") {{{{}}}} {{0.00012}} []',
                " complete query(X1,X2) {0.00013} {0.00013} []",
                f' call answer("vip","{alice_ref}") {{0.00019}} [at 4:7]',
                f'  call user__tag_seed("vip","{alice_ref}") {{0.00026}} [at 3:9]',
                f'   result user__tag_seed("vip","{alice_ref}") ("vip","{alice_ref}") {{{{}}}} {{0.00038}} [at 3:9]',
                f'  complete user__tag_seed("vip","{alice_ref}") {{0.00039}} {{0.00013}} []',
                f'  result answer("vip","{alice_ref}") ("vip","{alice_ref}") {{{{}}}} {{0.00060}} []',
                f' complete answer("vip","{alice_ref}") {{0.00061}} {{0.00042}} []',
                "",
                f'answer("vip","{alice_ref}"):\t0.42',
            ]
        )
        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag_seed",
                    "e_ref": alice_ref,
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])

            eval_resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "problog",
                    "inference": {
                        "derivation_id": "drv.problog_runtime_tree",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [["pred", "user:tag_seed", ["$u", "$tag"]]],
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            evaluation = eval_resp["evaluation"]
            self.assertRegex(evaluation["result_id"], r"^evalr_v1:[0-9a-f]{64}$")
            self.assertRegex(evaluation["result_digest"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(evaluation["engine"], "problog")
            self.assertNotIn("candidates", evaluation)
            row = dict(evaluation["rows"][0])
            self.assertEqual(row["raw_kind"], "probabilistic")
            self.assertEqual(row["bound"], [0.42, 0.42])
            self.assertRegex(row["evidence_ref"]["ref_id"], r"^evref_v1:[0-9a-f]{64}$")

            accept_resp = accept_runtime_derivation(
                session_id,
                {
                    "candidate": {"candidate_id": "cand_v2:legacy"},
                },
            )
            self.assertFalse(accept_resp["ok"])
            self.assertEqual(accept_resp["errors"][0]["kind"], "removed")
        finally:
            close_runtime_session(session_id)


if __name__ == "__main__":
    unittest.main()
