"""Layer 4C3-c EntityResolver tests."""

from __future__ import annotations

import unittest

from factpy.agent import (
    EntityResolver,
    ExtractionProvenance,
    FactDraftSpec,
    MergeEvent,
    ResolutionConfig,
    ResolutionError,
    ResolutionResult,
)


def _spec(
    *,
    segment_id: str,
    entity_type: str = "User",
    entity_identity: dict[str, object] | None = None,
    pred_id: str = "user:tag",
    field_values: list[tuple[str, object]] | None = None,
    confidence: float | None = None,
    doc_id: str = "doc_1",
    merged_from: tuple[ExtractionProvenance, ...] = (),
) -> FactDraftSpec:
    return FactDraftSpec(
        entity_type=entity_type,
        entity_identity=entity_identity or {"user_id": "u-1", "locale": "zh"},
        pred_id=pred_id,
        field_values=field_values or [("string", "vip")],
        extraction_provenance=ExtractionProvenance(
            source_document_id=doc_id,
            segment_id=segment_id,
            char_offset_start=0,
            char_offset_end=10,
            raw_text=f"text-{segment_id}",
            extraction_method="llm_refined",
            merged_from=merged_from,
        ),
        confidence=confidence,
    )


class AgentLayer4C3cResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = EntityResolver()

    def test_empty_specs_returns_resolution_error(self) -> None:
        result = self.resolver.resolve_batch([])
        self.assertIsInstance(result, ResolutionError)
        self.assertEqual(result.error_kind, "empty_specs")

    def test_doc_id_mismatch_returns_resolution_error(self) -> None:
        result = self.resolver.resolve_batch(
            [
                _spec(segment_id="seg_1", doc_id="doc_a"),
                _spec(segment_id="seg_2", doc_id="doc_b"),
            ]
        )
        self.assertIsInstance(result, ResolutionError)
        self.assertEqual(result.error_kind, "doc_id_mismatch")

    def test_duplicate_specs_merge_and_confidence_takes_max(self) -> None:
        result = self.resolver.resolve_batch(
            [
                _spec(segment_id="seg_1", confidence=0.6),
                _spec(segment_id="seg_2", confidence=0.9),
                _spec(segment_id="seg_3", entity_identity={"user_id": "u-2", "locale": "en"}),
            ]
        )
        self.assertEqual(len(result.resolved_specs), 2)
        self.assertEqual(result.stats.merge_count, 1)
        merged = result.resolved_specs[0]
        self.assertEqual(merged.confidence, 0.9)
        self.assertEqual(merged.extraction_provenance.source_segment_ids(), ("seg_1", "seg_2"))
        self.assertEqual(result.merge_events[0].primary_segment_id, "seg_1")
        self.assertEqual(result.merge_events[0].merged_segment_id, "seg_2")

    def test_field_value_order_is_semantic(self) -> None:
        result = self.resolver.resolve_batch(
            [
                _spec(
                    segment_id="seg_1",
                    pred_id="user:related_to",
                    field_values=[("entity_ref", "ent:alice"), ("entity_ref", "ent:bob")],
                ),
                _spec(
                    segment_id="seg_2",
                    pred_id="user:related_to",
                    field_values=[("entity_ref", "ent:bob"), ("entity_ref", "ent:alice")],
                ),
            ]
        )
        self.assertEqual(len(result.resolved_specs), 2)
        self.assertEqual(result.stats.merge_count, 0)

    def test_enable_dedupe_false_passthroughs_input(self) -> None:
        specs = [_spec(segment_id="seg_1"), _spec(segment_id="seg_2")]
        result = self.resolver.resolve_batch(specs, config=ResolutionConfig(enable_dedupe=False))
        self.assertEqual(result.resolved_specs, tuple(specs))
        self.assertEqual(result.stats.merge_count, 0)

    def test_resolution_is_idempotent_for_merged_specs(self) -> None:
        first = self.resolver.resolve_batch(
            [
                _spec(segment_id="seg_1"),
                _spec(segment_id="seg_2"),
                _spec(segment_id="seg_3"),
            ]
        )
        second = self.resolver.resolve_batch(list(first.resolved_specs))

        self.assertEqual(second.stats.merge_count, 0)
        self.assertEqual(len(second.resolved_specs), 1)
        self.assertEqual(
            set(second.resolved_specs[0].extraction_provenance.source_segment_ids()),
            {"seg_1", "seg_2", "seg_3"},
        )


