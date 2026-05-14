"""Layer 1 agent control-plane model tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agent import (
    AgentCheckpointStore,
    AgentRecoveryError,
    AgentScope,
    AgentScopeGuard,
    AgentScopeViolation,
    AgentSession,
    BundleManager,
    CandidatePayloadCache,
    DraftManager,
    FactDraft,
    LAYER1_STATE_SEQUENCE,
    RuntimeBootstrapSpec,
    build_layer1_agent_skeleton,
    recover_agent_session,
)
from agent.tools.explain import ExplainTools
from agent.tools.kg_read import KGReadTools
from agent.tools._runtime_api import LocalRuntimeAPI
from service.runtime_v1 import (
    close_runtime_session,
    get_runtime_session,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
)
from factgraph.tests._test_helpers import _schema_ir


class AgentLayer1ModelTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_state.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.schema_ir = _schema_ir()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def test_runtime_bootstrap_spec_roundtrip(self) -> None:
        open_dto = {"schema_ir": self.schema_ir, "ledger_path": self.ledger_path}
        spec = RuntimeBootstrapSpec.from_open_dto(open_dto)
        restored = RuntimeBootstrapSpec.from_checkpoint(spec.to_checkpoint())
        self.assertEqual(restored.schema_ir_digest, spec.schema_ir_digest)
        self.assertEqual(restored.open_dto, open_dto)

    def test_agent_session_checkpoint_roundtrip(self) -> None:
        session = AgentSession(scope=AgentScope(agent_id="agent-test"))
        spec = RuntimeBootstrapSpec.from_open_dto({"schema_ir": self.schema_ir})
        session.bind_runtime_session("rt_123", bootstrap_spec=spec, burr_db_path=str(self.db_path))

        restored = AgentSession.from_checkpoint(session.to_checkpoint())
        self.assertEqual(restored.agent_session_id, session.agent_session_id)
        self.assertEqual(restored.runtime_session_id, "rt_123")
        self.assertEqual(restored.status, "active")
        self.assertEqual(restored.burr_db_path, str(self.db_path))
        self.assertEqual(restored.bootstrap_spec.open_dto, {"schema_ir": self.schema_ir})

    def test_scope_guard_enforces_pred_and_source(self) -> None:
        scope = AgentScope(
            allowed_entity_types=frozenset({"User"}),
            allowed_pred_ids=frozenset({"user:tag"}),
            require_source=True,
            min_confidence=0.5,
            agent_id="agent-test",
        )
        draft = FactDraft(
            draft_id="draft_1",
            entity_type="User",
            entity_identity={"user_id": "u1", "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            confidence=0.8,
            source="manual",
            source_loc=None,
            note=None,
            created_at=1,
            status="pending",
            session_id="agent_1",
            conversation_turn=1,
        )
        AgentScopeGuard().validate(draft, scope)

        with self.assertRaises(AgentScopeViolation):
            AgentScopeGuard().validate(
                FactDraft(
                    **{
                        **draft.to_checkpoint(),
                        "pred_id": "user:name",
                    }
                ),
                scope,
            )

        with self.assertRaises(AgentScopeViolation):
            AgentScopeGuard().validate(
                FactDraft(
                    **{
                        **draft.to_checkpoint(),
                        "source": None,
                    }
                ),
                scope,
            )

    def test_draft_manager_lifecycle_and_restore(self) -> None:
        manager = DraftManager()
        draft = manager.create_draft(
            "agent_1",
            entity_type="User",
            entity_identity={"user_id": "u1", "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            confidence=0.9,
            source="manual",
            conversation_turn=1,
        )
        manager.update_draft(draft.draft_id, note="updated")
        manager.confirm_draft(draft.draft_id)
        manager.mark_committed(draft.draft_id, "asrt_123")

        restored = DraftManager.from_checkpoint(manager.to_checkpoint())
        restored_draft = restored.get_draft(draft.draft_id)
        self.assertIsNotNone(restored_draft)
        self.assertEqual(restored_draft.status, "committed")
        self.assertEqual(restored_draft.assertion_id, "asrt_123")

    def test_candidate_payload_cache_active_stale_and_evict(self) -> None:
        cache = CandidatePayloadCache(self.db_path)
        self.addCleanup(cache.close)
        cache.store("agent_1", "rt_old", [{"candidate_id": "cand_1", "value": 1}])
        cache.store("agent_1", "rt_new", [{"candidate_id": "cand_2", "value": 2}])

        self.assertEqual(cache.lookup_active("rt_new", "cand_2")["value"], 2)
        stale = cache.list_stale("agent_1", "rt_new")
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["candidate_id"], "cand_1")
        self.assertEqual(cache.evict_agent_session("agent_1"), 2)
        self.assertIsNone(cache.lookup_active("rt_new", "cand_2"))

    def test_checkpoint_store_save_and_load(self) -> None:
        store = AgentCheckpointStore(self.db_path)
        self.addCleanup(store.close)
        manager = DraftManager()
        manager.create_draft(
            "agent_1",
            entity_type="User",
            entity_identity={"user_id": "u1", "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            confidence=0.9,
            source="manual",
        )
        session = AgentSession(scope=AgentScope(agent_id="agent-test"))
        session.bind_runtime_session(
            "rt_123",
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto({"schema_ir": self.schema_ir}),
            burr_db_path=str(self.db_path),
        )
        store.save(session, manager)
        loaded_session, loaded_manager, loaded_bundles = store.load(session.agent_session_id)
        self.assertEqual(loaded_session.runtime_session_id, "rt_123")
        self.assertEqual(len(loaded_manager.list_drafts("agent_1")), 1)
        self.assertEqual(loaded_bundles.list_bundles(), [])

    def test_recover_agent_session_warm_reconnect(self) -> None:
        open_dto = {"schema_ir": self.schema_ir, "ledger_path": self.ledger_path}
        open_resp = open_runtime_session(open_dto)
        self.assertTrue(open_resp["ok"], open_resp)
        runtime_session_id = open_resp["session"]["session_id"]

        session = AgentSession(scope=AgentScope(agent_id="agent-test"))
        session.bind_runtime_session(
            runtime_session_id,
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto(open_dto),
            burr_db_path=str(self.db_path),
        )
        manager = DraftManager()
        manager.create_draft(
            session.agent_session_id,
            entity_type="User",
            entity_identity={"user_id": "u1", "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            confidence=0.9,
            source="manual",
        )
        checkpoint = AgentCheckpointStore(self.db_path)
        checkpoint.save(session, manager)
        checkpoint.close()

        cache = CandidatePayloadCache(self.db_path)
        cache.store(session.agent_session_id, runtime_session_id, [{"candidate_id": "cand_1", "value": 1}])
        cache.close()

        result = recover_agent_session(session.agent_session_id, db_path=self.db_path)
        self.addCleanup(result.candidate_cache.close)
        self.assertEqual(result.mode, "warm")
        self.assertEqual(result.session.runtime_session_id, runtime_session_id)
        self.assertEqual(result.candidate_cache.lookup_active(runtime_session_id, "cand_1")["value"], 1)
        self.assertEqual(result.stale_candidates, [])
        self.assertEqual(result.bundle_manager.list_bundles(), [])
        close_runtime_session(runtime_session_id)

    def test_recover_agent_session_cold_restart_marks_stale(self) -> None:
        open_dto = {"schema_ir": self.schema_ir, "ledger_path": self.ledger_path}
        open_resp = open_runtime_session(open_dto)
        self.assertTrue(open_resp["ok"], open_resp)
        old_runtime_session_id = open_resp["session"]["session_id"]

        session = AgentSession(scope=AgentScope(agent_id="agent-test"))
        session.bind_runtime_session(
            old_runtime_session_id,
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto(open_dto),
            burr_db_path=str(self.db_path),
        )
        manager = DraftManager()
        checkpoint = AgentCheckpointStore(self.db_path)
        checkpoint.save(session, manager)
        checkpoint.close()

        cache = CandidatePayloadCache(self.db_path)
        cache.store(session.agent_session_id, old_runtime_session_id, [{"candidate_id": "cand_1", "value": 1}])
        cache.close()

        reset_runtime_sessions_for_tests()

        result = recover_agent_session(session.agent_session_id, db_path=self.db_path)
        self.addCleanup(result.candidate_cache.close)
        self.assertEqual(result.mode, "cold")
        self.assertNotEqual(result.session.runtime_session_id, old_runtime_session_id)
        self.assertEqual(len(result.stale_candidates), 1)
        self.assertEqual(result.stale_candidates[0]["candidate_id"], "cand_1")
        self.assertEqual(result.bundle_manager.list_bundles(), [])
        check_resp = get_runtime_session(result.session.runtime_session_id)
        self.assertTrue(check_resp["ok"], check_resp)
        close_runtime_session(result.session.runtime_session_id)

    def test_checkpoint_store_backward_compatible_empty_bundle_manager(self) -> None:
        store = AgentCheckpointStore(self.db_path)
        self.addCleanup(store.close)
        manager = DraftManager()
        session = AgentSession(scope=AgentScope(agent_id="agent-test"))
        session.bind_runtime_session(
            "rt_123",
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto({"schema_ir": self.schema_ir}),
            burr_db_path=str(self.db_path),
        )
        store.save(session, manager, BundleManager(draft_manager=manager))
        loaded_session, loaded_manager, loaded_bundle_manager = store.load(session.agent_session_id)
        self.assertEqual(loaded_session.runtime_session_id, "rt_123")
        self.assertEqual(loaded_manager.list_drafts(session.agent_session_id), [])
        self.assertEqual(loaded_bundle_manager.list_bundles(), [])

    def test_recover_without_bootstrap_spec_raises(self) -> None:
        checkpoint = AgentCheckpointStore(self.db_path)
        session = AgentSession(scope=AgentScope(agent_id="agent-test"))
        session.bind_runtime_session(
            "rt_missing",
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto({"schema_ir": self.schema_ir}),
            burr_db_path=str(self.db_path),
        )
        session.bootstrap_spec = None
        checkpoint.save(session, DraftManager())
        checkpoint.close()
        with self.assertRaises(AgentRecoveryError):
            recover_agent_session(session.agent_session_id, db_path=self.db_path)

    def test_build_layer1_agent_skeleton_exposes_tool_registry(self) -> None:
        session = AgentSession(scope=AgentScope(agent_id="agent-test"))
        session.bind_runtime_session(
            "rt_123",
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto({"schema_ir": self.schema_ir}),
        )
        skeleton = build_layer1_agent_skeleton(
            session=session,
            kg_read_tools=KGReadTools(runtime_api=LocalRuntimeAPI()),
            explain_tools=ExplainTools(runtime_api=LocalRuntimeAPI()),
            enable_tracing=True,
        )
        self.assertEqual(skeleton.state_sequence, LAYER1_STATE_SEQUENCE)
        self.assertIn("get_steps", skeleton.tool_registry)
        self.assertEqual(skeleton.tool_registry["list_rules"].name, "list_rules")
        if not skeleton.dependency_status.langfuse_available:
            self.assertFalse(skeleton.tracing_enabled)


if __name__ == "__main__":
    unittest.main()
