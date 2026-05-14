"""Layer 2 read-first workflow tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agent import (
    AgentCheckpointStore,
    AgentScope,
    AgentSession,
    CandidatePayloadCache,
    DraftManager,
    EvaluateRequest,
    EvaluateTools,
    ReadReviewOrchestrator,
    RuntimeBootstrapSpec,
    build_layer2_tool_registry,
)
from agent.tools._runtime_api import LocalRuntimeAPI
from agent.tools.explain import ExplainTools
from agent.tools.kg_read import KGReadTools
from service.runtime_v1 import (
    close_runtime_session,
    get_runtime_session,
    open_runtime_session,
    register_ephemeral_rule,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)
from factgraph.tests._test_helpers import User, _schema_ir, _seed_users_for_syntax_matrix
from factgraph.sdk import SDKStore


def _open_session(open_dto: dict[str, object]) -> str:
    resp = open_runtime_session(open_dto)
    assert resp["ok"], resp
    return resp["session"]["session_id"]


def _register_ephemeral_user_tag_rule(session_id: str, *, rule_id: str = "q.user_tag_rows") -> None:
    resp = register_ephemeral_rule(
        session_id,
        {
            "rule": {
                "rule_id": rule_id,
                "version": "1.0.0",
                "select": ["$u", "$tag"],
                "where": [["pred", "user:tag", ["$u", "$tag"]]],
                "expose": True,
            }
        },
    )
    assert resp["ok"], resp


def _native_eval_request(*, rule_id: str = "q.user_tag_rows") -> EvaluateRequest:
    return EvaluateRequest(
        inference={
            "derivation_id": "drv.runtime.user_tag_copy",
            "version": "1.0.0",
            "target": "user:tag",
            "head_vars": ["$u", "$tag"],
            "where": [
                ["ruleref", rule_id, "1.0.0", ["$u", "$tag"]],
                ["eq", "$tag", "vip"],
            ],
        },
        engine="native",
    )


class AgentLayer2WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_layer2.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.schema_ir = _schema_ir()
        self.open_dto = {"schema_ir": self.schema_ir, "ledger_path": self.ledger_path}
        self.runtime_session_id = _open_session(self.open_dto)

        self.agent_session = AgentSession(scope=AgentScope(agent_id="agent-layer2"))
        self.agent_session.bind_runtime_session(
            self.runtime_session_id,
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto(self.open_dto),
            burr_db_path=str(self.db_path),
        )
        self.draft_manager = DraftManager()
        self.cache = CandidatePayloadCache(self.db_path)
        self.checkpoint = AgentCheckpointStore(self.db_path)
        self.runtime_api = LocalRuntimeAPI()
        self.kg = KGReadTools(runtime_api=self.runtime_api)
        self.explain = ExplainTools(runtime_api=self.runtime_api)
        self.evaluate_tools = EvaluateTools(
            runtime_api=self.runtime_api,
            candidate_cache=self.cache,
            explain_tools=self.explain,
            session=self.agent_session,
        )
        self.orchestrator = ReadReviewOrchestrator(
            session=self.agent_session,
            draft_manager=self.draft_manager,
            kg_read_tools=self.kg,
            explain_tools=self.explain,
            evaluate_tools=self.evaluate_tools,
            candidate_cache=self.cache,
            checkpoint_store=self.checkpoint,
        )

        self.sdk = SDKStore([User])
        self.refs = _seed_users_for_syntax_matrix(self.sdk)
        self._write_rows()
        _register_ephemeral_user_tag_rule(self.runtime_session_id)

    def tearDown(self) -> None:
        self.cache.close()
        self.checkpoint.close()
        if get_runtime_session(self.runtime_session_id).get("ok") is True:
            close_runtime_session(self.runtime_session_id)
        reset_runtime_sessions_for_tests()

    def _write_rows(self) -> None:
        for pred_id, e_ref, rest_terms, meta in (
            ("user:tag", self.refs["u1"], [["string", "vip"]], {"source": "manual"}),
            ("user:tag", self.refs["u2"], [["string", "staff"]], None),
            ("user:name", self.refs["u1"], [["string", "Alice"]], None),
            ("user:name", self.refs["u2"], [["string", "Bob"]], None),
        ):
            resp = write_runtime_fact(
                self.runtime_session_id,
                {
                    "pred_id": pred_id,
                    "e_ref": e_ref,
                    "rest_terms": rest_terms,
                    "meta": meta,
                },
                kind="add",
            )
            self.assertTrue(resp["ok"], resp)

    def test_evaluate_tools_evaluate_caches_candidates(self) -> None:
        result = self.evaluate_tools.evaluate(_native_eval_request())
        self.assertEqual(result.mode, "native")
        self.assertEqual(result.candidate_count, 1)
        self.assertFalse(result.truncated)
        cached = self.cache.lookup_active(self.runtime_session_id, result.candidates[0]["candidate_id"])
        self.assertIsNotNone(cached)
        self.assertEqual(cached["candidate_id"], result.candidates[0]["candidate_id"])

    def test_review_candidate_returns_summary_and_steps_for_active_cache(self) -> None:
        result = self.evaluate_tools.evaluate(_native_eval_request())
        candidate_id = result.candidates[0]["candidate_id"]
        review = self.evaluate_tools.review_candidate(candidate_id)
        self.assertEqual(review.cache_status, "active")
        self.assertEqual(review.candidate_id, candidate_id)
        self.assertEqual(review.pred_id, "user:tag")
        self.assertIsNotNone(review.summary)
        self.assertIsNotNone(review.steps)
        self.assertTrue(review.steps)

    def test_review_candidate_returns_stale_outcome_after_runtime_id_changes(self) -> None:
        result = self.evaluate_tools.evaluate(_native_eval_request())
        candidate_id = result.candidates[0]["candidate_id"]
        self.agent_session.runtime_session_id = "rt_restarted"
        review = self.evaluate_tools.review_candidate(candidate_id)
        self.assertEqual(review.status, "stale")
        self.assertEqual(review.candidate_id, candidate_id)
        self.assertEqual(review.action_required, "re-evaluate")
        self.assertEqual(review.stale_runtime_session_id, self.runtime_session_id)

    def test_accept_candidate_returns_result_for_active_cache(self) -> None:
        result = self.evaluate_tools.evaluate(_native_eval_request())
        candidate_id = result.candidates[0]["candidate_id"]
        accepted = self.evaluate_tools.accept_candidate(candidate_id, dry_run=True)
        self.assertEqual(accepted.candidate_id, candidate_id)
        self.assertTrue(accepted.dry_run)
        self.assertEqual(accepted.accept_detail["accepted_count"], 1)
        self.assertIn("written_assertions", accepted.accept_detail)

    def test_accept_candidate_returns_missing_outcome_when_cache_absent(self) -> None:
        outcome = self.evaluate_tools.accept_candidate("cand_missing", dry_run=True)
        self.assertEqual(outcome.status, "missing")
        self.assertEqual(outcome.action_required, "re-evaluate")

    def test_orchestrator_evaluate_and_accept_checkpoint(self) -> None:
        result = self.orchestrator.evaluate(_native_eval_request())
        restored_session, _, _ = self.checkpoint.load(self.agent_session.agent_session_id)
        self.assertEqual(restored_session.runtime_session_id, self.runtime_session_id)

        candidate_id = result.candidates[0]["candidate_id"]
        accepted = self.orchestrator.accept(candidate_id, dry_run=True)
        self.assertEqual(accepted.candidate_id, candidate_id)
        restored_session_2, _, _ = self.checkpoint.load(self.agent_session.agent_session_id)
        self.assertEqual(restored_session_2.runtime_session_id, self.runtime_session_id)

    def test_orchestrator_read_wrappers_and_health(self) -> None:
        schema = self.orchestrator.get_schema()
        self.assertIn("predicates", schema)
        claims = self.orchestrator.query_claims("user:tag", self.refs["u1"])
        self.assertEqual(len(claims), 1)
        entity = self.orchestrator.get_entity(
            "User",
            {"user_id": "u-syntax-1", "locale": "zh"},
        )
        self.assertEqual(entity.e_ref, self.refs["u1"])
        self.assertEqual(self.orchestrator.check_session_health(), "healthy")

        close_runtime_session(self.runtime_session_id)
        self.assertEqual(self.orchestrator.check_session_health(), "runtime_lost")
        self.agent_session.runtime_session_id = self.runtime_session_id

    def test_orchestrator_get_stale_candidates_and_tool_registry(self) -> None:
        result = self.orchestrator.evaluate(_native_eval_request())
        candidate_id = result.candidates[0]["candidate_id"]
        self.agent_session.runtime_session_id = "rt_restarted"
        stale = self.orchestrator.get_stale_candidates()
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["candidate_id"], candidate_id)

        tool_registry = build_layer2_tool_registry(orchestrator=self.orchestrator)
        self.assertEqual(len(tool_registry), 16)
        self.assertIn("evaluate", tool_registry)
        self.assertIn("accept_candidate", tool_registry)
        self.assertIn("get_steps", tool_registry)


if __name__ == "__main__":
    unittest.main()
