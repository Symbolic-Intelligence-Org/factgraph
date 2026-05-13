"""Layer 4B conservative engine routing tests."""

from __future__ import annotations

import unittest

from factpy.agent import (
    AgentScope,
    AgentSession,
    ConsistencyWarning,
    EngineRoutingAdvisor,
    EngineRoutingHint,
    RuleSpec,
    RuntimeBootstrapSpec,
)
from factpy.tests._test_helpers import _schema_ir


class _FakeRoutingRuntimeAPI:
    def __init__(self) -> None:
        self.ephemeral_rules = [{"rule_id": "q.ephemeral", "version": "v1"}]
        self.candidates = []

    def list_ephemeral_rules(self, session_id: str) -> dict[str, object]:
        return {
            "ok": True,
            "errors": [],
            "result": {"ephemeral_rules": list(self.ephemeral_rules), "total": len(self.ephemeral_rules)},
        }

    def list_candidates(
        self,
        session_id: str,
        *,
        pred_id_filter: str | None = None,
    ) -> dict[str, object]:
        candidates = [
            item
            for item in self.candidates
            if pred_id_filter is None or item.get("pred_id") == pred_id_filter
        ]
        return {
            "ok": True,
            "errors": [],
            "result": {"candidates": candidates, "total": len(candidates)},
        }


def _rule_spec(
    *,
    rule_id: str = "q.rule",
    version: str = "v1",
    tags: list[str] | None = None,
    routing_hint: EngineRoutingHint | None = None,
) -> RuleSpec:
    return RuleSpec(
        rule_id=rule_id,
        version=version,
        select_vars=["$u", "$tag"],
        where=[["pred", "user:tag", ["$u", "$tag"]]],
        expose=True,
        tags=tags,
        routing_hint=routing_hint,
    )


class AgentLayer4BRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = _FakeRoutingRuntimeAPI()
        self.session = AgentSession(scope=AgentScope(agent_id="agent-l4b-routing"))
        self.session.bind_runtime_session(
            "rt_l4b",
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto({"schema_ir": _schema_ir()}),
            burr_db_path="/tmp/agent-l4b-routing.sqlite3",
        )
        self.advisor = EngineRoutingAdvisor(runtime_api=self.runtime, session=self.session)

    def test_recommend_for_rule_prefers_explicit_hint(self) -> None:
        hint = self.advisor.recommend_for_rule(
            _rule_spec(
                routing_hint=EngineRoutingHint(
                    suggested_engine="pyreason",
                    reason="user selected pyreason",
                    source="explicit",
                    overrideable=False,
                    confidence=1.0,
                )
            )
        )
        self.assertEqual(hint.suggested_engine, "pyreason")
        self.assertEqual(hint.source, "explicit")
        self.assertFalse(hint.overrideable)

    def test_recommend_for_rule_extracts_engine_tag(self) -> None:
        hint = self.advisor.recommend_for_rule(_rule_spec(tags=["engine:problog"]))
        self.assertEqual(hint.suggested_engine, "problog")
        self.assertEqual(hint.source, "tag")
        self.assertEqual(hint.reason, "tag engine:problog")

    def test_recommend_for_rule_marks_existing_ephemeral_as_native_only(self) -> None:
        hint = self.advisor.recommend_for_rule(_rule_spec(rule_id="q.ephemeral"))
        self.assertEqual(hint.suggested_engine, "native")
        self.assertEqual(hint.source, "heuristic")
        self.assertFalse(hint.overrideable)
        self.assertEqual(hint.confidence, 1.0)

    def test_recommend_for_evaluate_prefers_explicit_mode(self) -> None:
        hint = self.advisor.recommend_for_evaluate(
            {
                "derivation_id": "drv.rule",
                "version": "v1",
                "target": "user:tag",
                "head_vars": ["$u", "$tag"],
                "where": [["pred", "user:tag", ["$u", "$tag"]]],
                "mode": "souffle",
            }
        )
        self.assertEqual(hint.suggested_engine, "souffle")
        self.assertEqual(hint.source, "explicit")

    def test_recommend_for_evaluate_detects_ephemeral_ruleref(self) -> None:
        hint = self.advisor.recommend_for_evaluate(
            {
                "derivation_id": "drv.rule",
                "version": "v1",
                "target": "user:tag",
                "head_vars": ["$u", "$tag"],
                "where": [["ruleref", "q.ephemeral", "v1", ["$u", "$tag"]]],
            }
        )
        self.assertEqual(hint.suggested_engine, "native")
        self.assertFalse(hint.overrideable)
        self.assertEqual(hint.confidence, 1.0)

    def test_check_consistency_warns_on_mismatched_history(self) -> None:
        self.runtime.candidates = [
            {
                "candidate_id": "cand_1",
                "pred_id": "user:tag",
                "support_kind": "native_binding_v1",
                "confidence_kind": "none",
            }
        ]
        warning = self.advisor.check_consistency("user:tag", "problog")
        self.assertIsInstance(warning, ConsistencyWarning)
        assert warning is not None
        self.assertEqual(warning.historical_engine, "native")
        self.assertEqual(warning.suggested_engine, "problog")

    def test_check_consistency_ignores_engine_without_witness(self) -> None:
        self.runtime.candidates = [
            {
                "candidate_id": "cand_1",
                "pred_id": "user:tag",
                "support_kind": "engine_no_witness_v1",
                "confidence_kind": "none",
            }
        ]
        warning = self.advisor.check_consistency("user:tag", "native")
        self.assertIsNone(warning)


if __name__ == "__main__":
    unittest.main()