class AliasResolverTests(unittest.TestCase):
    """Tests for P2 alias merge in EntityResolver."""

    def test_alias_merge_combines_token_subset(self) -> None:
        specs = [
            _spec(
                segment_id="s0",
                entity_type="Module",
                entity_identity={"name": "Kafka Ingest Pipeline"},
                pred_id="module:description",
                field_values=[("string", "handles events")],
            ),
            _spec(
                segment_id="s1",
                entity_type="Module",
                entity_identity={"name": "ingest"},
                pred_id="module:owner",
                field_values=[("string", "data-infra")],
            ),
        ]
        resolver = EntityResolver(config=ResolutionConfig(enable_alias_merge=True))
        result = resolver.resolve_batch(specs)
        self.assertIsInstance(result, ResolutionResult)
        keys = {s.entity_identity.get("name") for s in result.resolved_specs}
        self.assertEqual(len(keys), 1)
        self.assertIn("Kafka Ingest Pipeline", keys)

    def test_alias_merge_does_not_combine_different_entities(self) -> None:
        specs = [
            _spec(
                segment_id="s0",
                entity_type="Module",
                entity_identity={"name": "resolve"},
                pred_id="module:owner",
                field_values=[("string", "Alice")],
            ),
            _spec(
                segment_id="s1",
                entity_type="Module",
                entity_identity={"name": "serve"},
                pred_id="module:owner",
                field_values=[("string", "Bob")],
            ),
        ]
        resolver = EntityResolver(config=ResolutionConfig(enable_alias_merge=True))
        result = resolver.resolve_batch(specs)
        self.assertIsInstance(result, ResolutionResult)
        keys = {s.entity_identity.get("name") for s in result.resolved_specs}
        self.assertEqual(keys, {"resolve", "serve"})

    def test_alias_merge_disabled_by_default(self) -> None:
        specs = [
            _spec(
                segment_id="s0",
                entity_type="Module",
                entity_identity={"name": "Kafka Ingest Pipeline"},
                pred_id="module:description",
                field_values=[("string", "handles events")],
            ),
            _spec(
                segment_id="s1",
                entity_type="Module",
                entity_identity={"name": "ingest"},
                pred_id="module:owner",
                field_values=[("string", "data-infra")],
            ),
        ]
        resolver = EntityResolver()
        result = resolver.resolve_batch(specs)
        self.assertIsInstance(result, ResolutionResult)
        keys = {s.entity_identity.get("name") for s in result.resolved_specs}
        self.assertEqual(len(keys), 2)

    def test_alias_merge_records_alias_flag(self) -> None:
        specs = [
            _spec(
                segment_id="s0",
                entity_type="Module",
                entity_identity={"name": "Kafka Ingest Pipeline"},
                pred_id="module:description",
                field_values=[("string", "handles events")],
            ),
            _spec(
                segment_id="s1",
                entity_type="Module",
                entity_identity={"name": "ingest"},
                pred_id="module:description",
                field_values=[("string", "handles events")],
            ),
        ]
        resolver = EntityResolver(config=ResolutionConfig(enable_alias_merge=True))
        result = resolver.resolve_batch(specs)
        self.assertIsInstance(result, ResolutionResult)
        self.assertTrue(result.has_merges())
        alias_merges = [e for e in result.merge_events if e.alias_merge]
        self.assertGreater(len(alias_merges), 0)

    def test_alias_merge_skips_multi_field_identity(self) -> None:
        specs = [
            _spec(
                segment_id="s0",
                entity_identity={"user_id": "alice", "locale": "zh"},
                pred_id="user:tag",
                field_values=[("string", "vip")],
            ),
            _spec(
                segment_id="s1",
                entity_identity={"user_id": "alice chen", "locale": "zh"},
                pred_id="user:tag",
                field_values=[("string", "staff")],
            ),
        ]
        resolver = EntityResolver(config=ResolutionConfig(enable_alias_merge=True))
        result = resolver.resolve_batch(specs)
        self.assertIsInstance(result, ResolutionResult)
        self.assertEqual(len(result.resolved_specs), 2)


if __name__ == "__main__":
    unittest.main()
