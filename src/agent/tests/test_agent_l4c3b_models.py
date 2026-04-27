"""Layer 4C3-b batch extraction model tests."""

from __future__ import annotations

import unittest

from agent import (
    AgentContractError,
    BatchExtractionConfig,
    BatchExtractionError,
    BatchExtractionMetrics,
    BatchExtractionResult,
    ExtractionError,
    ExtractionProvenance,
    ExtractionRejection,
    ExtractionResult,
    FactDraftSpec,
    SegmentMetric,
)


def _spec() -> FactDraftSpec:
    return FactDraftSpec(
        entity_type="User",
        entity_identity={"user_id": "u-1", "locale": "zh"},
        pred_id="user:tag",
        field_values=[("string", "vip")],
        extraction_provenance=ExtractionProvenance(
            source_document_id="doc_1",
            segment_id="seg_1",
            char_offset_start=0,
            char_offset_end=10,
            raw_text="Alice VIP",
            extraction_method="llm_refined",
        ),
    )


class AgentLayer4C3bModelsTests(unittest.TestCase):
    def test_extraction_rejection_accepts_batch_sentinel_index(self) -> None:
        rejection = ExtractionRejection(
            reason="scope_max_batch_size",
            detail="batch cap reached; truncated 2 specs",
            proposal_index=-1,
        )
        self.assertEqual(rejection.proposal_index, -1)

    def test_batch_extraction_config_rejects_non_positive_segment_limit(self) -> None:
        with self.assertRaises(AgentContractError):
            BatchExtractionConfig(max_segments_per_batch=0)

    def test_batch_extraction_metrics_to_dict_is_json_friendly(self) -> None:
        metrics = BatchExtractionMetrics(
            doc_id="doc_1",
            total_segments=2,
            success_segment_count=1,
            error_segment_count=1,
            total_proposal_count=3,
            total_valid_count=1,
            total_rejection_count=2,
            batch_started_at_ns=100,
            batch_finished_at_ns=200,
            batch_duration_ms=0,
            per_segment_metrics=(
                SegmentMetric(
                    segment_id="seg_1",
                    model="gpt-4o-mini",
                    llm_latency_ms=10,
                    proposal_count=3,
                    valid_count=1,
                    rejection_count=2,
                    error_kind=None,
                ),
            ),
        )
        data = metrics.to_dict()
        self.assertEqual(data["doc_id"], "doc_1")
        self.assertIsInstance(data["per_segment_metrics"], list)
        self.assertEqual(data["per_segment_metrics"][0]["segment_id"], "seg_1")

    def test_batch_extraction_result_helper_methods(self) -> None:
        result = BatchExtractionResult(
            doc_id="doc_1",
            total_segments=2,
            segment_results=(
                ExtractionResult(
                    segment_id="seg_1",
                    valid_specs=[_spec()],
                    total_proposals=1,
                    rejections=[],
                    model="gpt-4o-mini",
                    llm_latency_ms=12,
                ),
                ExtractionError(
                    segment_id="seg_2",
                    error_kind="dependency_missing",
                    error_message="missing deps",
                ),
            ),
            aggregated_specs=(_spec(),),
            metrics=BatchExtractionMetrics(
                doc_id="doc_1",
                total_segments=2,
                success_segment_count=1,
                error_segment_count=1,
                total_proposal_count=1,
                total_valid_count=1,
                total_rejection_count=0,
                batch_started_at_ns=10,
                batch_finished_at_ns=20,
                batch_duration_ms=0,
                per_segment_metrics=(),
            ),
        )
        self.assertEqual(result.success_count(), 1)
        self.assertEqual(result.error_count(), 1)
        self.assertTrue(result.has_any_valid())

    def test_batch_extraction_error_requires_message(self) -> None:
        with self.assertRaises(AgentContractError):
            BatchExtractionError(
                doc_id=None,
                error_kind="empty_segments",
                error_message="",
            )


class BatchExtractionConfigEntityContextTests(unittest.TestCase):
    def test_enable_entity_context_default_true(self) -> None:
        config = BatchExtractionConfig()
        self.assertTrue(config.enable_entity_context)

    def test_enable_entity_context_false_accepted(self) -> None:
        config = BatchExtractionConfig(enable_entity_context=False)
        self.assertFalse(config.enable_entity_context)

    def test_enable_entity_context_non_bool_rejected(self) -> None:
        with self.assertRaises(AgentContractError):
            BatchExtractionConfig(enable_entity_context="yes")


class BatchExtractionConfigGleaningTests(unittest.TestCase):
    def test_enable_gleaning_default_false(self) -> None:
        config = BatchExtractionConfig()
        self.assertFalse(config.enable_gleaning)

    def test_gleaning_yield_threshold_default_zero(self) -> None:
        config = BatchExtractionConfig()
        self.assertEqual(config.gleaning_yield_threshold, 0)

    def test_enable_gleaning_true_accepted(self) -> None:
        config = BatchExtractionConfig(enable_gleaning=True)
        self.assertTrue(config.enable_gleaning)

    def test_enable_gleaning_non_bool_rejected(self) -> None:
        with self.assertRaises(AgentContractError):
            BatchExtractionConfig(enable_gleaning="yes")

    def test_gleaning_threshold_negative_rejected(self) -> None:
        with self.assertRaises(AgentContractError):
            BatchExtractionConfig(gleaning_yield_threshold=-1)


class BatchExtractionResultGleaningTests(unittest.TestCase):
    def test_gleaning_field_default_zero(self) -> None:
        result = BatchExtractionResult(
            doc_id="doc_1",
            total_segments=1,
            segment_results=(),
            aggregated_specs=(),
            metrics=BatchExtractionMetrics(
                doc_id="doc_1",
                total_segments=1,
                success_segment_count=0,
                error_segment_count=0,
                total_proposal_count=0,
                total_valid_count=0,
                total_rejection_count=0,
                batch_started_at_ns=0,
                batch_finished_at_ns=0,
                batch_duration_ms=0,
                per_segment_metrics=(),
            ),
        )
        self.assertEqual(result.gleaning_segments_reexamined, 0)


if __name__ == "__main__":
    unittest.main()
