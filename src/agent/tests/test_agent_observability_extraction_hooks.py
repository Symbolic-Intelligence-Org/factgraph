"""Agent observability extraction hook tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agent import (
    AgentCheckpointStore,
    AgentScope,
    AgentSession,
    BatchExtractor,
    CandidatePayloadCache,
    DocumentSegment,
    DocumentStaging,
    DraftManager,
    EntityResolver,
    ExtractionAgent,
    ExtractionConfig,
    ExtractionError,
    ExtractionProvenance,
    ExtractionResult,
    FactDraftSpec,
    NoOpTracer,
    ReadReviewOrchestrator,
    ResolutionConfig,
    RuntimeBootstrapSpec,
)
from agent.documents import BundleManager
from agent.tools._runtime_api import LocalRuntimeAPI
from agent.tools.evaluate import EvaluateTools
from agent.tools.explain import ExplainTools
from agent.tools.kg_read import KGReadTools
from agent.tools.write import WriteTools
from service.runtime_v1 import (
    close_runtime_session,
    get_runtime_session,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
)
from kernel.tests._test_helpers import _schema_ir


class _RecordingTracer:
    def __init__(self, *, raise_on: set[str] | None = None) -> None:
        self.raise_on = raise_on or set()
        self.single: list[dict[str, object]] = []
        self.batch: list[dict[str, object]] = []
        self.resolution: list[dict[str, object]] = []

    def record_single_segment_extraction(self, *, attributes: dict[str, object]) -> None:
        if "single" in self.raise_on:
            raise RuntimeError("single trace failed")
        self.single.append(attributes)

    def record_batch_extraction(self, *, attributes: dict[str, object]) -> None:
        if "batch" in self.raise_on:
            raise RuntimeError("batch trace failed")
        self.batch.append(attributes)

    def record_resolution(self, *, attributes: dict[str, object]) -> None:
        if "resolution" in self.raise_on:
            raise RuntimeError("resolution trace failed")
        self.resolution.append(attributes)


class _FakeCompletions:
    def __init__(self, behavior):
        self._behavior = behavior

    def create(self, **kwargs):
        return self._behavior(kwargs)


class _FakeChat:
    def __init__(self, behavior):
        self.completions = _FakeCompletions(behavior)


class _FakeClient:
    def __init__(self, behavior):
        self.chat = _FakeChat(behavior)


def _segment(index: int, *, doc_id: str = "doc_1", raw_text: str | None = None) -> DocumentSegment:
    return DocumentSegment(
        segment_id=f"seg_{index}",
        doc_id=doc_id,
        segment_index=index,
        section_label=f"Section {index + 1}",
        page_number=1,
        char_offset_start=index * 100,
        char_offset_end=(index + 1) * 100,
        raw_text=raw_text or f"Segment {index} raw text",
        structural_clarity=0.8,
        pattern_type="entity_relation",
        parser_version="txt_v1",
    )


def _spec(segment: DocumentSegment, user_id: str) -> FactDraftSpec:
    return FactDraftSpec(
        entity_type="User",
        entity_identity={"user_id": user_id, "locale": "zh"},
        pred_id="user:tag",
        field_values=[("string", f"tag-{user_id}")],
        extraction_provenance=ExtractionProvenance(
            source_document_id=segment.doc_id,
            segment_id=segment.segment_id,
            char_offset_start=segment.char_offset_start,
            char_offset_end=segment.char_offset_end,
            raw_text=segment.raw_text,
            page_number=segment.page_number,
            extraction_method="llm_refined",
        ),
    )


def _success(segment: DocumentSegment, *user_ids: str) -> ExtractionResult:
    return ExtractionResult(
        segment_id=segment.segment_id,
        valid_specs=[_spec(segment, user_id) for user_id in user_ids],
        total_proposals=len(user_ids),
        rejections=[],
        model="gpt-4o-mini",
        llm_latency_ms=15,
    )


class _FakeExtractionAgent(ExtractionAgent):
    def __init__(self, outcomes: dict[str, object], *, tracer=None) -> None:
        super().__init__(llm_client=object(), tracer=tracer or NoOpTracer())
        self._outcomes = outcomes

    def extract_from_segment(
        self,
        *,
        segment,
        schema_ir,
        scope,
        config=None,
        prior_entity_context="",
        source_doc_name=None,
        entity_descriptions=None,
    ):
        outcome = self._outcomes[segment.segment_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _open_session(open_dto: dict[str, object]) -> str:
    resp = open_runtime_session(open_dto)
    assert resp["ok"], resp
    return resp["session"]["session_id"]


class AgentObservabilityExtractionHookTests(unittest.TestCase):
    def test_single_segment_success_emits_stable_fields(self) -> None:
        tracer = _RecordingTracer()

        def _behavior(kwargs):
            response_model = kwargs["response_model"]
            return response_model(
                proposals=[
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-1"},
                            {"name": "locale", "value": "zh"},
                        ],
                        "pred_id": "user:tag",
                        "field_values": [{"tag": "string", "value": "vip"}],
                        "confidence": 0.9,
                    }
                ]
            )

        agent = ExtractionAgent(
            config=ExtractionConfig(max_text_chars=50),
            llm_client=_FakeClient(_behavior),
            tracer=tracer,
        )
        segment = _segment(0, raw_text="Alice is a VIP customer.")
        result = agent.extract_from_segment(
            segment=segment,
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-observe"),
        )

        self.assertIsInstance(result, ExtractionResult)
        self.assertEqual(len(tracer.single), 1)
        payload = tracer.single[0]
        self.assertEqual(
            set(payload),
            {
                "segment_id",
                "doc_id",
                "model",
                "llm_latency_ms",
                "proposal_count",
                "valid_count",
                "rejection_count",
                "error_kind",
                "structural_clarity",
                "pattern_type",
            },
        )
        self.assertEqual(payload["segment_id"], segment.segment_id)
        self.assertEqual(payload["error_kind"], None)
        self.assertNotIn("raw_text", payload)

    def test_single_segment_error_and_tracer_failure_do_not_break_business(self) -> None:
        tracer = _RecordingTracer(raise_on={"single"})
        agent = ExtractionAgent(config=ExtractionConfig(), tracer=tracer)
        segment = _segment(0)
        with patch(
            "agent.extraction.extractor.build_default_llm_client",
            side_effect=ImportError("missing deps"),
        ):
            result = agent.extract_from_segment(
                segment=segment,
                schema_ir=_schema_ir(),
                scope=AgentScope(agent_id="agent-observe"),
            )
        self.assertIsInstance(result, ExtractionError)
        self.assertEqual(result.error_kind, "dependency_missing")

    def test_batch_trace_detects_rejection_based_cap(self) -> None:
        tracer = _RecordingTracer()
        seg_a = _segment(0)
        seg_b = _segment(1)
        extractor = BatchExtractor(
            extraction_agent=_FakeExtractionAgent(
                {
                    seg_a.segment_id: _success(seg_a, "u-1"),
                    seg_b.segment_id: _success(seg_b, "u-2", "u-3"),
                }
            ),
            tracer=tracer,
        )
        result = extractor.extract_batch(
            segments=[seg_a, seg_b],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-observe", max_batch_size=2),
        )
        self.assertEqual(len(result.aggregated_specs), 2)
        self.assertEqual(len(tracer.batch), 1)
        self.assertEqual(tracer.batch[0]["batch_cap_reached"], True)

    def test_batch_trace_detects_error_based_cap(self) -> None:
        tracer = _RecordingTracer()
        seg_a = _segment(0)
        seg_b = _segment(1)
        extractor = BatchExtractor(
            extraction_agent=_FakeExtractionAgent(
                {
                    seg_a.segment_id: _success(seg_a, "u-1"),
                    seg_b.segment_id: _success(seg_b, "u-2"),
                }
            ),
            tracer=tracer,
        )
        result = extractor.extract_batch(
            segments=[seg_a, seg_b],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-observe", max_batch_size=1),
        )
        self.assertEqual(result.segment_results[1].error_kind, "batch_cap_reached")
        self.assertEqual(tracer.batch[0]["batch_cap_reached"], True)

    def test_resolution_trace_respects_enable_dedupe_flag(self) -> None:
        tracer = _RecordingTracer()
        resolver = EntityResolver(tracer=tracer)
        specs = [_spec(_segment(0), "u-1"), _spec(_segment(1), "u-1")]
        result = resolver.resolve_batch(specs, config=ResolutionConfig(enable_dedupe=False))
        self.assertEqual(len(result.resolved_specs), 2)
        self.assertEqual(len(tracer.resolution), 1)
        self.assertEqual(tracer.resolution[0]["dedupe_enabled"], False)


class AgentObservabilitySharedTracerWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "agent_observability.sqlite3"
        self.ledger_path = str(Path(self.tmp.name) / "runtime-ledger.db")
        self.open_dto = {"schema_ir": _schema_ir(), "ledger_path": self.ledger_path}
        self.runtime_session_id = _open_session(self.open_dto)

        self.agent_session = AgentSession(
            scope=AgentScope(
                agent_id="agent-observability",
                allowed_entity_types=frozenset({"User"}),
                allowed_pred_ids=frozenset({"user:tag"}),
                require_source=True,
                max_batch_size=10,
            )
        )
        self.agent_session.bind_runtime_session(
            self.runtime_session_id,
            bootstrap_spec=RuntimeBootstrapSpec.from_open_dto(self.open_dto),
            burr_db_path=str(self.db_path),
        )
        self.draft_manager = DraftManager()
        self.bundle_manager = BundleManager(draft_manager=self.draft_manager)
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
        self.write_tools = WriteTools(runtime_api=self.runtime_api, session=self.agent_session)
        self.document_staging = DocumentStaging()
        self.tracer = _RecordingTracer()

        def _behavior(kwargs):
            response_model = kwargs["response_model"]
            user_prompt = kwargs["messages"][1]["content"]
            if "Alice is a VIP customer" in user_prompt:
                proposals = [
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-doc-1"},
                            {"name": "locale", "value": "zh"},
                        ],
                        "pred_id": "user:tag",
                        "field_values": [{"tag": "string", "value": "vip"}],
                        "confidence": 0.91,
                    }
                ]
            elif "Bob is a staff user" in user_prompt:
                proposals = [
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-doc-2"},
                            {"name": "locale", "value": "en"},
                        ],
                        "pred_id": "user:tag",
                        "field_values": [{"tag": "string", "value": "staff"}],
                        "confidence": 0.87,
                    }
                ]
            else:
                proposals = []
            return response_model(proposals=proposals)

        self.extraction_agent = ExtractionAgent(
            config=ExtractionConfig(max_text_chars=500),
            llm_client=_FakeClient(_behavior),
            tracer=self.tracer,
        )
        self.batch_extractor = BatchExtractor(
            extraction_agent=self.extraction_agent,
            tracer=self.tracer,
        )
        self.entity_resolver = EntityResolver(tracer=self.tracer)
        self.orchestrator = ReadReviewOrchestrator(
            session=self.agent_session,
            draft_manager=self.draft_manager,
            kg_read_tools=self.kg,
            explain_tools=self.explain,
            evaluate_tools=self.evaluate_tools,
            candidate_cache=self.cache,
            checkpoint_store=self.checkpoint,
            write_tools=self.write_tools,
            document_staging=self.document_staging,
            bundle_manager=self.bundle_manager,
            extraction_agent=self.extraction_agent,
            batch_extractor=self.batch_extractor,
            entity_resolver=self.entity_resolver,
        )

    def tearDown(self) -> None:
        self.cache.close()
        self.checkpoint.close()
        if get_runtime_session(self.runtime_session_id).get("ok") is True:
            close_runtime_session(self.runtime_session_id)
        reset_runtime_sessions_for_tests()

    def test_shared_tracer_receives_single_batch_and_resolution_events(self) -> None:
        staging = self.orchestrator.stage_document(
            doc_name="sample.txt",
            content=(
                b"Section 1\n"
                b"Alice is a VIP customer.\n\n"
                b"Section 2\n"
                b"Alice is a VIP customer.\n\n"
                b"Section 3\n"
                b"Bob is a staff user."
            ),
        )
        batch, resolution, bundle = self.orchestrator.extract_resolve_and_create_document_bundle(
            segments=list(staging.segments),
            source_document_name=staging.source.doc_name,
        )
        self.assertEqual(len(batch.aggregated_specs), 3)
        self.assertIsNotNone(resolution)
        self.assertIsNotNone(bundle)
        self.assertEqual(len(self.tracer.single), 3)
        self.assertEqual(len(self.tracer.batch), 1)
        self.assertEqual(len(self.tracer.resolution), 1)
        self.assertEqual(self.tracer.batch[0]["doc_id"], staging.source.doc_id)
        self.assertEqual(self.tracer.resolution[0]["merge_count"], 1)


if __name__ == "__main__":
    unittest.main()
