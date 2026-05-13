"""Layer 4C3-b BatchExtractor tests."""

from __future__ import annotations

import unittest

from factpy.agent import (
    AgentScope,
    BatchExtractionConfig,
    BatchExtractionError,
    BatchExtractionResult,
    BatchExtractor,
    ExtractionAgent,
    ExtractionError,
    ExtractionProvenance,
    ExtractionResult,
    FactDraftSpec,
)
from factpy.agent.documents import DocumentSegment
from factpy.tests._test_helpers import _schema_ir


def _segment(index: int, *, doc_id: str = "doc_1") -> DocumentSegment:
    return DocumentSegment(
        segment_id=f"seg_{index}",
        doc_id=doc_id,
        segment_index=index,
        section_label=f"Section {index + 1}",
        page_number=1,
        char_offset_start=index * 100,
        char_offset_end=(index + 1) * 100,
        raw_text=f"Segment {index} raw text",
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
    def __init__(self, outcomes: dict[str, object]) -> None:
        super().__init__(llm_client=object())
        self._outcomes = outcomes
        self.calls: list[str] = []
        self.context_args: list[str] = []
        self._call_counts: dict[str, int] = {}

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
        self.calls.append(segment.segment_id)
        self.context_args.append(prior_entity_context)
        count = self._call_counts.get(segment.segment_id, 0)
        self._call_counts[segment.segment_id] = count + 1
        outcome = self._outcomes[segment.segment_id]
        if isinstance(outcome, list):
            outcome = outcome[min(count, len(outcome) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class AgentLayer4C3bBatchExtractorTests(unittest.TestCase):
    def test_empty_segments_returns_batch_error(self) -> None:
        extractor = BatchExtractor(extraction_agent=_FakeExtractionAgent({}))
        result = extractor.extract_batch(
            segments=[],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3b"),
        )
        self.assertIsInstance(result, BatchExtractionError)
        self.assertEqual(result.error_kind, "empty_segments")

    def test_doc_id_mismatch_returns_batch_error(self) -> None:
        seg_a = _segment(0, doc_id="doc_a")
        seg_b = _segment(1, doc_id="doc_b")
        extractor = BatchExtractor(extraction_agent=_FakeExtractionAgent({}))
        result = extractor.extract_batch(
            segments=[seg_a, seg_b],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3b"),
        )
        self.assertIsInstance(result, BatchExtractionError)
        self.assertEqual(result.error_kind, "doc_id_mismatch")

    def test_segments_exceed_limit_returns_batch_error(self) -> None:
        seg_a = _segment(0)
        seg_b = _segment(1)
        extractor = BatchExtractor(extraction_agent=_FakeExtractionAgent({}))
        result = extractor.extract_batch(
            segments=[seg_a, seg_b],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3b"),
            batch_config=BatchExtractionConfig(max_segments_per_batch=1),
        )
        self.assertIsInstance(result, BatchExtractionError)
        self.assertEqual(result.error_kind, "segments_exceed_limit")

    def test_mixed_success_and_error_results_continue(self) -> None:
        seg_a = _segment(0)
        seg_b = _segment(1)
        seg_c = _segment(2)
        extractor = BatchExtractor(
            extraction_agent=_FakeExtractionAgent(
                {
                    seg_a.segment_id: _success(seg_a, "u-1"),
                    seg_b.segment_id: ExtractionError(
                        segment_id=seg_b.segment_id,
                        error_kind="dependency_missing",
                        error_message="missing deps",
                    ),
                    seg_c.segment_id: _success(seg_c, "u-2", "u-3"),
                }
            )
        )
        result = extractor.extract_batch(
            segments=[seg_a, seg_b, seg_c],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3b", max_batch_size=10),
        )
        self.assertEqual(result.success_count(), 2)
        self.assertEqual(result.error_count(), 1)
        self.assertEqual(len(result.aggregated_specs), 3)
        self.assertEqual(result.metrics.total_valid_count, 3)
        self.assertEqual(result.metrics.error_segment_count, 1)

    def test_unexpected_exception_becomes_extraction_error(self) -> None:
        seg_a = _segment(0)
        seg_b = _segment(1)
        seg_c = _segment(2)
        fake = _FakeExtractionAgent(
            {
                seg_a.segment_id: _success(seg_a, "u-1"),
                seg_b.segment_id: RuntimeError("boom"),
                seg_c.segment_id: _success(seg_c, "u-2"),
            }
        )
        extractor = BatchExtractor(extraction_agent=fake)
        result = extractor.extract_batch(
            segments=[seg_a, seg_b, seg_c],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3b"),
        )
        self.assertEqual(fake.calls, [seg_a.segment_id, seg_b.segment_id, seg_c.segment_id])
        self.assertEqual(result.segment_results[1].error_kind, "unexpected")
        self.assertEqual(result.error_count(), 1)

    def test_batch_cap_truncates_current_segment_and_marks_remaining(self) -> None:
        seg_a = _segment(0)
        seg_b = _segment(1)
        seg_c = _segment(2)
        fake = _FakeExtractionAgent(
            {
                seg_a.segment_id: _success(seg_a, "u-1"),
                seg_b.segment_id: _success(seg_b, "u-2", "u-3"),
                seg_c.segment_id: _success(seg_c, "u-4"),
            }
        )
        extractor = BatchExtractor(extraction_agent=fake)
        result = extractor.extract_batch(
            segments=[seg_a, seg_b, seg_c],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3b", max_batch_size=2),
        )
        self.assertEqual(fake.calls, [seg_a.segment_id, seg_b.segment_id])
        self.assertEqual(len(result.aggregated_specs), 2)
        second = result.segment_results[1]
        self.assertIsInstance(second, ExtractionResult)
        self.assertEqual(len(second.valid_specs), 1)
        self.assertEqual(second.rejections[-1].reason, "scope_max_batch_size")
        self.assertEqual(second.rejections[-1].proposal_index, -1)
        third = result.segment_results[2]
        self.assertIsInstance(third, ExtractionError)
        self.assertEqual(third.error_kind, "batch_cap_reached")
        self.assertEqual(result.metrics.total_valid_count, 2)

    def test_entity_context_accumulated_across_segments(self) -> None:
        seg_0 = _segment(0)
        seg_1 = _segment(1)
        seg_2 = _segment(2)
        agent = _FakeExtractionAgent({
            seg_0.segment_id: _success(seg_0, "alice"),
            seg_1.segment_id: _success(seg_1, "bob"),
            seg_2.segment_id: _success(seg_2, "carol"),
        })
        extractor = BatchExtractor(extraction_agent=agent)
        result = extractor.extract_batch(
            segments=[seg_0, seg_1, seg_2],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-ctx"),
        )
        self.assertIsInstance(result, BatchExtractionResult)
        self.assertEqual(agent.context_args[0], "")
        self.assertIn("alice", agent.context_args[1])
        self.assertIn("User", agent.context_args[1])
        self.assertIn("alice", agent.context_args[2])
        self.assertIn("bob", agent.context_args[2])

    def test_entity_context_disabled_via_config(self) -> None:
        seg_0 = _segment(0)
        seg_1 = _segment(1)
        agent = _FakeExtractionAgent({
            seg_0.segment_id: _success(seg_0, "alice"),
            seg_1.segment_id: _success(seg_1, "bob"),
        })
        extractor = BatchExtractor(extraction_agent=agent)
        result = extractor.extract_batch(
            segments=[seg_0, seg_1],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-ctx"),
            batch_config=BatchExtractionConfig(enable_entity_context=False),
        )
        self.assertIsInstance(result, BatchExtractionResult)
        self.assertEqual(agent.context_args[0], "")
        self.assertEqual(agent.context_args[1], "")

    def test_entity_context_skips_error_segments(self) -> None:
        seg_0 = _segment(0)
        seg_1 = _segment(1)
        seg_2 = _segment(2)
        agent = _FakeExtractionAgent({
            seg_0.segment_id: _success(seg_0, "alice"),
            seg_1.segment_id: ExtractionError(
                segment_id=seg_1.segment_id,
                error_kind="llm_unavailable",
                error_message="test error",
            ),
            seg_2.segment_id: _success(seg_2, "carol"),
        })
        extractor = BatchExtractor(extraction_agent=agent)
        result = extractor.extract_batch(
            segments=[seg_0, seg_1, seg_2],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-ctx"),
        )
        self.assertIsInstance(result, BatchExtractionResult)
        self.assertIn("alice", agent.context_args[2])
        self.assertNotIn("bob", agent.context_args[2])

    def test_gleaning_reexamines_zero_yield_segments(self) -> None:
        seg_0 = _segment(0)
        seg_1 = _segment(1)
        seg_2 = _segment(2)
        agent = _FakeExtractionAgent(
            {
                seg_0.segment_id: [_success(seg_0), _success(seg_0, "alice_gleaned")],
                seg_1.segment_id: _success(seg_1, "bob"),
                seg_2.segment_id: _success(seg_2, "carol"),
            }
        )
        extractor = BatchExtractor(extraction_agent=agent)
        result = extractor.extract_batch(
            segments=[seg_0, seg_1, seg_2],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-gl"),
            batch_config=BatchExtractionConfig(enable_gleaning=True),
        )
        self.assertIsInstance(result, BatchExtractionResult)
        self.assertEqual(result.gleaning_segments_reexamined, 1)
        self.assertEqual(len(agent.calls), 4)
        entity_types = [s.entity_type for s in result.aggregated_specs]
        self.assertIn("User", entity_types)

    def test_gleaning_disabled_by_default(self) -> None:
        seg_0 = _segment(0)
        seg_1 = _segment(1)
        agent = _FakeExtractionAgent(
            {
                seg_0.segment_id: _success(seg_0),
                seg_1.segment_id: _success(seg_1, "bob"),
            }
        )
        extractor = BatchExtractor(extraction_agent=agent)
        result = extractor.extract_batch(
            segments=[seg_0, seg_1],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-gl"),
        )
        self.assertIsInstance(result, BatchExtractionResult)
        self.assertEqual(result.gleaning_segments_reexamined, 0)
        self.assertEqual(len(agent.calls), 2)

    def test_gleaning_skips_error_segments(self) -> None:
        seg_0 = _segment(0)
        seg_1 = _segment(1)
        seg_2 = _segment(2)
        agent = _FakeExtractionAgent(
            {
                seg_0.segment_id: _success(seg_0),
                seg_1.segment_id: ExtractionError(
                    segment_id=seg_1.segment_id,
                    error_kind="llm_unavailable",
                    error_message="test error",
                ),
                seg_2.segment_id: _success(seg_2, "carol"),
            }
        )
        extractor = BatchExtractor(extraction_agent=agent)
        result = extractor.extract_batch(
            segments=[seg_0, seg_1, seg_2],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-gl"),
            batch_config=BatchExtractionConfig(enable_gleaning=True),
        )
        self.assertIsInstance(result, BatchExtractionResult)
        self.assertEqual(result.gleaning_segments_reexamined, 1)

    def test_gleaning_adds_specs_to_aggregated(self) -> None:
        seg_0 = _segment(0)
        seg_1 = _segment(1)
        agent = _FakeExtractionAgent(
            {
                seg_0.segment_id: [_success(seg_0), _success(seg_0, "gleaned_user")],
                seg_1.segment_id: _success(seg_1, "bob", "carol"),
            }
        )
        extractor = BatchExtractor(extraction_agent=agent)
        result = extractor.extract_batch(
            segments=[seg_0, seg_1],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-gl"),
            batch_config=BatchExtractionConfig(enable_gleaning=True),
        )
        self.assertIsInstance(result, BatchExtractionResult)
        self.assertEqual(len(result.aggregated_specs), 3)

    def test_gleaning_respects_batch_cap(self) -> None:
        seg_0 = _segment(0)
        seg_1 = _segment(1)
        agent = _FakeExtractionAgent(
            {
                seg_0.segment_id: [_success(seg_0), _success(seg_0, "gleaned_user")],
                seg_1.segment_id: _success(seg_1, "bob"),
            }
        )
        extractor = BatchExtractor(extraction_agent=agent)
        result = extractor.extract_batch(
            segments=[seg_0, seg_1],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-gl", max_batch_size=1),
            batch_config=BatchExtractionConfig(enable_gleaning=True),
        )
        self.assertIsInstance(result, BatchExtractionResult)
        self.assertEqual(result.gleaning_segments_reexamined, 0)

    def test_gleaning_exception_is_nonfatal(self) -> None:
        seg_0 = _segment(0)
        seg_1 = _segment(1)
        agent = _FakeExtractionAgent(
            {
                seg_0.segment_id: [_success(seg_0), RuntimeError("gleaning boom")],
                seg_1.segment_id: _success(seg_1, "bob"),
            }
        )
        extractor = BatchExtractor(extraction_agent=agent)
        result = extractor.extract_batch(
            segments=[seg_0, seg_1],
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-gl"),
            batch_config=BatchExtractionConfig(enable_gleaning=True),
        )
        self.assertIsInstance(result, BatchExtractionResult)
        self.assertEqual(result.gleaning_segments_reexamined, 1)
        self.assertEqual(len(result.aggregated_specs), 1)


if __name__ == "__main__":
    unittest.main()
