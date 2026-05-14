"""Layer 1 agent tool adapter tests."""

from __future__ import annotations

import unittest

from agent.tools._runtime_api import LocalRuntimeAPI
from agent.tools.explain import ExplainTools
from agent.tools.kg_read import KGReadTools
from factgraph.sdk import SDKStore
from service.runtime_v1 import (
    close_runtime_session,
    evaluate_runtime_derivation,
    open_runtime_session,
    register_ephemeral_rule,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)
from factgraph.tests._test_helpers import User, _schema_ir, _seed_users_for_syntax_matrix


def _open_session() -> str:
    resp = open_runtime_session({"schema_ir": _schema_ir()})
    assert resp["ok"], resp
    return resp["session"]["session_id"]


def _register_ephemeral_user_tag_rule(
    session_id: str,
    *,
    rule_id: str = "q.user_tag_rows",
    version: str = "1.0.0",
) -> dict:
    return register_ephemeral_rule(
        session_id,
        {
            "rule": {
                "rule_id": rule_id,
                "version": version,
                "select": ["$u", "$tag"],
                "where": [["pred", "user:tag", ["$u", "$tag"]]],
                "expose": True,
            }
        },
    )


def _native_derivation_dto(*, rule_id: str = "q.user_tag_rows", version: str = "1.0.0") -> dict:
    return {
        "inference": {
            "derivation_id": "drv.runtime.user_tag_copy",
            "version": "1.0.0",
            "target": "user:tag",
            "head_vars": ["$u", "$tag"],
            "where": [
                ["ruleref", rule_id, version, ["$u", "$tag"]],
                ["eq", "$tag", "vip"],
            ],
        },
        "engine": "native",
    }


class _FakeTimelineRuntimeAPI(LocalRuntimeAPI):
    def explain_summary(self, session_id: str, dto: dict[str, object]) -> dict[str, object]:
        return {
            "ok": True,
            "errors": [],
            "meta": {"candidate_id": dto["id"]},
            "kind": "candidate_provenance_timeline_summary",
            "summary": {
                "explain_kind": "timeline",
                "timesteps": 3,
                "chain_count": 2,
                "total_event_count": 5,
            },
        }

    def explain_steps(self, session_id: str, dto: dict[str, object]) -> dict[str, object]:
        return {
            "ok": True,
            "errors": [],
            "meta": {"candidate_id": dto["id"]},
            "kind": "candidate_evidence_steps",
            "candidate_id": dto["id"],
            "engine": "pyreason_provenance_v1",
            "steps": [
                {
                    "step_num": 1,
                    "step_kind": "bound_seed",
                    "description": "t=0: NODE.signal initialized",
                    "node_ref": "node/NODE/signal",
                    "detail": {"depth": 0, "time": 0},
                }
            ],
        }

    def explain_tree(self, session_id: str, dto: dict[str, object]) -> dict[str, object]:
        return {
            "ok": False,
            "errors": [
                {
                    "kind": "runtime_explain_not_supported",
                    "path": "$.id",
                    "details": {"message": "tree not supported"},
                }
            ],
            "meta": {},
        }

    def explain_timeline(self, session_id: str, dto: dict[str, object]) -> dict[str, object]:
        return {
            "ok": True,
            "errors": [],
            "meta": {"candidate_id": dto["id"]},
            "kind": "candidate_provenance_timeline",
            "timeline": {
                "kind": "candidate_provenance_timeline",
                "candidate_id": dto["id"],
                "engine": "pyreason",
                "timesteps": 3,
                "chains": [{"component": "NODE"}],
            },
        }


class AgentLayer1ToolTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.session_id = _open_session()
        self.runtime_api = LocalRuntimeAPI()
        self.kg = KGReadTools(runtime_api=self.runtime_api)
        self.explain = ExplainTools(runtime_api=self.runtime_api)

        self.sdk = SDKStore([User])
        self.refs = _seed_users_for_syntax_matrix(self.sdk)
        self._write_rows()

    def tearDown(self) -> None:
        close_runtime_session(self.session_id)
        reset_runtime_sessions_for_tests()

    def _write_rows(self) -> None:
        for pred_id, e_ref, rest_terms, meta in (
            ("user:tag", self.refs["u1"], [["string", "vip"]], {"source": "manual"}),
            ("user:tag", self.refs["u2"], [["string", "staff"]], None),
            ("user:name", self.refs["u1"], [["string", "Alice"]], None),
            ("user:name", self.refs["u2"], [["string", "Bob"]], None),
        ):
            resp = write_runtime_fact(
                self.session_id,
                {
                    "pred_id": pred_id,
                    "e_ref": e_ref,
                    "rest_terms": rest_terms,
                    "meta": meta,
                },
                kind="add",
            )
            self.assertTrue(resp["ok"], resp)

    def _evaluate_candidate(self) -> str:
        reg = _register_ephemeral_user_tag_rule(self.session_id)
        self.assertTrue(reg["ok"], reg)
        eval_resp = evaluate_runtime_derivation(self.session_id, _native_derivation_dto())
        self.assertTrue(eval_resp["ok"], eval_resp)
        return eval_resp["evaluation"]["candidates"][0]["candidate_id"]

    def test_get_schema_summary_returns_entities_and_predicates(self) -> None:
        summary = self.kg.get_schema_summary(self.session_id)
        self.assertEqual(summary["entity_types"][0]["entity_type"], "User")
        pred_ids = {p["pred_id"] for p in summary["predicates"]}
        self.assertIn("user:name", pred_ids)
        self.assertIn("user:tag", pred_ids)

    def test_query_claims_returns_meta_and_revocation_flag(self) -> None:
        claims = self.kg.query_claims(self.session_id, pred_id="user:tag", e_ref=self.refs["u1"])
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].meta["source"], "manual")
        self.assertFalse(claims[0].is_revoked)

    def test_get_entity_snapshot_aggregates_claims(self) -> None:
        snapshot = self.kg.get_entity_snapshot(
            self.session_id,
            entity_type="User",
            identity={"user_id": "u-syntax-1", "locale": "zh"},
        )
        self.assertEqual(snapshot.e_ref, self.refs["u1"])
        pred_ids = {claim.pred_id for claim in snapshot.claims}
        self.assertIn("user:name", pred_ids)
        self.assertIn("user:tag", pred_ids)

    def test_list_rules_returns_inventory_and_optional_spec(self) -> None:
        reg = _register_ephemeral_user_tag_rule(self.session_id, rule_id="q.spec_test")
        self.assertTrue(reg["ok"], reg)
        rules = self.kg.list_rules(self.session_id)
        self.assertEqual(rules[0].source, "ephemeral")
        self.assertIsNone(rules[0].spec)

        rules_with_spec = self.kg.list_rules(self.session_id, include_spec=True)
        self.assertEqual(rules_with_spec[0].spec["expose"], True)
        self.assertIn("where", rules_with_spec[0].spec)

    def test_list_candidates_reads_runtime_inventory(self) -> None:
        candidate_id = self._evaluate_candidate()
        candidates = self.kg.list_candidates(self.session_id)
        ids = {item.candidate_id for item in candidates}
        self.assertIn(candidate_id, ids)

    def test_explain_tools_native_summary_steps_tree(self) -> None:
        candidate_id = self._evaluate_candidate()
        summary = self.explain.get_summary(self.session_id, candidate_id)
        steps = self.explain.get_steps(self.session_id, candidate_id)
        tree = self.explain.get_tree(self.session_id, candidate_id)
        timeline = self.explain.get_timeline(self.session_id, candidate_id)

        self.assertEqual(summary.kind, "tree_summary")
        self.assertEqual(summary.summary["candidate_id"], candidate_id)
        self.assertTrue(steps)
        self.assertGreaterEqual(steps[0].step_num, 1)
        self.assertIsNotNone(tree)
        self.assertIsNone(timeline)

    def test_explain_tools_timeline_path_with_stub_runtime(self) -> None:
        tools = ExplainTools(runtime_api=_FakeTimelineRuntimeAPI())
        summary = tools.get_summary("rt_fake", "cand_fake")
        steps = tools.get_steps("rt_fake", "cand_fake")
        tree = tools.get_tree("rt_fake", "cand_fake")
        timeline = tools.get_timeline("rt_fake", "cand_fake")

        self.assertEqual(summary.kind, "timeline_summary")
        self.assertEqual(steps[0].step_kind, "bound_seed")
        self.assertIsNone(tree)
        self.assertIsNotNone(timeline)
        self.assertEqual(timeline.timeline["engine"], "pyreason")


if __name__ == "__main__":
    unittest.main()
